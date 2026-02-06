"""Basic tests for FastTOML parser."""

import pytest
import fasttoml


def test_loads_simple_string():
    """Test parsing a simple string value."""
    toml_str = 'key = "value"'
    result = fasttoml.loads(toml_str)
    assert result == {"key": "value"}


def test_loads_integer():
    """Test parsing integer values."""
    toml_str = 'number = 42'
    result = fasttoml.loads(toml_str)
    assert result == {"number": 42}


def test_loads_float():
    """Test parsing float values."""
    toml_str = 'pi = 3.14159'
    result = fasttoml.loads(toml_str)
    assert result == {"pi": 3.14159}


def test_loads_boolean():
    """Test parsing boolean values."""
    toml_str = 'flag = true'
    result = fasttoml.loads(toml_str)
    assert result == {"flag": True}


def test_loads_multiple_keys():
    """Test parsing multiple key-value pairs."""
    toml_str = '''
key1 = "value1"
key2 = 42
key3 = true
'''
    result = fasttoml.loads(toml_str)
    assert result == {
        "key1": "value1",
        "key2": 42,
        "key3": True
    }


def test_loads_array():
    """Test parsing array values."""
    toml_str = 'numbers = [1, 2, 3, 4, 5]'
    result = fasttoml.loads(toml_str)
    assert result == {"numbers": [1, 2, 3, 4, 5]}


def test_loads_mixed_array():
    """Test parsing mixed-type arrays."""
    toml_str = 'mixed = [1, "two", 3.0, true]'
    result = fasttoml.loads(toml_str)
    assert result == {"mixed": [1, "two", 3.0, True]}


def test_loads_literal_string():
    """Test parsing literal strings (no escape processing)."""
    # In TOML literal strings, backslashes are literal. So 'C:\Users\name' is C:\Users\name
    toml_str = "path = 'C:\\Users\\name'"
    result = fasttoml.loads(toml_str)
    assert result == {"path": "C:\\Users\\name"}


def test_loads_escaped_string():
    """Test parsing escaped strings."""
    toml_str = 'message = "Hello\\nWorld"'
    result = fasttoml.loads(toml_str)
    assert result == {"message": "Hello\nWorld"}


def test_loads_comments():
    """Test parsing files with comments."""
    toml_str = '''
# This is a comment
key = "value"  # Inline comment
# Another comment
'''
    result = fasttoml.loads(toml_str)
    assert result == {"key": "value"}


def test_loads_empty_string():
    """Test parsing empty TOML string."""
    result = fasttoml.loads("")
    assert result == {}


def test_loads_error():
    """Test error handling for invalid TOML."""
    with pytest.raises(ValueError):
        fasttoml.loads('invalid = "unclosed string')


if __name__ == "__main__":
    pytest.main([__file__])
