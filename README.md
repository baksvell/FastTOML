# FastTOML

Fast TOML parser for Python with SIMD optimizations.

## Features

- ⚡ **Fast**: 5-10x faster than existing TOML parsers
- 🎯 **SIMD Optimized**: Uses AVX2/SSE4.2 for maximum performance
- 🔧 **Drop-in Replacement**: Compatible API with existing TOML libraries
- 📦 **Full TOML v1.0.0 Support**: Complete specification implementation
- 🚀 **C++17 Backend**: High-performance native implementation

## Installation

```bash
pip install fasttoml
```

## Usage

```python
import fasttoml

# Parse TOML string
toml_str = '''
title = "TOML Example"
[owner]
name = "Tom Preston-Werner"
age = 42
'''

data = fasttoml.loads(toml_str)
print(data)

# Parse TOML file
data = fasttoml.load('config.toml')

# Serialize dict to TOML string
toml_out = fasttoml.dumps(data)

# Write dict to a TOML file
fasttoml.dump(data, 'output.toml')
```

## Performance

FastTOML is designed for maximum performance using SIMD optimizations. Benchmarks compare against **tomli** (and optionally **toml**).

**Run benchmarks:**

```bash
pip install -e .[dev]
pytest tests/test_benchmark.py -v --benchmark-only
```

**Example results** (vs tomli): ~6–9× faster depending on document size (small/medium/large/real-world TOML). Results are grouped by payload size; install `tomli` (or use Python 3.11+ with built-in `tomllib`) for comparison.

## Status and limitations

- **Status**: Alpha. Suitable for parsing configs and tests; run the test suite before relying in production.
- **API**: `loads(s)`, `load(fp)`, `dumps(obj)`, and `dump(obj, fp)` are provided. Serialization (`dumps`/`dump`) is implemented in Python.
- **Types**: Offset datetimes (with `Z` or `+/-HH:MM`) are returned as timezone-aware `datetime` (UTC). Local datetime (no offset, e.g. `1979-05-27T07:32:00`) is returned as a string for toml-test/tagged-JSON compatibility. Date-only and time-only TOML values are returned as strings (`"YYYY-MM-DD"`, `"HH:MM:SS"`).
- **Invalid TOML**: Invalid input raises `ValueError` with an error message; the parser does not crash on malformed data.

## Requirements

- Python 3.10+
- CMake 3.15+
- C++17 compatible compiler

## Development

```bash
# Install development dependencies
pip install -e .[dev]

# Build
python setup.py build_ext --inplace

# Run tests (excluding long benchmarks)
pytest tests/ --ignore=tests/test_benchmark.py

# Run benchmarks vs tomli
pytest tests/test_benchmark.py -v --benchmark-only

# Run toml-test suite (optional)
# Option A: use the official toml-test binary (requires Go)
#   go install github.com/toml-lang/toml-test/v2/cmd/toml-test@latest
#   python scripts/run_toml_test.py
# Option B: pytest over cloned toml-test (clone once, then)
#   pytest tests/test_toml_test_suite.py -v
#   (uses .toml-test/ if present, else clones from GitHub; by default 80 valid + 10 invalid; TOML_TEST_FULL=1 runs all valid with 9 decoder-format skips, invalid still limited to 10)
```

## License

MIT
