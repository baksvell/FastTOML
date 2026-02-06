"""Tests for TOML tables [section] and array of tables [[array]]."""

import pytest
import fasttoml


def test_simple_table():
    """Test single [table] section."""
    toml_str = """
[owner]
name = "Tom"
age = 42
"""
    result = fasttoml.loads(toml_str)
    assert result == {
        "owner": {
            "name": "Tom",
            "age": 42,
        }
    }


def test_multiple_tables():
    """Test multiple [table] sections."""
    toml_str = """
[database]
server = "localhost"
ports = [8001, 8002]

[servers]
ip = "10.0.0.1"
"""
    result = fasttoml.loads(toml_str)
    assert result == {
        "database": {
            "server": "localhost",
            "ports": [8001, 8002],
        },
        "servers": {
            "ip": "10.0.0.1",
        },
    }


def test_nested_table_dotted_header():
    """Test [a.b.c] creates nested tables."""
    toml_str = """
[a.b.c]
key = "value"
"""
    result = fasttoml.loads(toml_str)
    assert result == {
        "a": {
            "b": {
                "c": {
                    "key": "value",
                }
            }
        }
    }


def test_root_keys_then_table():
    """Test keys at root then [section]."""
    toml_str = """
title = "TOML Example"
[owner]
name = "Tom"
"""
    result = fasttoml.loads(toml_str)
    assert result == {
        "title": "TOML Example",
        "owner": {
            "name": "Tom",
        },
    }


def test_array_of_tables_single():
    """Test [[array]] creates list of one table."""
    toml_str = """
[[products]]
name = "Hammer"
price = 10
"""
    result = fasttoml.loads(toml_str)
    assert result == {
        "products": [
            {"name": "Hammer", "price": 10}
        ]
    }


def test_array_of_tables_multiple():
    """Test multiple [[array]] entries append to same array."""
    toml_str = """
[[products]]
name = "Hammer"
price = 10

[[products]]
name = "Nail"
price = 1
"""
    result = fasttoml.loads(toml_str)
    assert result == {
        "products": [
            {"name": "Hammer", "price": 10},
            {"name": "Nail", "price": 1},
        ]
    }


def test_array_of_tables_nested_path():
    """Test [[a.b]] with dotted path."""
    toml_str = """
[[a.b]]
x = 1

[[a.b]]
x = 2
"""
    result = fasttoml.loads(toml_str)
    assert result == {
        "a": {
            "b": [
                {"x": 1},
                {"x": 2},
            ]
        }
    }


def test_array_of_tables_then_subtable_header():
    """Test [[arr]] then [arr.subtab]: subtable applies to last array element (toml-test array-subtables)."""
    toml_str = """
[[arr]]
[arr.subtab]
val=1

[[arr]]
[arr.subtab]
val=2
"""
    result = fasttoml.loads(toml_str)
    assert result == {
        "arr": [
            {"subtab": {"val": 1}},
            {"subtab": {"val": 2}},
        ]
    }


def test_dotted_key_value():
    """Test dotted key in key-value: a.b.c = value."""
    toml_str = """
a.b.c = 42
"""
    result = fasttoml.loads(toml_str)
    assert result == {
        "a": {
            "b": {
                "c": 42,
            }
        }
    }


def test_dotted_key_and_table():
    """Test dotted key then [section] with same prefix."""
    toml_str = """
[dog.tater]
type = "pug"

[dog.tater.other]
name = "x"
"""
    result = fasttoml.loads(toml_str)
    assert result == {
        "dog": {
            "tater": {
                "type": "pug",
                "other": {
                    "name": "x",
                },
            }
        }
    }


def test_full_example():
    """Example from TOML spec (simplified)."""
    toml_str = """
title = "TOML Example"

[owner]
name = "Tom Preston-Werner"
age = 42

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
"""
    result = fasttoml.loads(toml_str)
    assert result["title"] == "TOML Example"
    assert result["owner"]["name"] == "Tom Preston-Werner"
    assert result["owner"]["age"] == 42
    assert result["database"]["server"] == "192.168.1.1"
    assert result["database"]["ports"] == [8001, 8001, 8002]
    assert result["database"]["enabled"] is True
    assert result["servers"] == [
        {"ip": "10.0.0.1", "dc": "eqdc10"},
        {"ip": "10.0.0.2", "dc": "eqdc10"},
    ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
