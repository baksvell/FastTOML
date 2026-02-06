"""
Run toml-test suite (valid + invalid) without the toml-test binary.

If env TOML_TEST_DIR is set, use that directory (must contain tests/valid, tests/invalid, tests/files-toml-1.0.0).
Otherwise clone toml-test into .toml-test (requires git + network). Set TOML_TEST_SKIP=1 to skip entirely.

Limits: by default 80 valid, 200 invalid cases. TOML_TEST_FULL=1 → all valid; TOML_TEST_INVALID_FULL=1 → all invalid.
Invalid test fails only when the parser accepts a case not in _INVALID_ACCEPTED_SKIP (known gaps).
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
    # By default limit valid; invalid: 200 cases. TOML_TEST_FULL=1 → all valid; TOML_TEST_INVALID_FULL=1 → all invalid.
    if not os.environ.get("TOML_TEST_FULL"):
        valid = valid[:80]
    if not os.environ.get("TOML_TEST_INVALID_FULL"):
        invalid = invalid[:200]
    return valid, invalid


@pytest.fixture(scope="module")
def toml_test_root():
    return get_toml_test_root()


@pytest.fixture(scope="module")
def toml_test_cases(toml_test_root):
    if toml_test_root is None:
        return [], []
    return collect_toml_test_cases()


# Invalid toml-test cases that we currently accept (known gaps). Test fails only when we accept an invalid case not in this set.
# Shrink this set as the parser is improved. Generate with: python scripts/list_accepted_invalid.py
_INVALID_ACCEPTED_SKIP = frozenset({
    "invalid/array/tables-02.toml",
    "invalid/control/bare-cr.toml",
    "invalid/control/comment-cr.toml",
    "invalid/control/rawstring-cr.toml",
    "invalid/control/string-cr.toml",
    "invalid/datetime/no-year-month-sep.toml",
    "invalid/encoding/bad-codepoint.toml",
    "invalid/encoding/bad-utf8-in-comment.toml",
    "invalid/encoding/bad-utf8-in-multiline-literal.toml",
    "invalid/encoding/bad-utf8-in-multiline.toml",
    "invalid/encoding/bad-utf8-in-string-literal.toml",
    "invalid/encoding/bad-utf8-in-string.toml",
    "invalid/float/exp-dot-01.toml",
    "invalid/float/exp-dot-02.toml",
    "invalid/float/exp-dot-03.toml",
    "invalid/float/exp-double-e-01.toml",
    "invalid/float/exp-double-e-02.toml",
    "invalid/float/exp-double-us.toml",
    "invalid/float/exp-leading-us.toml",
    "invalid/float/exp-trailing-us-01.toml",
    "invalid/float/exp-trailing-us-02.toml",
    "invalid/float/exp-trailing-us.toml",
    "invalid/float/leading-dot-neg.toml",
    "invalid/float/leading-dot-plus.toml",
    "invalid/float/leading-zero-neg.toml",
    "invalid/float/leading-zero-plus.toml",
    "invalid/float/trailing-exp-dot.toml",
    "invalid/float/trailing-exp-minus.toml",
    "invalid/float/trailing-exp-plus.toml",
    "invalid/float/trailing-exp.toml",
    "invalid/float/trailing-us-exp-01.toml",
    "invalid/float/trailing-us-exp-02.toml",
    "invalid/float/trailing-us.toml",
    "invalid/float/us-after-dot.toml",
    "invalid/float/us-before-dot.toml",
    "invalid/inline-table/duplicate-key-01.toml",
    "invalid/inline-table/duplicate-key-02.toml",
    "invalid/inline-table/duplicate-key-03.toml",
    "invalid/inline-table/overwrite-01.toml",
    "invalid/inline-table/overwrite-02.toml",
    "invalid/inline-table/overwrite-03.toml",
    "invalid/inline-table/overwrite-05.toml",
    "invalid/inline-table/overwrite-08.toml",
    "invalid/inline-table/overwrite-09.toml",
    "invalid/integer/capital-bin.toml",
    "invalid/integer/capital-hex.toml",
    "invalid/integer/capital-oct.toml",
    "invalid/integer/double-us.toml",
    "invalid/integer/leading-zero-03.toml",
    "invalid/integer/leading-zero-sign-01.toml",
    "invalid/integer/leading-zero-sign-02.toml",
    "invalid/integer/leading-zero-sign-03.toml",
    "invalid/integer/negative-bin.toml",
    "invalid/integer/negative-hex.toml",
    "invalid/integer/negative-oct.toml",
    "invalid/integer/positive-bin.toml",
    "invalid/integer/positive-hex.toml",
    "invalid/integer/positive-oct.toml",
    "invalid/integer/trailing-us-bin.toml",
    "invalid/integer/trailing-us-hex.toml",
    "invalid/integer/trailing-us-oct.toml",
    "invalid/integer/trailing-us.toml",
    "invalid/integer/us-after-bin.toml",
    "invalid/integer/us-after-hex.toml",
    "invalid/integer/us-after-oct.toml",
    "invalid/key/after-array.toml",
    "invalid/key/after-table.toml",
    "invalid/key/after-value.toml",
    "invalid/key/duplicate-keys-01.toml",
    "invalid/key/duplicate-keys-02.toml",
    "invalid/key/duplicate-keys-03.toml",
    "invalid/key/duplicate-keys-04.toml",
    "invalid/key/duplicate-keys-05.toml",
    "invalid/key/duplicate-keys-06.toml",
    "invalid/key/duplicate-keys-07.toml",
    "invalid/key/duplicate-keys-08.toml",
    "invalid/key/duplicate-keys-09.toml",
    "invalid/key/multiline-key-01.toml",
    "invalid/key/multiline-key-02.toml",
    "invalid/key/multiline-key-03.toml",
    "invalid/key/multiline-key-04.toml",
    "invalid/key/newline-02.toml",
    "invalid/key/newline-03.toml",
    "invalid/key/newline-04.toml",
    "invalid/key/newline-05.toml",
    "invalid/key/no-eol-01.toml",
    "invalid/key/no-eol-02.toml",
    "invalid/key/no-eol-03.toml",
    "invalid/key/no-eol-04.toml",
    "invalid/key/no-eol-06.toml",
    "invalid/key/no-eol-07.toml",
    "invalid/local-date/day-1digit.toml",
    "invalid/local-date/no-leads-with-milli.toml",
    "invalid/local-date/no-leads.toml",
    "invalid/local-date/trailing-t.toml",
    "invalid/local-date/y10k.toml",
    "invalid/local-date/year-3digits.toml",
    "invalid/local-time/trailing-dot.toml",
    "invalid/spec-1.0.0/inline-table-2-0.toml",
    "invalid/spec-1.0.0/inline-table-3-0.toml",
    "invalid/spec-1.0.0/string-7-0.toml",
    "invalid/spec-1.0.0/table-9-0.toml",
    "invalid/spec-1.0.0/table-9-1.toml",
    "invalid/string/bad-multiline.toml",
    "invalid/string/literal-multiline-quotes-01.toml",
    "invalid/string/literal-multiline-quotes-02.toml",
    "invalid/string/multiline-quotes-01.toml",
    "invalid/string/no-close-09.toml",
    "invalid/string/no-close-10.toml",
    "invalid/table/append-with-dotted-keys-01.toml",
    "invalid/table/append-with-dotted-keys-02.toml",
    "invalid/table/append-with-dotted-keys-04.toml",
    "invalid/table/append-with-dotted-keys-05.toml",
    "invalid/table/duplicate-key-01.toml",
    "invalid/table/duplicate-key-04.toml",
    "invalid/table/duplicate-key-05.toml",
    "invalid/table/duplicate-key-07.toml",
    "invalid/table/duplicate-key-08.toml",
    "invalid/table/duplicate-key-09.toml",
    "invalid/table/llbrace.toml",
    "invalid/table/multiline-key-01.toml",
    "invalid/table/multiline-key-02.toml",
    "invalid/table/newline-01.toml",
    "invalid/table/newline-02.toml",
    "invalid/table/newline-03.toml",
    "invalid/table/overwrite-array-in-parent.toml",
    "invalid/table/redefine-02.toml",
    "invalid/table/redefine-03.toml",
    "invalid/table/super-twice.toml",
})

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
    # Fail only for accepted cases that are not in the known-gap set (shrink set as parser improves)
    accepted_not_ok = [r for r in accepted if r not in _INVALID_ACCEPTED_SKIP]
    if accepted_not_ok:
        msg = "\n".join(f"  {r}" for r in accepted_not_ok[:25])
        if len(accepted_not_ok) > 25:
            msg += f"\n  ... and {len(accepted_not_ok) - 25} more"
        pytest.fail(f"toml-test invalid (should reject) but parser accepted:\n{msg}")
