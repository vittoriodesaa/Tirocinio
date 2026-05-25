#!/usr/bin/env python3
"""Converte .doc/.docx in Markdown. Vedi README."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.tools.doc_to_markdown import main

if __name__ == "__main__":
    main()
