"""Utilità condivise per lettura/scrittura nel workspace."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def heading_level(line: str) -> int:
    m = re.match(r"^(#{1,6})\s", line.strip())
    return len(m.group(1)) if m else 0


def find_section_lines(lines: list[str], query: str) -> tuple[int, int]:
    q = query.strip().lower()
    start = None
    start_level = 0
    for i, line in enumerate(lines):
        lvl = heading_level(line)
        if lvl and q in line.lower():
            start = i + 1
            start_level = lvl
            break
    if start is None:
        for i, line in enumerate(lines):
            if q in line.lower():
                return i + 1, min(i + 80, len(lines))
        raise ValueError(f"Sezione non trovata: {query}")

    end = len(lines)
    for j in range(start, len(lines)):
        lvl = heading_level(lines[j])
        if lvl and lvl <= start_level and j + 1 > start:
            end = j
            break
    if end <= start:
        end = min(start + 100, len(lines))
    return start, end


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
