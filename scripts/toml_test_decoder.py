#!/usr/bin/env python3
"""
toml-test decoder: read TOML from stdin, output tagged JSON to stdout.
Usage: toml-test test -decoder="python scripts/toml_test_decoder.py"
See https://github.com/toml-lang/toml-test
"""
import json
import math
import sys
from datetime import datetime, timezone

# Add project root for import
sys.path.insert(0, ".")
import fasttoml


def is_date_string(s):
    """Exactly YYYY-MM-DD for date-local; no trailing chars."""
    if not isinstance(s, str) or len(s) != 10:
        return False
    return (
        s[4] == "-" and s[7] == "-"
        and s[:4].isdigit() and s[5:7].isdigit() and s[8:10].isdigit()
    )


def is_time_string(s):
    if not isinstance(s, str) or len(s) < 8:
        return False
    if len(s) >= 8 and s[2] == ":" and s[5] == ":" and s[:2].isdigit() and s[3:5].isdigit() and s[6:8].isdigit():
        return True
    return False


def is_datetime_local_string(s):
    """String like 1979-05-27T07:32:00 or 1979-05-27 07:32:00 or with .frac, no Z or offset."""
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
        return s[i + 1 : i + 3].isdigit() and s[i + 4 : i + 6].isdigit() and i + 6 == len(s)
    return False


def _normalize_datetime_local(s):
    if len(s) >= 19 and s[10] == " ":
        return s[:10] + "T" + s[11:]
    return s


def to_tagged(obj):
    """Convert parsed TOML (fasttoml format) to toml-test tagged JSON."""
    if isinstance(obj, dict):
        return {k: to_tagged(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_tagged(x) for x in obj]
    if isinstance(obj, bool):
        return {"type": "bool", "value": "true" if obj else "false"}
    if isinstance(obj, int):
        return {"type": "integer", "value": str(obj)}
    if isinstance(obj, float):
        return {"type": "float", "value": _float_str(obj)}
    if isinstance(obj, datetime):
        return {"type": "datetime", "value": _datetime_rfc3339(obj)}
    if isinstance(obj, str):
        if is_datetime_offset_string(obj):
            val = obj.replace(" ", "T") if len(obj) > 19 and obj[10] == " " else obj
            return {"type": "datetime", "value": val}
        if is_datetime_local_string(obj):
            return {"type": "datetime-local", "value": _normalize_datetime_local(obj)}
        if is_date_string(obj) and not is_time_string(obj):
            return {"type": "date-local", "value": obj[:10]}
        if is_time_string(obj):
            return {"type": "time-local", "value": obj}
        return {"type": "string", "value": obj}
    return {"type": "string", "value": str(obj)}


def _float_str(x):
    if x == float("inf"):
        return "inf"
    if x == float("-inf"):
        return "-inf"
    if x != x:  # nan
        return "nan"
    if x == 0:
        return "-0" if math.copysign(1, x) < 0 else "0"
    if x == 9007199254740991.0 or x == -9007199254740991.0:
        return str(int(x))
    s = repr(x)
    if "e" in s or "E" in s:
        return format(x, ".1e").replace("e+", "e").replace("E+", "e").replace("E", "e")
    if abs(x) >= 1e10 or (0 < abs(x) < 1e-4):
        return format(x, ".1e").replace("e+", "e").replace("E+", "e").replace("E", "e")
    if x == int(x) and abs(x) in (6, 9):
        return str(int(x))
    if "." not in s:
        return s + ".0"
    return s


def _datetime_rfc3339(dt):
    """Format datetime for toml-test (RFC 3339, millisecond precision)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    s = dt.strftime("%Y-%m-%dT%H:%M:%S")
    if dt.microsecond:
        s += ".%03d" % (dt.microsecond // 1000)
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


def decode_to_tagged_json(toml_str: str):
    """Parse TOML string and return tagged JSON dict. Raises on invalid TOML."""
    data = fasttoml.loads(toml_str)
    return to_tagged(data)


def main():
    try:
        toml_str = sys.stdin.read()
        tagged = decode_to_tagged_json(toml_str)
        print(json.dumps(tagged, separators=(",", ":")))
        return 0
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
