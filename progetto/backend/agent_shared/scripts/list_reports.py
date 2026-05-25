#!/usr/bin/env python3
"""Elenco JSON in WORKSPACE_ROOT/reports."""
import os
import sys
from pathlib import Path

root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
rep = root / "reports"
if not rep.is_dir():
    print("reports/ non trovato:", rep, file=sys.stderr)
    raise SystemExit(1)
for p in sorted(rep.glob("*.json")):
    print(p.name)
