"""
Libreria globale del Deep Agent: script e markdown riusabili su ogni corso.

La home condivisa (`agent_shared/`) è il default del filesystem virtuale.
I materiali del corso corrente sono montati in sola lettura su `/sources`, ecc.
`WORKSPACE_ROOT` (env a ogni run) indica quale corso si sta elaborando.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from deepagents.backends import CompositeBackend, FilesystemBackend, LocalShellBackend
from deepagents.backends.protocol import BackendProtocol, EditResult, WriteResult
from deepagents.middleware.filesystem import FilesystemPermission
from pipeline.paths import AGENT_SHARED_ROOT, BACKEND_ROOT

_COURSE_ROUTE_SUBDIRS = ("sources", "chunks", "reports", "modules", "uploads")
_READ_ONLY_COURSE_MSG = "Sola lettura: cartella del corso corrente."


class _ReadOnlyCourseBackend:
    """Blocca write/edit sulle route del corso; inoltra ls/read/grep/glob."""

    def __init__(self, inner: BackendProtocol):
        self._inner = inner

    def write(self, *args: Any, **kwargs: Any) -> WriteResult:
        return WriteResult(error=_READ_ONLY_COURSE_MSG)

    def edit(self, *args: Any, **kwargs: Any) -> EditResult:
        return EditResult(error=_READ_ONLY_COURSE_MSG)

    async def awrite(self, *args: Any, **kwargs: Any) -> WriteResult:
        return WriteResult(error=_READ_ONLY_COURSE_MSG)

    async def aedit(self, *args: Any, **kwargs: Any) -> EditResult:
        return EditResult(error=_READ_ONLY_COURSE_MSG)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def shared_agent_home_path() -> Path:
    """Percorso su disco della libreria condivisa (uguale per tutti i corsi)."""
    return Path(
        os.getenv("MICROLEARNING_AGENT_SHARED_ROOT", str(AGENT_SHARED_ROOT)),
    ).resolve()


def setup_shared_agent_home() -> Path:
    """Crea la libreria globale e i template generici se mancanti."""
    home = shared_agent_home_path()
    for sub in ("notes", "scripts", "memory"):
        (home / sub).mkdir(parents=True, exist_ok=True)

    seeds: dict[Path, str] = {
        home / "README.md": _readme_template(),
        home / "notes" / "percorsi_filesystem.md": _percorsi_filesystem_note(),
        home / "notes" / "workflow_microlearning.md": _workflow_note(),
        home / "notes" / "struttura_lezione.md": _struttura_lezione_note(),
        home / "notes" / "quiz_linee_guida.md": _quiz_note(),
        home / "memory" / "miglioramenti.md": _miglioramenti_note(),
        home / "scripts" / "list_sources.py": _script_list_sources(),
        home / "scripts" / "list_reports.py": _script_list_reports(),
        home / "scripts" / "grep_sources.py": _script_grep_sources(),
        home / "scripts" / "estrai_titoli_h2.py": _script_estrai_h2(),
    }
    for path, content in seeds.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            if path.suffix == ".py":
                path.chmod(0o755)

    return home


def _readme_template() -> str:
    return """# Libreria globale Deep Agent

Questa cartella è **condivisa tra tutti i corsi**. Script e markdown qui dentro devono restare
**generici e riusabili** — non salvare piani o appunti legati a un singolo libro/corso.

## Contenuto

| Percorso | Contenuto |
|----------|-----------|
| `/notes/` | Playbook: percorsi filesystem, workflow, struttura lezioni, quiz |
| `/scripts/` | Helper da eseguire con `execute` (leggono `WORKSPACE_ROOT` a runtime) |
| `/memory/miglioramenti.md` | Lezioni apprese **trasversali** (cosa ha funzionato in generale) |

## Corso in elaborazione

A ogni run viene impostato `WORKSPACE_ROOT` = cartella del corso su disco.
I materiali del corso corrente sono in sola lettura: `/sources`, `/chunks`, `/reports`, …

## Cosa NON fare qui

- Nessun `plan_corso_X.md`, outline di un libro specifico, dump di capitoli.
- Il piano del corso in corso va in `write_todos` o direttamente nei tool `aggiungi_modulo_corso`.

## Cosa fare per autoincrementarsi

1. Migliora gli script in `/scripts/` quando trovi un pattern ripetibile.
2. Aggiorna `/notes/` se refine workflow o template didattici **validi per ogni corso**.
3. Aggiungi voci brevi in `/memory/miglioramenti.md` (pattern path o grep validi per ogni corso).

**Ordine di lettura:** `/notes/percorsi_filesystem.md` → `workflow_microlearning.md` → `struttura_lezione.md`.
"""


def _percorsi_filesystem_note() -> str:
    path = AGENT_SHARED_ROOT / "notes" / "percorsi_filesystem.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return (BACKEND_ROOT / "agent_shared" / "notes" / "percorsi_filesystem.md").read_text(
        encoding="utf-8",
    )


def _workflow_note() -> str:
    return """# Workflow microlearning (generico)

**Prima di tutto:** leggi `/notes/percorsi_filesystem.md` (path virtuali, cosa evitare).

