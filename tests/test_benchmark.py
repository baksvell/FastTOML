"""
Benchmarks: FastTOML vs tomli (and toml if installed).

Run:
  pytest tests/test_benchmark.py -v --benchmark-only
  pytest tests/test_benchmark.py -v --benchmark-only --benchmark-autosave
  pytest tests/test_benchmark.py -v --benchmark-only -k "small"
"""

import pytest

import fasttoml
from tests.benchmark_data import TOML_SMALL, TOML_MEDIUM, TOML_LARGE, TOML_REALWORLD

try:
    import tomli
    HAS_TOMLI = True
except ImportError:
    try:
        import tomllib as tomli
        HAS_TOMLI = True
    except ImportError:
        HAS_TOMLI = False

try:
    import toml
    HAS_TOML = True
except ImportError:
    HAS_TOML = False


def _tomli_loads(s: str):
    if hasattr(tomli, "loads"):
        return tomli.loads(s)
    import io
    return tomli.load(io.BytesIO(s.encode("utf-8")))


# --- FastTOML ---

@pytest.mark.benchmark(group="small")
def test_bench_fasttoml_small(benchmark):
    """Parse small TOML (~200 bytes) with FastTOML."""
    result = benchmark(fasttoml.loads, TOML_SMALL)
    assert "title" in result


@pytest.mark.benchmark(group="medium")
def test_bench_fasttoml_medium(benchmark):
    """Parse medium TOML (~1.5 KB) with FastTOML."""
    result = benchmark(fasttoml.loads, TOML_MEDIUM)
    assert "owner" in result and "database" in result


@pytest.mark.benchmark(group="large")
def test_bench_fasttoml_large(benchmark):
    """Parse large TOML (~15 KB) with FastTOML."""
    result = benchmark(fasttoml.loads, TOML_LARGE)
    assert "title" in result


@pytest.mark.benchmark(group="realworld")
def test_bench_fasttoml_realworld(benchmark):
    """Parse real-world style TOML with FastTOML."""
    result = benchmark(fasttoml.loads, TOML_REALWORLD)
    assert "name" in result and "tool" in result


# --- tomli / tomllib ---

@pytest.mark.benchmark(group="small")
@pytest.mark.skipif(not HAS_TOMLI, reason="tomli/tomllib not installed")
def test_bench_tomli_small(benchmark):
    """Parse small TOML with tomli."""
    result = benchmark(_tomli_loads, TOML_SMALL)
    assert "title" in result


@pytest.mark.benchmark(group="medium")
@pytest.mark.skipif(not HAS_TOMLI, reason="tomli/tomllib not installed")
def test_bench_tomli_medium(benchmark):
    """Parse medium TOML with tomli."""
    result = benchmark(_tomli_loads, TOML_MEDIUM)
    assert "owner" in result


@pytest.mark.benchmark(group="large")
@pytest.mark.skipif(not HAS_TOMLI, reason="tomli/tomllib not installed")
def test_bench_tomli_large(benchmark):
    """Parse large TOML with tomli."""
    result = benchmark(_tomli_loads, TOML_LARGE)
    assert "title" in result


@pytest.mark.benchmark(group="realworld")
@pytest.mark.skipif(not HAS_TOMLI, reason="tomli/tomllib not installed")
def test_bench_tomli_realworld(benchmark):
    """Parse real-world TOML with tomli."""
    result = benchmark(_tomli_loads, TOML_REALWORLD)
    assert "name" in result


# --- toml (optional) ---

@pytest.mark.benchmark(group="small")
@pytest.mark.skipif(not HAS_TOML, reason="toml package not installed")
def test_bench_toml_small(benchmark):
    """Parse small TOML with toml."""
    result = benchmark(toml.loads, TOML_SMALL)
    assert "title" in result


@pytest.mark.benchmark(group="medium")
@pytest.mark.skipif(not HAS_TOML, reason="toml package not installed")
def test_bench_toml_medium(benchmark):
    """Parse medium TOML with toml."""
    result = benchmark(toml.loads, TOML_MEDIUM)
    assert "owner" in result


@pytest.mark.benchmark(group="large")
@pytest.mark.skipif(not HAS_TOML, reason="toml package not installed")
def test_bench_toml_large(benchmark):
    """Parse large TOML with toml."""
    result = benchmark(toml.loads, TOML_LARGE)
    assert "title" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
