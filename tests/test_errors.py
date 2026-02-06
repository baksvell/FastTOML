"""Tests for invalid TOML: parser must raise ValueError and not crash."""

import pytest
import fasttoml


@pytest.mark.parametrize("invalid_toml", [
    'key = "unclosed string',
    'key = "bad unicode \\u00"',
    'key = "bad unicode \\uXXXX"',
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
