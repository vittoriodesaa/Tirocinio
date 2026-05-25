#!/usr/bin/env python3
"""Converte PDF in Markdown (batch su una cartella). Vedi README."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.tools.pdf_to_markdown import main

if __name__ == "__main__":
    raise SystemExit(main())
