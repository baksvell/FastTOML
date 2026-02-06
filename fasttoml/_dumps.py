"""
Serialize Python dict (loads() output) to TOML string.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


def _is_bare_key(s: str) -> bool:
    return bool(s) and re.match(r"^[A-Za-z0-9_-]+$", s)


def _escape_string(s: str) -> str:
    out = []
    for c in s:
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif c == "\n":
            out.append("\\n")
        elif c == "\r":
            out.append("\\r")
        elif c == "\t":
            out.append("\\t")
        elif ord(c) < 0x20:
            out.append(f"\\u{(ord(c)):04x}")
        else:
            out.append(c)
    return "".join(out)


def _format_key(key: str) -> str:
    if _is_bare_key(key):
        return key
    return '"' + _escape_string(key) + '"'


def _is_date_string(s: str) -> bool:
    if not isinstance(s, str) or len(s) != 10:
        return False
    return (
        s[4] == "-"
        and s[7] == "-"
        and s[:4].isdigit()
        and s[5:7].isdigit()
        and s[8:10].isdigit()
    )


def _is_time_string(s: str) -> bool:
    if not isinstance(s, str) or len(s) < 8:
        return False
    return (
        s[2] == ":"
        and s[5] == ":"
        and s[:2].isdigit()
        and s[3:5].isdigit()
        and s[6:8].isdigit()
        and (len(s) == 8 or (len(s) > 8 and s[8] == "." and s[9:].replace(".", "").isdigit()))
    )


def _is_datetime_local_string(s: str) -> bool:
    if not isinstance(s, str) or len(s) < 19:
        return False
    if s[4] != "-" or s[7] != "-" or s[10] not in "Tt " or s[13] != ":" or s[16] != ":":
        return False
    if not (
        s[:4].isdigit()
        and s[5:7].isdigit()
        and s[8:10].isdigit()
        and s[11:13].isdigit()
        and s[14:16].isdigit()
        and s[17:19].isdigit()
    ):
        return False
    if len(s) == 19:
        return True
    if len(s) > 19 and s[19] == "." and all(c.isdigit() or c == "." for c in s[20:]):
        return True
    return False


def _format_scalar(value: Any) -> str:
    if value is None:
        raise TypeError("None is not a valid TOML value")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:
            return "nan"
        if value == float("inf"):
            return "inf"
        if value == float("-inf"):
            return "-inf"
        s = repr(value)
        if s == "-0.0":
            return "-0.0"
        return s
    if isinstance(value, datetime):
        # RFC 3339 with Z or ±HH:MM
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        s = value.strftime("%Y-%m-%dT%H:%M:%S")
        if value.microsecond:
            s += f".{value.microsecond:06d}".rstrip("0").rstrip(".")
        offset = value.utcoffset()
        if offset is not None:
            total = int(offset.total_seconds())
            if total == 0:
                s += "Z"
            else:
                sign = "+" if total >= 0 else "-"
                h, r = divmod(abs(total), 3600)
                m = r // 60
                s += f"{sign}{h:02d}:{m:02d}"
        return s
    if isinstance(value, str):
        if _is_date_string(value) and not _is_time_string(value):
            return value[:10]
        if _is_time_string(value) and not _is_datetime_local_string(value):
            return value
        if _is_datetime_local_string(value):
            return value.replace(" ", "T")
        return '"' + _escape_string(value) + '"'
    raise TypeError(f"Unsupported type for TOML: {type(value).__name__}")


def _is_table_array(value: list) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(isinstance(x, dict) for x in value)


def _format_value(value: Any, inline: bool = False) -> str:
    """Format a single value. inline=True for inline tables/arrays only."""
    if isinstance(value, dict):
        if inline:
            pairs = ",".join(f"{_format_key(k)} = {_format_value(v, inline=True)}" for k, v in value.items())
            return "{" + pairs + "}"
        raise TypeError("Nested dict must be emitted as [section], not inline (use serialize_table)")
    if isinstance(value, list):
        if _is_table_array(value):
            raise TypeError("List of tables must be emitted as [[section]]")
        return "[" + ", ".join(_format_value(item, inline=True) for item in value) + "]"
    return _format_scalar(value)


def _serialize_table_body(table: dict, path_prefix: str) -> list[str]:
    lines = []
    scalars = []
    tables = []
    array_tables = []
    for k, v in sorted(table.items()):
        if isinstance(v, dict):
            tables.append((k, v))
        elif _is_table_array(v):
            array_tables.append((k, v))
        else:
            scalars.append((k, v))
    for k, v in scalars:
        lines.append(f"{_format_key(k)} = {_format_value(v, inline=True)}")
    for k, v in tables:
        path = f"{path_prefix}.{k}" if path_prefix else k
        lines.append(f"[{path}]")
        lines.extend(_serialize_table_body(v, path))
    for k, v in array_tables:
        path = f"{path_prefix}.{k}" if path_prefix else k
        for item in v:
            lines.append(f"[[{path}]]")
            lines.extend(_serialize_table_body(item, path))
    return lines


def dumps(obj: dict) -> str:
    """
    Serialize a Python dict to a TOML string.

    The dict should have the same structure as returned by loads():
    str, int, float, bool, datetime, list, dict. Strings that match
    date (YYYY-MM-DD), time (HH:MM:SS), or datetime-local are emitted
    as TOML date/time/datetime literals.

    Args:
        obj: Root table (dict) to serialize.

    Returns:
        TOML string.

    Raises:
        TypeError: If obj is not a dict or contains unsupported types.
    """
    if not isinstance(obj, dict):
        raise TypeError("dumps() requires a dict")
    return "\n".join(_serialize_table_body(obj, ""))


def dump(obj: dict, fp, *, encoding: str = "utf-8") -> None:
    """
    Serialize a Python dict to TOML and write to a file-like object.

    Args:
        obj: Root table (dict) to serialize.
        fp: File-like object (with .write()) or file path (str).
        encoding: Used when fp is a file path. Default "utf-8".
    """
    s = dumps(obj)
    if isinstance(fp, str):
        with open(fp, "w", encoding=encoding) as f:
            f.write(s)
    else:
        fp.write(s)
