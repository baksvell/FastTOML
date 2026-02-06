"""Tests for multiline strings and Unicode escapes (p.3)."""

import pytest
import fasttoml


# --- Multiline basic string """ ---

def test_multiline_basic_simple():
    toml_str = '''key = """
hello
world"""'''
    result = fasttoml.loads(toml_str)
    assert result["key"] == "hello\nworld"


def test_multiline_basic_first_newline_trimmed():
    toml_str = '''key = """
first line"""'''
    result = fasttoml.loads(toml_str)
    assert result["key"] == "first line"


def test_multiline_basic_with_escapes():
    toml_str = '''key = """
line1
\\tline2\\n"""'''
    result = fasttoml.loads(toml_str)
    assert result["key"] == "line1\n\tline2\n"


def test_multiline_basic_quotes_inside():
    toml_str = '''key = """
Say \\"hello\\" """'''
    result = fasttoml.loads(toml_str)
    assert "hello" in result["key"]


# --- Multiline literal string ''' ---

def test_multiline_literal_simple():
    toml_str = """key = '''
hello
world'''"""
    result = fasttoml.loads(toml_str)
    assert result["key"] == "hello\nworld"


def test_multiline_literal_no_escape():
    toml_str = """key = '''
C:\\\\path\\\\to\\\\file'''"""
    result = fasttoml.loads(toml_str)
    assert result["key"] == "C:\\\\path\\\\to\\\\file"


def test_multiline_literal_first_newline_trimmed():
    toml_str = """key = '''
first line'''"""
    result = fasttoml.loads(toml_str)
    assert result["key"] == "first line"


# --- Allowed escape sequences in basic string (TOML 1.0: \b \t \n \f \r \" \\ \uXXXX \UXXXXXXXX) ---

def test_basic_string_backspace_and_form_feed():
    """\\b and \\f are valid escapes in basic strings."""
    assert fasttoml.loads('k = "a\\bb"')["k"] == "a\bb"
    assert fasttoml.loads('k = "a\\fc"')["k"] == "a\fc"


# --- Unicode escapes in basic string ---

def test_unicode_escape_4digit():
    toml_str = 'key = "\\u00E9"'
    result = fasttoml.loads(toml_str)
    assert result["key"] == "\u00e9"


def test_unicode_escape_8digit():
    toml_str = 'key = "\\U0001F600"'
    result = fasttoml.loads(toml_str)
    assert result["key"] == "\U0001F600"


def test_unicode_escape_in_text():
    toml_str = 'key = "Hello \\u00E0 tous"'
    result = fasttoml.loads(toml_str)
    assert result["key"] == "Hello \u00e0 tous"


def test_unicode_escape_ascii():
    toml_str = 'key = "\\u0041\\u0042"'
    result = fasttoml.loads(toml_str)
    assert result["key"] == "AB"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
