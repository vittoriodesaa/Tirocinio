#!/usr/bin/env python3
"""Cerca pattern nei .md di sources. Uso: grep_sources.py <pattern> [sottostringa file]"""
import os
import re
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Uso: grep_sources.py <pattern> [nome_file_contiene]", file=sys.stderr)
    raise SystemExit(2)

pattern, *rest = sys.argv[1:]
file_hint = rest[0].lower() if rest else ""
root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
src = root / "sources"
rx = re.compile(pattern, re.IGNORECASE)
hits = 0
for path in sorted(src.rglob("*.md")) if src.is_dir() else []:
    if file_hint and file_hint not in path.name.lower():
        continue
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if rx.search(line):
            print(f"{path.relative_to(root)}:{i}: {line.strip()[:120]}")
            hits += 1
            if hits >= 30:
                raise SystemExit(0)
print("Nessun risultato" if hits == 0 else "")
