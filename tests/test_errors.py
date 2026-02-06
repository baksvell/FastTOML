"""Tests for invalid TOML: parser must raise ValueError and not crash."""

import pytest
import fasttoml


@pytest.mark.parametrize("invalid_toml", [
    'key = "unclosed string',
    'key = "bad unicode \\u00"',
    'key = "bad unicode \\uXXXX"',
    'key = "invalid escape \\x41"',
    'key = "invalid escape \\z"',
    '[]',  # empty table name
    'key = ',
    '= 1',
    'key',
    '[[a',
    '[a',
    'key = 1 2',
    'key = {',
    'key = { a = 1',
    'key = [',
    'key = [1,',
])
def test_invalid_toml_raises(invalid_toml):
    """Invalid TOML must raise ValueError (no crash, no generic exception)."""
    with pytest.raises(ValueError) as exc_info:
        fasttoml.loads(invalid_toml)
    assert exc_info.value.args
    assert "error" in str(exc_info.value).lower() or "expected" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


def test_error_message_contains_context():
    """Error message should be informative (mention parse error)."""
    with pytest.raises(ValueError) as exc_info:
        fasttoml.loads('key = "no end')
    msg = str(exc_info.value)
    assert len(msg) > 10
    assert "TOML" in msg or "parse" in msg or "Expected" in msg or "unclosed" in msg.lower() or "error" in msg.lower()


def test_load_nonexistent_file_raises():
    """load() with nonexistent path must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        fasttoml.load("_nonexistent_file_12345.toml")


# Strict date/time validation: invalid values must raise ValueError
@pytest.mark.parametrize("invalid_toml,substring", [
    ("d = 1979-99-99", "month"),           # invalid month
    ("d = 1979-00-01", "month"),           # month 00
    ("d = 1979-02-30", "day"),             # Feb 30
    ("d = 1979-04-31", "day"),             # Apr 31
    ("d = 1979-01-01x", "unexpected"),     # trailing after date
    ("t = 12:00:00z", "unexpected"),       # trailing after time (z not offset here: no date)
    ("t = 25:00:00", None),                # hour 25 (invalid)
    ("t = 12:60:00", None),                # minute 60
])
def test_invalid_date_time_raises(invalid_toml, substring):
    """Strict date/time validation: invalid month, day, or trailing garbage raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        fasttoml.loads(invalid_toml)
    msg = str(exc_info.value).lower()
    if substring:
        assert substring.lower() in msg
