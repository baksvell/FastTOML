"""
Compatibility tests: compare FastTOML output with tomli on the same TOML.

Run with: pytest tests/test_compatibility.py -v
Requires: pip install tomli (or tomli-w; on Python 3.11+ tomllib is stdlib).
"""

from datetime import date, time, datetime, timezone
import pytest

import fasttoml

try:
    import tomli
    HAS_TOMLI = True
except ImportError:
    try:
        import tomllib as tomli  # Python 3.11+
        HAS_TOMLI = True
    except ImportError:
        HAS_TOMLI = False


def _looks_like_date(s):
    if not isinstance(s, str) or len(s) < 10:
        return False
    return (
        s[4] == "-" and s[7] == "-"
        and s[:4].isdigit() and s[5:7].isdigit() and s[8:10].isdigit()
    )


def _looks_like_time(s):
    if not isinstance(s, str) or len(s) < 8:
        return False
    return (
        s[2] == ":" and s[5] == ":"
        and s[:2].isdigit() and s[3:5].isdigit() and s[6:8].isdigit()
    )


def _normalize_for_compare(obj):
    """
    Normalize a parsed TOML value so fasttoml and tomli results can be compared.
    - dict/list: recurse
    - datetime: ("datetime", ts, has_tz)
    - date / date-like string: ("date", "YYYY-MM-DD")
    - time / time-like string: ("time", "HH:MM:SS...")
    - rest: identity
    """
    if isinstance(obj, dict):
        return {k: _normalize_for_compare(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_for_compare(x) for x in obj]
    if isinstance(obj, datetime):
        ts = obj.timestamp()
        tz = obj.tzinfo is not None
        return ("datetime", ts, tz)
    if isinstance(obj, date) and not isinstance(obj, datetime):
        return ("date", obj.isoformat())
    if isinstance(obj, time):
        return ("time", obj.isoformat())
    if _looks_like_date(obj):
        return ("date", obj[:10] if len(obj) >= 10 else obj)
    if _looks_like_time(obj):
        return ("time", obj)
    return obj


def _assert_equal_normalized(a, b, path="root"):
    """Recursively assert normalized structures are equal."""
    if type(a) != type(b):
        raise AssertionError(f"At {path}: type mismatch {type(a).__name__} vs {type(b).__name__}")
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            raise AssertionError(f"At {path}: keys differ {set(a.keys())} vs {set(b.keys())}")
        for k in a:
            _assert_equal_normalized(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        if len(a) != len(b):
            raise AssertionError(f"At {path}: list length {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            _assert_equal_normalized(x, y, f"{path}[{i}]")
    elif isinstance(a, tuple) and len(a) >= 2 and a[0] in ("datetime", "date", "time"):
        if a[0] != b[0]:
            raise AssertionError(f"At {path}: temporal type {a[0]} vs {b[0]}")
        if a[0] == "datetime":
            if abs(a[1] - b[1]) > 1e-6:
                raise AssertionError(f"At {path}: timestamp {a[1]} vs {b[1]}")
        else:
            if a[1] != b[1]:
                raise AssertionError(f"At {path}: value {a[1]} vs {b[1]}")
    else:
        if a != b:
            raise AssertionError(f"At {path}: {a!r} != {b!r}")


def _parse_tomli(s: str):
    """Parse with tomli. tomli.loads wants bytes in 3.11 tomllib."""
    if hasattr(tomli, "loads"):
        return tomli.loads(s)
    # tomllib (3.11+) only has load(fp)
    import io
    return tomli.load(io.BytesIO(s.encode("utf-8")))


@pytest.mark.skipif(not HAS_TOMLI, reason="tomli/tomllib not installed")
class TestCompatibilityWithTomli:
    """Parse same TOML with fasttoml and tomli, compare normalized results."""

    def test_simple_key_values(self):
        toml_str = '''
name = "test"
count = 42
ratio = 3.14
flag = true
'''
        a = _normalize_for_compare(fasttoml.loads(toml_str))
        b = _normalize_for_compare(_parse_tomli(toml_str))
        _assert_equal_normalized(a, b)

    def test_arrays(self):
        toml_str = '''
ints = [1, 2, 3]
mixed = [1, "a", true, 2.5]
nested = [[1, 2], [3, 4]]
'''
        a = _normalize_for_compare(fasttoml.loads(toml_str))
        b = _normalize_for_compare(_parse_tomli(toml_str))
        _assert_equal_normalized(a, b)

    def test_tables(self):
        toml_str = '''
[table]
a = 1
b = "two"

[table.nested]
x = 10
'''
        a = _normalize_for_compare(fasttoml.loads(toml_str))
        b = _normalize_for_compare(_parse_tomli(toml_str))
        _assert_equal_normalized(a, b)

    def test_array_of_tables(self):
        toml_str = '''
[[items]]
id = 1
name = "first"

[[items]]
id = 2
name = "second"
'''
        a = _normalize_for_compare(fasttoml.loads(toml_str))
        b = _normalize_for_compare(_parse_tomli(toml_str))
        _assert_equal_normalized(a, b)

    def test_inline_table(self):
        toml_str = 'point = { x = 1, y = 2 }\nline = { start = { x = 0 }, end = { x = 1 } }'
        a = _normalize_for_compare(fasttoml.loads(toml_str))
        b = _normalize_for_compare(_parse_tomli(toml_str))
        _assert_equal_normalized(a, b)

    def test_datetime_offset(self):
        toml_str = 'ts = 1979-05-27T07:32:00Z'
        a = _normalize_for_compare(fasttoml.loads(toml_str))
        b = _normalize_for_compare(_parse_tomli(toml_str))
        _assert_equal_normalized(a, b)

    def test_datetime_with_offset(self):
        toml_str = 'ts = 1979-05-27T00:32:00-07:00'
        a = _normalize_for_compare(fasttoml.loads(toml_str))
        b = _normalize_for_compare(_parse_tomli(toml_str))
        _assert_equal_normalized(a, b)

    def test_local_date_and_time_as_string(self):
        # FastTOML returns date/time as string; tomli returns date/time objects.
        # Normalizer converts both to ("date", "YYYY-MM-DD") and ("time", "HH:MM:SS").
        toml_str = 'd = 1979-05-27\nt = 07:32:00'
        a = _normalize_for_compare(fasttoml.loads(toml_str))
        b = _normalize_for_compare(_parse_tomli(toml_str))
        _assert_equal_normalized(a, b)

    def test_multiline_and_unicode(self):
        toml_str = '''
text = """
hello
world"""
unicode = "\\u00E9"
emoji = "\\U0001F600"
'''
        a = _normalize_for_compare(fasttoml.loads(toml_str))
        b = _normalize_for_compare(_parse_tomli(toml_str))
        _assert_equal_normalized(a, b)

    def test_full_spec_example(self):
        toml_str = '''
# TOML spec–style example
title = "TOML Example"
[owner]
name = "Tom Preston-Werner"
dob = 1979-05-27T07:32:00Z

[database]
server = "192.168.1.1"
ports = [8001, 8001, 8002]
enabled = true

[[servers]]
ip = "10.0.0.1"
dc = "eqdc10"

[[servers]]
ip = "10.0.0.2"
dc = "eqdc10"
'''
        a = _normalize_for_compare(fasttoml.loads(toml_str))
        b = _normalize_for_compare(_parse_tomli(toml_str))
        _assert_equal_normalized(a, b)


def test_tomli_available_or_skipped():
    """If tomli is not installed, compatibility tests are skipped (no failure)."""
    if not HAS_TOMLI:
        pytest.skip("tomli/tomllib not installed; install tomli for compatibility tests")
