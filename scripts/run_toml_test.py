#!/usr/bin/env python3
"""
Run toml-test suite against FastTOML decoder.

Requires toml-test binary (Go):
  go install github.com/toml-lang/toml-test/v2/cmd/toml-test@latest

Then from project root:
  python scripts/run_toml_test.py
  # or
  toml-test test -decoder="python scripts/toml_test_decoder.py"
"""
import os
import subprocess
import sys


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(script_dir)
    os.chdir(root)
    decoder_cmd = f'python "{os.path.join(script_dir, "toml_test_decoder.py")}"'
    # Prefer decoder as module so path is correct
    decoder_cmd = f'{sys.executable} "{os.path.join(script_dir, "toml_test_decoder.py")}"'
    result = subprocess.run(
        ["toml-test", "test", "-decoder", decoder_cmd],
        cwd=root,
    )
    if result.returncode != 0:
        print("toml-test not found? Install with: go install github.com/toml-lang/toml-test/v2/cmd/toml-test@latest", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
