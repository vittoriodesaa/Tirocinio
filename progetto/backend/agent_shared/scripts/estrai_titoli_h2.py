#!/usr/bin/env python3
"""Prime 40 righe ## del markdown principale in sources (per outline rapido)."""
import os
import re
import sys
from pathlib import Path

root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
src = root / "sources"
mds = sorted(src.glob("*.md")) if src.is_dir() else []
if not mds:
    print("Nessun .md in sources/", file=sys.stderr)
    raise SystemExit(1)
# preferisci file senza _raw/_clean nel nome se possibile
main = next((p for p in mds if "_raw" not in p.name and "_clean" not in p.name), mds[0])
print("FILE:", main.relative_to(root))
count = 0
for i, line in enumerate(main.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
    if re.match(r"^##\s+\S", line):
        print(f"{i:6d}| {line.strip()[:100]}")
        count += 1
        if count >= 40:
            break
