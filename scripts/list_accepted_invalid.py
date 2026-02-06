"""List invalid toml-test cases that our parser currently accepts (should reject)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fasttoml

ROOT = Path(__file__).resolve().parents[1]
tests_dir = ROOT / ".toml-test" / "tests"
files_list = tests_dir / "files-toml-1.0.0"
if not files_list.exists():
    print("Run from project root with .toml-test cloned", file=sys.stderr)
    sys.exit(1)
lines = files_list.read_text(encoding="utf-8").strip().splitlines()
invalid = [l.strip() for l in lines if l.strip().startswith("invalid/") and l.strip().endswith(".toml")]

accepted = []
for rel in invalid:
    p = tests_dir / rel
    if not p.exists():
        continue
    try:
        s = p.read_text(encoding="utf-8", errors="replace")
        fasttoml.loads(s)
        accepted.append(rel)
    except Exception:
        pass

for a in sorted(accepted):
    print(a)
print(f"\n# Total: {len(accepted)} accepted of {len(invalid)} invalid", file=sys.stderr)
