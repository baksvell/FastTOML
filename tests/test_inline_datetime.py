"""Tests for inline tables and date/time (p.2)."""

import pytest
from datetime import datetime, timezone

import fasttoml

# Expected Unix timestamp for 1979-05-27 07:32:00 UTC (for timezone-independent checks)
TS_1979_05_27_07_32_UTC = 296724720


# --- Inline tables ---

def test_inline_table_empty():
    toml_str = "a = {}"
    result = fasttoml.loads(toml_str)
    assert result == {"a": {}}


def test_inline_table_one_key():
    toml_str = 'point = { x = 1, y = 2 }'
    result = fasttoml.loads(toml_str)
    assert result == {"point": {"x": 1, "y": 2}}


def test_inline_table_nested():
    toml_str = 'a = { b = { c = 42 } }'
    result = fasttoml.loads(toml_str)
    assert result == {"a": {"b": {"c": 42}}}


def test_inline_table_with_strings():
    toml_str = 'user = { name = "Alice", active = true }'
    result = fasttoml.loads(toml_str)
    assert result == {"user": {"name": "Alice", "active": True}}


def test_inline_table_in_array():
    toml_str = "points = [ { x = 1, y = 2 }, { x = 3, y = 4 } ]"
    result = fasttoml.loads(toml_str)
    assert result == {"points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}


# --- Date / time ---

def test_local_date():
    toml_str = "d = 1979-05-27"
    result = fasttoml.loads(toml_str)
    assert result["d"] == "1979-05-27"


def test_local_time():
    toml_str = "t = 07:32:00"
    result = fasttoml.loads(toml_str)
    assert result["t"] == "07:32:00"


def test_offset_datetime_z():
    toml_str = "ts = 1979-05-27T07:32:00Z"
    result = fasttoml.loads(toml_str)
    assert isinstance(result["ts"], datetime)
    assert result["ts"].tzinfo is timezone.utc
    assert result["ts"].year == 1979 and result["ts"].month == 5 and result["ts"].day == 27
    assert result["ts"].hour == 7 and result["ts"].minute == 32 and result["ts"].second == 0


def test_offset_datetime_plus_offset():
    toml_str = "ts = 1979-05-27T00:32:00-07:00"
    result = fasttoml.loads(toml_str)
    assert isinstance(result["ts"], datetime)
    # Parser preserves original offset; local time is 00:32 in -07:00
    assert result["ts"].tzinfo is not None
    assert result["ts"].year == 1979 and result["ts"].month == 5 and result["ts"].day == 27
    assert result["ts"].hour == 0 and result["ts"].minute == 32
    # Same instant as 07:32 UTC
    utc = result["ts"].astimezone(timezone.utc)
    assert utc.hour == 7 and utc.minute == 32


def test_local_datetime():
    """Local datetime (no Z or offset) is returned as string for datetime-local in tagged JSON."""
    toml_str = "ts = 1979-05-27T07:32:00"
    result = fasttoml.loads(toml_str)
    assert result["ts"] == "1979-05-27T07:32:00"


def test_datetime_with_fraction():
    toml_str = "ts = 1979-05-27T00:32:00.999999Z"
    result = fasttoml.loads(toml_str)
    assert isinstance(result["ts"], datetime)
    assert result["ts"].microsecond == 999999


def test_full_example_with_inline_and_datetime():
    toml_str = """
[owner]
name = "Tom"
dob = 1979-05-27T07:32:00Z

[database]
conn = { host = "localhost", port = 5432 }
"""
    result = fasttoml.loads(toml_str)
    assert result["owner"]["name"] == "Tom"
    assert isinstance(result["owner"]["dob"], datetime)
    assert result["database"]["conn"] == {"host": "localhost", "port": 5432}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
