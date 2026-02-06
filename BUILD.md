# Building FastTOML

## Prerequisites

- Python 3.10+
- CMake 3.15+
- C++17 compatible compiler (GCC 7+, Clang 5+, MSVC 2017+)
- pybind11

## Installation from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/fasttoml.git
cd fasttoml

# Install dependencies
pip install -r requirements-dev.txt

# Install in development mode
pip install -e .

# Or build wheel
python setup.py bdist_wheel
```

## Development Build

```bash
# Build extension in-place
python setup.py build_ext --inplace

# Run tests
pytest tests/ -v

# Run benchmarks
pytest tests/test_benchmark.py -v -s
```

## Building with CMake

```bash
mkdir build
cd build
cmake ..
make  # or cmake --build . on Windows
```

## SIMD Support

The parser automatically uses SIMD optimizations (AVX2/SSE4.2) if available.

To enable SIMD manually:
- GCC/Clang: `-mavx2 -msse4.2`
- MSVC: `/arch:AVX2`

The build system should detect and enable these automatically.
