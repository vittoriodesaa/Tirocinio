#!/usr/bin/env python3
"""Elenco file in WORKSPACE_ROOT/sources (stdout)."""
import os
from pathlib import Path

root = Path(os.environ.get('WORKSPACE_ROOT', '.'))
src = root / 'sources'
if not src.is_dir():
    print('sources/ non trovato:', src)
    raise SystemExit(1)
for p in sorted(src.iterdir()):
    if p.is_file():
        print(p.name, p.stat().st_size, 'bytes')
