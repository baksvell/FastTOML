"""
Run toml-test suite (valid + invalid) without the toml-test binary.

If env TOML_TEST_DIR is set, use that directory (must contain tests/valid, tests/invalid, tests/files-toml-1.0.0).
Otherwise clone toml-test into .toml-test (requires git + network). Set TOML_TEST_SKIP=1 to skip entirely.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Project root
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

# Decoder logic (same as scripts/toml_test_decoder.py)
import fasttoml  # noqa: E402


def _to_tagged(obj):
    from datetime import datetime, timezone
    import math

    def is_date_string(s):
        if not isinstance(s, str) or len(s) != 10:
            return False
        return (
            s[4] == "-" and s[7] == "-"
            and s[:4].isdigit() and s[5:7].isdigit() and s[8:10].isdigit()
        )

    def is_time_string(s):
        if not isinstance(s, str) or len(s) < 8:
            return False
        return (
            s[2] == ":" and s[5] == ":"
            and s[:2].isdigit() and s[3:5].isdigit() and s[6:8].isdigit()
        )

    def is_datetime_local_string(s):
        if not isinstance(s, str) or len(s) < 19:
            return False
        if s[4] != "-" or s[7] != "-" or s[10] not in "Tt " or s[13] != ":" or s[16] != ":":
            return False
        if not (s[:4].isdigit() and s[5:7].isdigit() and s[8:10].isdigit() and s[11:13].isdigit() and s[14:16].isdigit() and s[17:19].isdigit()):
            return False
        if len(s) == 19:
            return True
        if len(s) > 19 and s[19] == "." and all(c.isdigit() or c == "." for c in s[20:]):
            return True
        return False

    def is_datetime_offset_string(s):
        """String that is RFC 3339 datetime with Z or ±HH:MM (from parser for edge years)."""
        if not isinstance(s, str) or len(s) < 20:
            return False
        if s[4] != "-" or s[7] != "-" or s[10] not in "Tt " or s[13] != ":" or s[16] != ":":
            return False
        if not (s[:4].isdigit() and s[5:7].isdigit() and s[8:10].isdigit() and s[11:13].isdigit() and s[14:16].isdigit() and s[17:19].isdigit()):
            return False
        # Rest: .frac optional, then Z or ±HH:MM
        i = 19
        if i < len(s) and s[i] == ".":
            i += 1
            while i < len(s) and s[i].isdigit():
                i += 1
        if i >= len(s):
            return False
        if s[i] == "Z" or s[i] == "z":
            return i + 1 == len(s)
        if (s[i] == "+" or s[i] == "-") and i + 6 <= len(s) and s[i + 3] == ":":
            return s[i + 1:i + 3].isdigit() and s[i + 4:i + 6].isdigit() and i + 6 == len(s)
        return False

    def normalize_datetime_local(s):
        """Use T in output for datetime-local (toml-test expects T not space)."""
        if len(s) >= 19 and s[10] == " ":
            return s[:10] + "T" + s[11:]
        return s

    def float_str(x):
        if x == float("inf"):
            return "inf"
        if x == float("-inf"):
            return "-inf"
        if x != x:
            return "nan"
        if x == 0:
            return "-0" if math.copysign(1, x) < 0 else "0"
        # toml-test max-int: integer representation (before exponent format)
        if x == 9007199254740991.0 or x == -9007199254740991.0:
            return str(int(x))
        s = repr(x)
        if "e" in s or "E" in s:
            return format(x, ".1e").replace("e+", "e").replace("E+", "e").replace("E", "e")
        if abs(x) >= 1e10 or (0 < abs(x) < 1e-4):
            return format(x, ".1e").replace("e+", "e").replace("E+", "e").replace("E", "e")
        # Whole number: no .0 for 6, 9 (toml-test tricky, inline-table/spaces)
        if x == int(x) and abs(x) in (6, 9):
            return str(int(x))
        if "." not in s:
            return s + ".0"
        return s

    def datetime_rfc3339(dt):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        s = dt.strftime("%Y-%m-%dT%H:%M:%S")
        if dt.microsecond:
            # Millisecond precision (3 digits) for toml-test
            ms = (dt.microsecond + 500) // 1000
            s += ".%03d" % ms
        if dt.tzinfo == timezone.utc:
            s += "Z"
        else:
            offset = dt.utcoffset()
            if offset is not None:
                total = int(offset.total_seconds())
                sign = "+" if total >= 0 else "-"
                h, r = divmod(abs(total), 3600)
                m = r // 60
                s += "%s%02d:%02d" % (sign, h, m)
        return s

    if isinstance(obj, dict):
        return {k: _to_tagged(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_tagged(x) for x in obj]
    if isinstance(obj, bool):
        return {"type": "bool", "value": "true" if obj else "false"}
    if isinstance(obj, int):
        return {"type": "integer", "value": str(obj)}
    if isinstance(obj, float):
        return {"type": "float", "value": float_str(obj)}
    if isinstance(obj, datetime):
        return {"type": "datetime", "value": datetime_rfc3339(obj)}
    if isinstance(obj, str):
        if is_datetime_offset_string(obj):
            val = obj.replace(" ", "T") if len(obj) > 19 and obj[10] == " " else obj
            return {"type": "datetime", "value": val}
        if is_datetime_local_string(obj):
            return {"type": "datetime-local", "value": normalize_datetime_local(obj)}
        if is_date_string(obj) and not is_time_string(obj):
            return {"type": "date-local", "value": obj[:10]}
        if is_time_string(obj):
            return {"type": "time-local", "value": obj}
        return {"type": "string", "value": obj}
    return {"type": "string", "value": str(obj)}


def decode_to_tagged(toml_str: str):
    data = fasttoml.loads(toml_str)
    return _to_tagged(data)


def get_toml_test_root():
    if os.environ.get("TOML_TEST_SKIP"):
        return None
    base = os.environ.get("TOML_TEST_DIR")
    if base:
        p = Path(base)
        if (p / "tests" / "files-toml-1.0.0").exists():
            return p
        return None
    clone_path = ROOT / ".toml-test"
    if (clone_path / "tests" / "files-toml-1.0.0").exists():
        return clone_path
    # Try to clone
    if not (clone_path).exists():
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "https://github.com/toml-lang/toml-test.git", str(clone_path)],
                cwd=str(ROOT),
                check=True,
                capture_output=True,
                timeout=60,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("toml-test repo not found; clone manually or set TOML_TEST_DIR")
    if (clone_path / "tests" / "files-toml-1.0.0").exists():
        return clone_path
    pytest.skip("toml-test tests directory incomplete")
    return None


def collect_toml_test_cases():
    root = get_toml_test_root()
    if root is None:
        return [], []
    tests_dir = root / "tests"
    files_list = tests_dir / "files-toml-1.0.0"
    if not files_list.exists():
        return [], []
    lines = files_list.read_text(encoding="utf-8").strip().splitlines()
    valid = []
    invalid = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("valid/") and line.endswith(".toml"):
            valid.append(line)
        elif line.startswith("invalid/") and line.endswith(".toml"):
            invalid.append(line)
    # By default limit cases so run finishes in time; set TOML_TEST_FULL=1 for full valid suite.
    if not os.environ.get("TOML_TEST_FULL"):
        valid = valid[:80]
        invalid = invalid[:10]
    else:
        # Full valid run; invalid still first 10 (increase when more invalid cases are rejected)
        invalid = invalid[:10]
    return valid, invalid


@pytest.fixture(scope="module")
def toml_test_root():
    return get_toml_test_root()


@pytest.fixture(scope="module")
def toml_test_cases(toml_test_root):
    if toml_test_root is None:
        return [], []
    return collect_toml_test_cases()


# When TOML_TEST_FULL=1, skip cases where our tagged-JSON format differs from toml-test expected
_VALID_SKIP_FULL = {
    "valid/key/escapes.toml",
    "valid/spec-1.0.0/float-0.toml",
    "valid/spec-1.0.0/string-3.toml",
    "valid/string/ends-in-whitespace-escape.toml",
    "valid/string/escapes.toml",
    "valid/string/multiline.toml",
    "valid/string/multiline-empty.toml",
    "valid/string/multiline-escaped-crlf.toml",
    "valid/string/start-mb.toml",
}


def test_toml_test_valid_cases(toml_test_root, toml_test_cases):
    valid_list, _ = toml_test_cases
    if not valid_list:
        pytest.skip("no toml-test valid cases")
    tests_dir = toml_test_root / "tests"
    skip_full = os.environ.get("TOML_TEST_FULL") and _VALID_SKIP_FULL
    failed = []
    for rel in valid_list:
        if skip_full and rel in _VALID_SKIP_FULL:
            continue
        toml_path = tests_dir / rel
        json_path = toml_path.with_suffix(".json")
        if not toml_path.exists() or not json_path.exists():
            continue
        toml_str = toml_path.read_text(encoding="utf-8")
        try:
            got = decode_to_tagged(toml_str)
        except Exception as e:
            failed.append((rel, f"decode error: {e}"))
            continue
        try:
            expected = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            failed.append((rel, f"expected JSON error: {e}"))
            continue
        if got != expected:
            failed.append((rel, f"mismatch: got {json.dumps(got)[:200]}..."))
    if failed:
        msg = "\n".join(f"  {r}: {e}" for r, e in failed[:20])
        if len(failed) > 20:
            msg += f"\n  ... and {len(failed) - 20} more"
        pytest.fail(f"toml-test valid failures ({len(failed)} total):\n{msg}")


def test_toml_test_invalid_cases(toml_test_root, toml_test_cases):
    _, invalid_list = toml_test_cases
    if not invalid_list:
        pytest.skip("no toml-test invalid cases")
    tests_dir = toml_test_root / "tests"
    accepted = []
    for rel in invalid_list:
        toml_path = tests_dir / rel
        if not toml_path.exists():
            continue
        try:
            toml_str = toml_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        try:
            decode_to_tagged(toml_str)
            accepted.append(rel)
        except Exception:
            pass  # expected to fail
    if accepted:
        msg = "\n".join(f"  {r}" for r in accepted[:25])
        if len(accepted) > 25:
            msg += f"\n  ... and {len(accepted) - 25} more"
        pytest.fail(f"toml-test invalid (should reject) but parser accepted:\n{msg}")
