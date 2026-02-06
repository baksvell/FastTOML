"""TOML samples for benchmarking (small / medium / large)."""

# Small: ~200 bytes
TOML_SMALL = """
title = "App"
version = "1.0"
[server]
host = "localhost"
port = 8080
"""

# Medium: ~1.5 KB (spec-style example)
TOML_MEDIUM = '''
title = "TOML Example"

[owner]
name = "Tom Preston-Werner"
dob = 1979-05-27T07:32:00Z

[database]
server = "192.168.1.1"
ports = [8001, 8001, 8002]
connection_max = 5000
enabled = true

[servers.alpha]
ip = "10.0.0.1"
dc = "eqdc10"

[servers.beta]
ip = "10.0.0.2"
dc = "eqdc10"

[[products]]
name = "Hammer"
price = 10

[[products]]
name = "Nail"
price = 1
'''

# Large: repeat medium content to get ~15 KB
TOML_LARGE = (
    "# config\n" + TOML_MEDIUM.strip() + "\n\n"
    + "\n".join(
        f"[section_{i}]\nfoo = {i}\nbar = \"value_{i}\""
        for i in range(80)
    )
)

# Real-world style: mixed keys, strings, arrays, tables
TOML_REALWORLD = '''
name = "myapp"
version = "0.1.0"
description = "An app"
authors = ["Alice <a@x.com>", "Bob <b@x.com>"]
keywords = ["toml", "config"]
requires-python = ">=3.10"
dependencies = ["fasttoml>=0.1", "pytest>=7"]

[project.optional-dependencies]
dev = ["pytest-benchmark", "tomli>=2.0"]

[project.urls]
Homepage = "https://example.com"
Repository = "https://github.com/example/repo"

[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v"

[tool.coverage.run]
source = ["src"]
branch = true

[tool.coverage.report]
exclude_lines = ["pragma: no cover", "def __repr__"]
'''
