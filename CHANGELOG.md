# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0b3] - 2025-02-06

### Added

- Strict date/time validation: month 01–12, day in range (incl. leap year), hour/minute/second; reject trailing garbage after date/time.
- Full TOML 1.0 basic string escapes: `\b`, `\f`; invalid escapes (e.g. `\x`) raise `ValueError`.
- Expanded invalid toml-test: 200 cases by default, all 473 with `TOML_TEST_INVALID_FULL=1`; known-accepted skip set.
- `__version__` from package metadata or pyproject.toml; type hints for `load(fp)`.
- CONTRIBUTING.md; wheels workflow (cibuildwheel) for multi-platform builds.

### Changed

- README: Contributing section, doc/links for toml-test and wheels.

## [0.2.0b2] - 2025-02-06

### Changed

- README long description now correctly displayed on PyPI (explicit `content-type` for Markdown).
- Setuptools build requirement raised to >=77 for modern license and readme handling.

### Fixed

- MANIFEST.in added so C++ headers (`include/`) are included in sdist; fixes wheel build from sdist (e.g. `python -m build`).

## [0.2.0b1] - 2025-02-06

### Added

- Initial beta release on PyPI.
- `loads(s)`, `load(fp)`, `dumps(obj)`, `dump(obj, fp)` API.
- C++17 parser with SIMD (AVX2/SSE4.2 on x86).
- Python serialization (`dumps`/`dump`) for TOML output.
- toml-test suite integration (valid tests with known skips; subset of invalid tests).
- Validation improvements: integer (leading zero), float (double-dot, leading/trailing dot), datetime (offset, day-in-month, trailing dot).
- CI on GitHub Actions (Windows, Linux, macOS; Python 3.10–3.12).

[Unreleased]: https://github.com/baksvell/FastTOML/compare/v0.2.0b3...HEAD
[0.2.0b3]: https://github.com/baksvell/FastTOML/compare/v0.2.0b2...v0.2.0b3
[0.2.0b2]: https://github.com/baksvell/FastTOML/compare/v0.2.0b1...v0.2.0b2
[0.2.0b1]: https://github.com/baksvell/FastTOML/releases/tag/v0.2.0b1
