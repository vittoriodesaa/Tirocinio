"""Percorsi radice del backend (cartelle dati, static, workspace)."""
from __future__ import annotations

from pathlib import Path

# progetto/backend/
BACKEND_ROOT = Path(__file__).resolve().parent.parent

WORKSPACE_ROOT = BACKEND_ROOT / "workspace"
# Libreria globale Deep Agent (script e note riusabili su tutti i corsi)
AGENT_SHARED_ROOT = BACKEND_ROOT / "agent_shared"
STATIC_DIR = BACKEND_ROOT / "static"
DATA_DIR = BACKEND_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
EXAMPLES_DIR = DATA_DIR / "examples"
ENV_FILE = BACKEND_ROOT / ".env"
ENV_EXAMPLE = BACKEND_ROOT / ".env.example"

# Retrocompatibilità (vecchi upload PDF e workspace temporaneo)
LEGACY_TEMP_DIR = BACKEND_ROOT / "temp"
LEGACY_WORKSPACE = LEGACY_TEMP_DIR / "workspace"

# Cartelle sotto workspace/ che non sono corsi (infra agente, ecc.)
WORKSPACE_NON_COURSE_DIRS = frozenset({"_agent_homes", "agent_shared"})


def is_course_workspace_dir(name: str) -> bool:
    """True se la directory in workspace/ va elencata come corso."""
    if not name or name.startswith(".") or name.startswith("_"):
        return False
    return name not in WORKSPACE_NON_COURSE_DIRS
