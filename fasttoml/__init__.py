"""
Fast TOML parser for Python with SIMD optimizations.

This module provides a fast TOML parser implemented in C++ with SIMD optimizations.
It aims to be a drop-in replacement for existing TOML libraries with significantly
better performance.
"""
from __future__ import annotations

import re
from typing import BinaryIO, TextIO, Union

try:
    from ._native import loads as _loads
except ImportError as e:
    raise ImportError(
        "fasttoml native extension not found. "
        "Make sure the package is properly installed."
    ) from e

def _get_version() -> str:
    try:
        from importlib.metadata import version
        return version("fasttoml")
    except Exception:
        pass
    try:
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        if path.exists():
            m = re.search(r'version\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"))
            return m.group(1) if m else "0.0.0"
    except Exception:
        pass
    return "0.0.0"

__version__ = _get_version()

from ._dumps import dumps, dump

__all__ = ["loads", "load", "dumps", "dump", "__version__"]


def loads(s: str) -> dict:
    """
    Parse a TOML string and return a dictionary.
    
    Args:
        s: The TOML string to parse
        
    Returns:
        dict: Parsed TOML data as a Python dictionary
        
    Raises:
        ValueError: If parsing fails
        
    Example:
        >>> import fasttoml
        >>> toml_str = 'key = "value"'
        >>> data = fasttoml.loads(toml_str)
        >>> print(data)
        {'key': 'value'}
    """
    try:
        return _loads(s)
    except RuntimeError as e:
        raise ValueError(str(e)) from e


def load(fp: Union[str, BinaryIO, TextIO]) -> dict:
    """
    Parse a TOML file and return a dictionary.

    Args:
        fp: File path (str) or file-like object open for reading (text or binary).

    Returns:
        Parsed TOML data as a Python dictionary.

    Raises:
        ValueError: If the content is not valid TOML.
        FileNotFoundError: If fp is a path and the file does not exist.
        OSError: If the file cannot be read.
    """
    if isinstance(fp, str):
        # File path provided
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
        return loads(content)
    else:
        # File-like object
        content = fp.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        return loads(content)