1. `python3 scripts/list_sources.py` — quali markdown ci sono (evita `ls` su path assoluti).
2. `leggi_gerarchia_documento` con `/reports/*_hierarchy.json` — **una volta**.
3. Opzionale: `python3 scripts/estrai_titoli_h2.py` — mappa sezioni sul sorgente principale.
4. `imposta_corso` — titolo e descrizione in italiano.
5. Per ogni lezione: `trova_sezione` + `read_file` mirato (offset/limit) → `aggiungi_modulo_corso`.
6. Ogni 2–3 lezioni: `aggiungi_quiz_corso` collegato alla lezione precedente (`dopo_modulo_id`).
7. Obiettivo tipico: 8–12 lezioni + almeno 2 quiz; non duplicare l'intero libro.

## Efficienza

- Dopo i passi 1–3, **passa subito** a `imposta_corso` e alle lezioni.
- Per lezione: al massimo 2–4 tool (`trova_sezione` → `read_file` → `aggiungi_modulo_corso`).
- Se il corso è già sufficiente, rispondi in testo senza altri tool.
"""


def _struttura_lezione_note() -> str:
    return """# Struttura lezione (template generico)

Ogni lezione nel tool `aggiungi_modulo_corso` deve usare markdown con:

- `## Introduzione` — contesto e perché conta
- `## Concetti chiave` — spiegazione narrativa, non solo elenco
- `## Esempio pratico` — caso concreto
- `## Riepilogo` — punti essenziali
- `## Metti in pratica` (opzionale, breve)

Vietato: solo checklist numerata; titolo H2 uguale al campo argomento; sezione "Azione concreta".
"""


def _quiz_note() -> str:
    return """# Linee guida quiz (generico)

- Almeno 3 domande per quiz; 3–4 opzioni ciascuna.
- `dopo_modulo_id` = id lezione verificata (es. mod_003).
- Domande sulla lezione appena vista, non trivia dal resto del libro.
- Spiegazione breve della risposta corretta.
"""


def _miglioramenti_note() -> str:
    return """# Miglioramenti trasversali

Annota qui solo trucchi **validi per qualsiasi corso** (l'agente può appendere righe).

- Leggere sempre `/notes/percorsi_filesystem.md` all'inizio: path del corso = `/sources`, `/chunks`, `/reports`, mai assoluti su disco.
- Dopo `read_file` fallito su path assoluto, non fare `ls` su `/home` o `/` — usare `/sources` e `/reports`.
- `list_sources.py` + `leggi_gerarchia_documento` una volta bastano prima di `imposta_corso`.
- Preferire `trova_sezione` + `read_file` parziale invece di scorrere tutto il markdown a blocchi.
- Manuali tecnici: spesso niente `^## 1.` — usare `trova_sezione`, grep per parole chiave o `estrai_titoli_h2.py`.
- Leggere con `read_file` su `/sources/...`; in execute solo script `/scripts/` (non `head /sources/...`).
"""


def _script_list_sources() -> str:
    return '''#!/usr/bin/env python3
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
        print(f"{p.name}\t{p.stat().st_size} bytes")
'''


def _script_list_reports() -> str:
    return '''#!/usr/bin/env python3
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
'''


def _script_grep_sources() -> str:
    return '''#!/usr/bin/env python3
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
'''


def _script_estrai_h2() -> str:
    return '''#!/usr/bin/env python3
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
    if re.match(r"^##\\s+\\S", line):
        print(f"{i:6d}| {line.strip()[:100]}")
        count += 1
        if count >= 40:
            break
'''


def course_filesystem_permissions() -> list[FilesystemPermission]:
    """Scrittura solo nella libreria globale (note/script/memory condivisi)."""
    writable = [
        "/README.md",
        "/notes",
        "/notes/**",
        "/scripts",
        "/scripts/**",
        "/memory",
        "/memory/**",
    ]
    return [
        FilesystemPermission(operations=["write"], paths=writable, mode="allow"),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]


def _execute_enabled() -> bool:
    return os.getenv("MICROLEARNING_AGENT_EXECUTE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _agent_default_backend(home: Path, workspace: Path) -> BackendProtocol:
    timeout = int(os.getenv("MICROLEARNING_EXECUTE_TIMEOUT", "90"))
    env = {
        "PATH": os.getenv("MICROLEARNING_AGENT_PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "PYTHONPATH": str(home / "scripts"),
        "WORKSPACE_ROOT": str(workspace.resolve()),
        "LANG": "C.UTF-8",
    }
    if _execute_enabled():
        return LocalShellBackend(
            root_dir=str(home),
            virtual_mode=True,
            inherit_env=False,
            timeout=timeout,
            env=env,
        )
    return FilesystemBackend(root_dir=str(home), virtual_mode=True)


def build_course_backend(workspace: Path, shared_home: Path) -> CompositeBackend:
    """Default = libreria globale; route = cartelle del corso corrente (sola lettura)."""
    ws = workspace.resolve()
    home = shared_home.resolve()
    routes: dict[str, BackendProtocol] = {}
    for sub in _COURSE_ROUTE_SUBDIRS:
        sub_path = ws / sub
        if sub_path.is_dir():
            routes[f"/{sub}/"] = _ReadOnlyCourseBackend(
                FilesystemBackend(root_dir=str(sub_path), virtual_mode=True),
            )

    return CompositeBackend(default=_agent_default_backend(home, ws), routes=routes)


def agent_filesystem_permissions() -> list[FilesystemPermission] | None:
    """
    Permessi scrittura sulla sola libreria globale.

    Con execute attivo non si possono combinare permissions + LocalShellBackend:
    in quel caso si affida al default backend (solo agent_shared) e route read-only.
    """
    if _execute_enabled():
        return None
    return course_filesystem_permissions()
