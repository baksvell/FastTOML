"""Tests for fasttoml.dumps() and dump()."""

import io
import tempfile
from datetime import datetime, timezone

import pytest
import fasttoml


def test_dumps_empty():
    assert fasttoml.dumps({}) == ""


def test_dumps_simple():
    data = {"a": 1, "b": "hello", "c": True, "d": False}
    out = fasttoml.dumps(data)
    assert "a = 1" in out
    assert 'b = "hello"' in out
    assert "c = true" in out
    assert "d = false" in out
    assert fasttoml.loads(out) == data


def test_dumps_float_inf_nan():
    data = {"inf": float("inf"), "ninf": float("-inf"), "nan": float("nan")}
    out = fasttoml.dumps(data)
    assert "inf = inf" in out
    assert "ninf = -inf" in out
    assert "nan = nan" in out
    parsed = fasttoml.loads(out)
    assert parsed["inf"] == float("inf")
    assert parsed["ninf"] == float("-inf")
    assert parsed["nan"] != parsed["nan"]


def test_dumps_array():
    data = {"arr": [1, 2, "x"], "empty": []}
    out = fasttoml.dumps(data)
    assert "[1, 2, \"x\"]" in out or '2, "x"' in out
    assert fasttoml.loads(out) == data


def test_dumps_nested_table():
    data = {"root": "r", "section": {"a": 1, "b": "two"}}
    out = fasttoml.dumps(data)
    assert "root" in out and "section" in out
    assert "[section]" in out
    assert "a = 1" in out and "b = " in out
    assert fasttoml.loads(out) == data


def test_dumps_array_of_tables():
    data = {"items": [{"name": "a", "v": 1}, {"name": "b", "v": 2}]}
    out = fasttoml.dumps(data)
    assert "[[items]]" in out
    assert "name = \"a\"" in out and "name = \"b\"" in out
    assert fasttoml.loads(out) == data


def test_dumps_datetime():
    dt = datetime(2020, 1, 2, 12, 30, 45, 123000, tzinfo=timezone.utc)
    data = {"t": dt}
    out = fasttoml.dumps(data)
    assert "2020-01-02" in out and "12:30:45" in out
    assert "Z" in out or "+00:00" in out
    parsed = fasttoml.loads(out)
    assert parsed["t"].year == 2020 and parsed["t"].month == 1


def test_dumps_date_time_local_strings():
    data = {"d": "2020-01-15", "t": "08:05:30", "dt": "2020-01-15T08:05:30"}
    out = fasttoml.dumps(data)
    assert "2020-01-15" in out
    assert "08:05:30" in out
    assert "2020-01-15T08:05:30" in out
    assert fasttoml.loads(out) == data


def test_dumps_quoted_key():
    data = {"key with spaces": 1}
    out = fasttoml.dumps(data)
    assert '"key with spaces"' in out
    assert fasttoml.loads(out) == data


def test_dumps_inline_table_in_array():
    data = {"pairs": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}
    out = fasttoml.dumps(data)
    # Array of tables emitted as [[pairs]]
    assert "[[pairs]]" in out
    assert fasttoml.loads(out) == data


def test_round_trip_tables():
    toml_orig = """
[a]
x = 1

[b]
y = 2
"""
    data = fasttoml.loads(toml_orig)
    out = fasttoml.dumps(data)
    data2 = fasttoml.loads(out)
    assert data2 == data


def test_round_trip_array_of_tables():
    toml_orig = """
[[arr]]
k = 1
[[arr]]
k = 2
"""
    data = fasttoml.loads(toml_orig)
    out = fasttoml.dumps(data)
    data2 = fasttoml.loads(out)
    assert data2 == data


def test_dump_fp_string():
    data = {"a": 1}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        path = f.name
    try:
        fasttoml.dump(data, path)
        with open(path, encoding="utf-8") as f:
            assert f.read().strip() == "a = 1"
        assert fasttoml.load(path) == data
    finally:
        import os
        os.unlink(path)


def test_dump_fp_filelike():
    data = {"b": 2}
    buf = io.StringIO()
    fasttoml.dump(data, buf)
    assert buf.getvalue().strip() == "b = 2"
    buf.seek(0)
    assert fasttoml.loads(buf.read()) == data


def test_dumps_not_dict_raises():
    with pytest.raises(TypeError, match="dict"):
        fasttoml.dumps([1, 2, 3])
    with pytest.raises(TypeError, match="dict"):
        fasttoml.dumps("x")
