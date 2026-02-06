"""
Fast TOML parser for Python with SIMD optimizations.

This module provides a fast TOML parser implemented in C++ with SIMD optimizations.
It aims to be a drop-in replacement for existing TOML libraries with significantly
better performance.
"""

try:
    from ._native import loads as _loads
except ImportError as e:
    raise ImportError(
        "fasttoml native extension not found. "
        "Make sure the package is properly installed."
    ) from e

__version__ = "0.1.0"

from ._dumps import dumps, dump

__all__ = ["loads", "load", "dumps", "dump"]


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


def load(fp) -> dict:
    """
    Parse a TOML file and return a dictionary.
    
    Args:
        fp: File-like object or file path (string)
        
    Returns:
        dict: Parsed TOML data as a Python dictionary
        
    Raises:
        ValueError: If parsing fails
        FileNotFoundError: If file doesn't exist
        IOError: If file can't be read
        
    Example:
        >>> import fasttoml
        >>> with open('config.toml', 'r') as f:
        ...     data = fasttoml.load(f)
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
