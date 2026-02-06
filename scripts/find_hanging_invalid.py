#!/usr/bin/env python3
"""Find which invalid toml-test file causes the parser to hang. Run from project root."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOML_TEST = ROOT / ".toml-test" / "tests"
FILES_LIST = TOML_TEST / "files-toml-1.0.0"
TIMEOUT_PER_FILE = 3  # seconds


def main():
    if not FILES_LIST.exists():
        print("Run from project root; .toml-test/tests/files-toml-1.0.0 must exist", file=sys.stderr)
        return 1
    lines = FILES_LIST.read_text(encoding="utf-8").strip().splitlines()
    invalid = [ln.strip() for ln in lines if ln.strip().startswith("invalid/") and ln.strip().endswith(".toml")]
    # Check first N to find first hang quickly
    if len(sys.argv) > 1:
        invalid = invalid[: int(sys.argv[1])]
    print(f"Checking {len(invalid)} invalid files (timeout {TIMEOUT_PER_FILE}s each)...")
    hanging = []
    for i, rel in enumerate(invalid):
        path = TOML_TEST / rel
        if not path.exists():
            continue
        try:
            toml_str = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            hanging.append((rel, str(e), None))
            continue
        code = f"""
import sys
sys.path.insert(0, {repr(str(ROOT))})
import fasttoml
try:
    fasttoml.loads({repr(toml_str)})
    sys.exit(0)
except Exception:
    sys.exit(1)
"""
        try:
            r = subprocess.run(
                [sys.executable, "-c", code],
                cwd=str(ROOT),
                timeout=TIMEOUT_PER_FILE,
                capture_output=True,
            )
            if r.returncode not in (0, 1):
                hanging.append((rel, "exit", r.returncode))
        except subprocess.TimeoutExpired:
            hanging.append((rel, "timeout", None))
        if (i + 1) % 50 == 0:
            print(f"  checked {i + 1}/{len(invalid)} ...")
    if hanging:
        print("\nHanging or suspicious files:")
        for rel, kind, code in hanging:
            print(f"  {rel} ({kind}" + (f", code={code}" if code is not None else "") + ")")
        return 1
    print("No hanging files found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
