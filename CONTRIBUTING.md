# Contributing to FastTOML

Thanks for your interest in improving FastTOML.

## Development setup

1. Clone the repository and enter the directory:
   ```bash
   git clone https://github.com/baksvell/FastTOML.git
   cd FastTOML
   ```

2. Create a virtual environment and install in editable mode with dev dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   # or:  .venv\Scripts\activate  # Windows
   pip install -e ".[dev]"
   ```

3. Build the C++ extension:
   ```bash
   python setup.py build_ext --inplace
   ```

## Running tests

- All tests (except benchmarks):
  ```bash
  pytest tests/ -v --ignore=tests/test_benchmark.py
  ```
- Benchmarks (vs tomli):
  ```bash
  pytest tests/test_benchmark.py -v --benchmark-only
  ```
- toml-test suite (optional; requires `.toml-test` clone or `TOML_TEST_DIR`):
  ```bash
  pytest tests/test_toml_test_suite.py -v
  ```

## Code style

- Python: follow PEP 8. Use type hints for public API.
- C++: C++17, match existing style in `src/` and `include/`.

## Submitting changes

1. Open an issue or pick an existing one to discuss the change.
2. Fork the repo, create a branch, make your changes.
3. Ensure tests pass and add tests for new behavior.
4. Open a pull request with a clear description and reference to the issue.

## Release checklist (maintainers)

- Bump version in `pyproject.toml`.
- Update `CHANGELOG.md`.
- Run full test suite and toml-test (e.g. `TOML_TEST_FULL=1 TOML_TEST_INVALID_FULL=1`).
- Tag and push; optionally build wheels with cibuildwheel and publish to PyPI.
