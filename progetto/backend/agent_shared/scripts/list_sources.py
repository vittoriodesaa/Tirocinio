#!/usr/bin/env python3
"""Elenco file in WORKSPACE_ROOT/sources (generico, ogni corso)."""
import os
import sys
from pathlib import Path

root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
src = root / "sources"
if not src.is_dir():
    print("sources/ non trovato:", src, file=sys.stderr)
    raise SystemExit(1)
for p in sorted(src.iterdir()):
    if p.is_file():
        print(f"{p.name}	{p.stat().st_size} bytes")
