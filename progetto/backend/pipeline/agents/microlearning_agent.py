"""
Pianificazione microlearning con LangChain Deep Agents (`create_deep_agent`).

Esplora il workspace del corso e usa una libreria globale condivisa (`agent_shared/`:
note e script generici riusabili su tutti i corsi) per autoincrementarsi.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, Optional  # Any: modello LLM in registrazione harness

from dotenv import load_dotenv
from pipeline.paths import BACKEND_ROOT, WORKSPACE_ROOT

load_dotenv(BACKEND_ROOT / ".env")

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError
from pipeline.agents.agent_home import (
    agent_filesystem_permissions,
    build_course_backend,
    setup_shared_agent_home,
    shared_agent_home_path,
)
from pipeline.core.agent_logging import (
    LLMUsageAccumulator,
    deep_agent_say,
    deep_agent_tool_call,
    deep_agent_tool_result,
    narrative,
    phase,
    phase_percent_for,
    record_llm_response,
    setup_logging,
)
from pipeline.core.llm_factory import create_chat_model
from pipeline.core.pipeline_state import CORPUS_SOURCE_ID, corpus_plan_path, detect_source_id, list_course_sources
from pipeline.models.schemas import DomandaQuiz, FonteRiferimento, MicrolearningCourse, ModuloMicrolearning

_MAX_READ_LINES = 200
_MAX_GREP_HITS = 25
_MIN_CONTENUTO_LEZIONE = int(os.getenv("MICRO_MIN_CONTENUTO_CHARS", "500"))
_MIN_DOMANDE_QUIZ = int(os.getenv("MICRO_MIN_QUIZ_DOMANDE", "3"))
_MIN_SEZIONI_H2 = int(os.getenv("MICRO_MIN_H2_SECTIONS", "3"))

_MICROLEARNING_HARNESS = HarnessProfile(
    excluded_tools=frozenset({"task"}),
    general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
)
_HARNESS_REGISTERED = False


def _register_microlearning_harness() -> None:
    global _HARNESS_REGISTERED
    if _HARNESS_REGISTERED:
        return
    for key in ("openai", "groq"):
        register_harness_profile(key, _MICROLEARNING_HARNESS)
    _HARNESS_REGISTERED = True


def _plan_point_count(workspace: Path) -> int:
    """Numero di punti nel piano strutturale (corpus o singola sorgente)."""
    ws = workspace.resolve()
    corp = corpus_plan_path(ws)
    if corp.exists():
        try:
            plan = json.loads(corp.read_text(encoding="utf-8"))
            return len(plan.get("lezioni") or plan.get("punti_taglio") or [])
        except json.JSONDecodeError:
            pass
    sid = detect_source_id(ws)
    if not sid:
        return 0
    plan_path = ws / "reports" / f"{sid}_plan.json"
    if not plan_path.exists():
        return 0
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        return len(plan.get("lezioni") or plan.get("punti_taglio") or [])
    except json.JSONDecodeError:
        return 0


def _compute_max_steps(workspace: Path, override: Optional[int] = None) -> int:
    """
    Limite recursion LangGraph (≈ turni agente + tool).

    Override esplicito > MICROLEARNING_MAX_STEPS in .env > default adattivo al piano.
    """
    if override is not None:
        return max(20, override)
    env = os.getenv("MICROLEARNING_MAX_STEPS", "").strip()
    if env:
        return max(20, int(env))

    cap = int(os.getenv("MICROLEARNING_MAX_STEPS_CAP", "400"))
    base = int(os.getenv("MICROLEARNING_MAX_STEPS_DEFAULT", "120"))
    per_lesson = int(os.getenv("MICROLEARNING_STEPS_PER_LESSON", "5"))
    n = _plan_point_count(workspace)
    _, target_lez, _ = _target_course_size(workspace)
    estimated = base + target_lez * per_lesson
    if n > 80:
        estimated += 40
    return min(cap, max(80, estimated))


def _target_course_size(workspace: Path) -> tuple[int, int, int]:
    """(min_lezioni, target_lezioni, min_quiz) scalato dal piano strutturale."""
    floor_min = int(os.getenv("MICROLEARNING_TARGET_MIN_LESSONS", "15"))
    floor_target = int(os.getenv("MICROLEARNING_TARGET_MAX_LESSONS", "40"))
    cap = int(os.getenv("MICROLEARNING_TARGET_LESSONS_CAP", "120"))
    min_quiz_env = int(os.getenv("MICROLEARNING_TARGET_MIN_QUIZ", "3"))
    cov_min = float(os.getenv("MICROLEARNING_PLAN_COVERAGE_MIN", "0.5"))
    cov_target = float(os.getenv("MICROLEARNING_PLAN_COVERAGE", "0.85"))

    n = _plan_point_count(workspace)
    if n > 0:
        min_lez = max(floor_min, min(cap, int(n * cov_min)))
        target_lez = min(cap, max(min_lez, int(n * cov_target)))
        if n <= floor_target:
            target_lez = max(min_lez, n)
    else:
        min_lez = floor_min
        target_lez = floor_target

    min_quiz = max(min_quiz_env, max(2, target_lez // 3))
    return min_lez, target_lez, min_quiz


def _completion_lesson_threshold(min_lez: int, target_lez: int) -> int:
    ratio = float(os.getenv("MICROLEARNING_TARGET_THRESHOLD", "0.9"))
    return max(min_lez, int(target_lez * ratio))


def _count_modules(course: MicrolearningCourse) -> tuple[int, int]:
    lez = sum(1 for m in course.moduli if m.tipo == "lezione")
    quiz = sum(1 for m in course.moduli if m.tipo == "quiz")
    return lez, quiz


def _corpus_source_ids(workspace: Path) -> List[str]:
    corp = corpus_plan_path(workspace)
    if corp.exists():
        try:
            plan = json.loads(corp.read_text(encoding="utf-8"))
            sorgenti = plan.get("sorgenti") or []
            if len(sorgenti) >= 2:
                return list(sorgenti)
        except json.JSONDecodeError:
            pass
    sources = list_course_sources(workspace)
    if len(sources) >= 2:
        return [s["source_id"] for s in sources]
    return []


def _source_id_from_fonte_path(percorso: str) -> Optional[str]:
    name = Path((percorso or "").replace("\\", "/")).name
    if name.endswith("_clean.md"):
        return name[: -len("_clean.md")]
    if name.endswith(".md"):
        return name[:-3]
    return None


def _count_lessons_by_source(course: MicrolearningCourse) -> dict[str, int]:
    counts: dict[str, int] = {}
    for m in course.moduli:
        if m.tipo != "lezione":
            continue
        paths = [m.fonte.percorso]
        paths.extend(fa.percorso for fa in (m.fonti_aggiuntive or []))
        seen: set[str] = set()
        for percorso in paths:
            sid = _source_id_from_fonte_path(percorso)
            if sid and sid not in seen:
                seen.add(sid)
                counts[sid] = counts.get(sid, 0) + 1
    return counts


def _min_lessons_per_corpus_source(threshold: int, n_sources: int) -> int:
    if n_sources < 2:
        return 0
    floor = int(os.getenv("MICROLEARNING_CORPUS_MIN_PER_SOURCE", "0"))
    if floor > 0:
        return floor
    return max(3, threshold // (n_sources * 2))


def _corpus_balance_ok(
    workspace: Path,
    course: MicrolearningCourse,
    *,
    threshold: int,
) -> bool:
    """Ogni documento del corpus deve contribuire al mix prima di chiudere il corso."""
    sids = _corpus_source_ids(workspace)
    if len(sids) < 2:
        return True
    by_src = _count_lessons_by_source(course)
    min_each = _min_lessons_per_corpus_source(threshold, len(sids))
    return all(by_src.get(sid, 0) >= min_each for sid in sids)


def _corpus_bootstrap_lines(workspace: Path, course: MicrolearningCourse) -> List[str]:
    sids = _corpus_source_ids(workspace)
    if len(sids) < 2:
        return []
    by_src = _count_lessons_by_source(course)
    corp = corpus_plan_path(workspace)
    preview_lines: List[str] = []
    if corp.exists():
        try:
            plan = json.loads(corp.read_text(encoding="utf-8"))
            pts = plan.get("punti_taglio") or []
            n_done = sum(1 for m in course.moduli if m.tipo == "lezione")
            if n_done < len(pts):
                nxt = pts[n_done]
                segmenti = nxt.get("segmenti_fonte") or []
                if len(segmenti) >= 2:
                    preview_lines.append(
                        f"Prossima lezione INTEGRATA (ordine {nxt.get('ordine')}): "
                        f"«{nxt.get('titolo', '')[:70]}»"
                    )
                    for seg in segmenti:
                        preview_lines.append(
                            f"  - {seg.get('source_id')}: {seg.get('markdown_sorgente')} "
                            f"righe {seg.get('riga_inizio')}-{seg.get('riga_fine')} "
                            f"«{(seg.get('titolo_originale') or '')[:50]}»"
                        )
                else:
                    preview_lines.append(
                        f"Prossimo punto piano (ordine {nxt.get('ordine')}): "
                        f"«{nxt.get('titolo', '')[:60]}» → {nxt.get('markdown_sorgente', '')}"
                    )
        except (json.JSONDecodeError, IndexError, TypeError):
            pass
    lines = [
        "",
        "CORPUS MULTI-DOCUMENTO — LEZIONI INTEGRATE:",
        f"Sorgenti: {', '.join(sids)}.",
        "Ogni punto in corso_plan.json con segmenti_fonte (2+ libri) è UNA sola lezione che "
        "fonde i materiali: leggi TUTTI i segmenti, poi scrivi un racconto didattico unico in italiano "
        "con collegamenti espliciti tra i libri (non due mini-lezioni separate).",
        "In aggiungi_modulo_corso: percorso_fonte = primo segmento; fonti_aggiuntive = gli altri "
        "(stesse righe del piano).",
        "Lezioni per sorgente finora: "
        + ", ".join(f"{s}={by_src.get(s, 0)}" for s in sids),
    ]
    lines.extend(preview_lines)
    lines.append("Segui l'ordine di corso_plan.json: un modulo per punto_taglio.")
    return lines


def _is_course_sufficient(
    course: MicrolearningCourse,
    *,
    workspace: Path,
    min_lez: int,
    max_lez: int,
    min_quiz: int,
) -> bool:
    lez, quiz = _count_modules(course)
    threshold = _completion_lesson_threshold(min_lez, max_lez)
    if lez < threshold or quiz < min_quiz:
        return False
    return _corpus_balance_ok(workspace, course, threshold=threshold)


def _next_module_ids(course: MicrolearningCourse) -> tuple[str, str, int]:
    """Prossimi id lezione/quiz e ordine suggerito."""
    lez_n = sum(1 for m in course.moduli if m.tipo == "lezione")
    quiz_n = sum(1 for m in course.moduli if m.tipo == "quiz")
    ordine = max((m.ordine for m in course.moduli), default=0) + 1
    return f"mod_{lez_n + 1:03d}", f"quiz_{quiz_n + 1:03d}", ordine


def _register_microlearning_harness_for_model(llm: Any, model_name: str, provider: str) -> None:
    """Associa il profilo al modello risolto (OpenRouter usa client openai)."""
    from deepagents._models import get_model_identifier, get_model_provider

    ident = get_model_identifier(llm)
    prov = get_model_provider(llm) or provider
    keys: list[str] = []
    if prov:
        keys.append(prov)
    if prov and ident:
        keys.append(f"{prov}:{ident}")
    if ident:
        keys.append(ident)
    if model_name:
        keys.append(model_name)
    for key in dict.fromkeys(keys):
        register_harness_profile(key, _MICROLEARNING_HARNESS)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _CourseStore:
    """Stato del corso con scrittura incrementale su disco."""

    def __init__(self, path: Path, workspace: Path):
        self.path = path
        self.workspace = workspace
        self.course = MicrolearningCourse(
            titolo_corso="Corso microlearning",
            lingua="it",
            descrizione="",
            metadati={
                "generato_il": _now_iso(),
                "workspace": str(workspace),
                "agente": "microlearning_planning_agent",
            },
        )
        if self.path.exists():
            try:
                self.course = MicrolearningCourse(
                    **json.loads(self.path.read_text(encoding="utf-8")),
                )
            except (json.JSONDecodeError, OSError, ValueError):
                self._flush(label="inizializzazione", silent=True)
        else:
            self._flush(label="inizializzazione", silent=True)

    def _flush(self, label: str, *, silent: bool = False) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.course.model_dump()
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if not silent and self.course.moduli:
            narrative(
                f"Ho aggiunto la lezione {len(self.course.moduli)} al corso microlearning.",
                percent=phase_percent_for(
                    "microlearning_agent",
                    min(0.95, 0.4 + len(self.course.moduli) * 0.04),
                ),
            )

    def init_meta(self, titolo: str, descrizione: str) -> str:
        if self.course.moduli:
            return (
                f"Corso già avviato con {len(self.course.moduli)} moduli "
                f"('{self.course.titolo_corso}'). NON chiamare di nuovo imposta_corso."
            )
        self.course.titolo_corso = titolo
        self.course.descrizione = descrizione
        self._flush("meta_corso")
        return f"Corso inizializzato: '{titolo}'"

    def add_module(self, modulo: ModuloMicrolearning) -> str:
        if any(m.id == modulo.id for m in self.course.moduli):
            return (
                f"ERRORE: id '{modulo.id}' già presente. "
                f"Usa un id nuovo (es. {_next_module_ids(self.course)[0]})."
            )
        self.course.moduli.append(modulo)
        self.course.moduli.sort(key=lambda m: m.ordine)
        self._flush(f"modulo_{modulo.id}")
        tipo = modulo.tipo
        extra = ""
        if tipo == "lezione":
            extra = f", {len(modulo.contenuto)} caratteri di contenuto"
        else:
            extra = f", {len(modulo.domande)} domande"
        return (
            f"{tipo.capitalize()} {modulo.id} aggiunto (ordine {modulo.ordine}): "
            f"{modulo.argomento}{extra}"
        )


def _resolve_workspace_file(
    workspace: Path,
    relative: str,
    *,
    kind: Literal["chunks", "hierarchy", "sources", "any"] = "any",
) -> Path:
    """
    Risolve un percorso nel workspace del corso.

    Tollera path virtuali (/chunks/...), assoluti sotto workspace, o solo nome file.
    """
    ws = workspace.resolve()
    raw = (relative or "").strip().replace("\\", "/")
    sid = detect_source_id(ws)

    candidates: list[Path] = []
    if raw:
        p = Path(raw)
        if p.is_absolute():
            candidates.append(p)
        else:
            rel = raw.lstrip("/")
            candidates.append(ws / rel)
            if "/" not in rel and kind == "chunks":
                candidates.append(ws / "chunks" / rel)
            if "/" not in rel and kind in ("sources", "any"):
                candidates.append(ws / "sources" / rel)

    if kind in ("chunks", "any") and sid:
        candidates.append(ws / "chunks" / f"{sid}_chunks.json")
        chunks_dir = ws / "chunks"
        if chunks_dir.is_dir():
            candidates.extend(sorted(chunks_dir.glob("*_chunks.json")))

    if kind in ("hierarchy", "any") and sid:
        candidates.append(ws / "reports" / f"{sid}_hierarchy.json")
        reports = ws / "reports"
        if reports.is_dir():
            candidates.extend(sorted(reports.glob("*_hierarchy.json")))

    if kind in ("sources", "any") and sid:
        for name in (f"{sid}.md", f"{sid}_clean.md", f"{sid}_raw.md"):
            candidates.append(ws / "sources" / name)

    seen: set[Path] = set()
    for cand in candidates:
        try:
            target = cand.resolve()
        except OSError:
            continue
        if target in seen:
            continue
        seen.add(target)
        if not str(target).startswith(str(ws)):
            continue
        if target.is_file():
            return target

    hint = ""
    if kind == "chunks" and sid:
        hint = f" Atteso: chunks/{sid}_chunks.json"
    elif kind == "hierarchy" and sid:
        hint = f" Atteso: reports/{sid}_hierarchy.json"
    raise FileNotFoundError(f"File non trovato: {raw or '(vuoto)'}.{hint}")


def _tool_path_error(exc: BaseException) -> str:
    return f"ERRORE: {exc}"


def _heading_level(line: str) -> int:
    m = re.match(r"^(#{1,6})\s", line.strip())
    return len(m.group(1)) if m else 0


def _find_section_lines(lines: list[str], query: str) -> tuple[int, int]:
    """Riga inizio/fine (1-based) della sezione il cui titolo contiene query."""
    q = query.strip().lower()
    start = None
    start_level = 0
    for i, line in enumerate(lines):
        lvl = _heading_level(line)
        if lvl and q in line.lower():
            start = i + 1
            start_level = lvl
            break
    if start is None:
        for i, line in enumerate(lines):
            if q in line.lower():
                return i + 1, min(i + 80, len(lines))
        raise ValueError(f"Sezione non trovata per: {query}")

    end = len(lines)
    for j in range(start, len(lines)):
        lvl = _heading_level(lines[j])
        if lvl and lvl <= start_level and j + 1 > start:
            end = j
            break
    if end <= start:
        end = min(start + 100, len(lines))
    return start, end


def _estrai_testo_fonte(workspace: Path, fonte: FonteRiferimento, max_chars: int = 12000) -> str:
    """Estrae il testo grezzo dalla fonte (fallback se contenuto lezione troppo corto)."""
    try:
        path = _resolve_workspace_file(workspace, fonte.percorso, kind="sources")
    except (ValueError, FileNotFoundError):
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, fonte.riga_inizio)
    end = fonte.riga_fine or min(start + 150, len(lines))
    end = min(end, len(lines))
    chunk = "\n".join(lines[start - 1 : end]).strip()
    if len(chunk) > max_chars:
        return chunk[: max_chars - 3] + "..."
    return chunk


def _conteggia_sezioni_h2(testo: str) -> int:
    return len(re.findall(r"^##\s+\S", testo, re.MULTILINE))


def _valida_struttura_lezione(testo: str) -> str | None:
    """None se ok, altrimenti messaggio errore per il tool."""
    lower = testo.lower()
    if _conteggia_sezioni_h2(testo) < _MIN_SEZIONI_H2:
        return (
            f"ERRORE: servono almeno {_MIN_SEZIONI_H2} sezioni ## "
            f"(Introduzione, Concetti chiave, Riepilogo, ecc.)."
        )
    has_intro = bool(
        re.search(
            r"^##\s+(introduzione|contesto|in questa lezione|perché)",
            lower,
            re.MULTILINE,
        )
    )
    has_riepilogo = bool(
        re.search(
            r"^##\s+(riepilogo|cosa hai imparato|sintesi|takeaway)",
            lower,
            re.MULTILINE,
        )
    )
    has_nucleo = bool(
        re.search(
            r"^##\s+(concetti|esempio|analogia|come\s)",
            lower,
            re.MULTILINE,
        )
    )
    if not has_intro:
        return (
            "ERRORE: apri con ## Introduzione (contesto e perché serve), "
            "non con un titolo diverso dall'argomento."
        )
    if not has_riepilogo:
        return "ERRORE: chiudi con ## Riepilogo (punti essenziali)."
    if not has_nucleo:
        return (
            "ERRORE: aggiungi ## Concetti chiave e/o ## Esempio pratico "
            "con spiegazione narrativa (non solo elenco numerato)."
        )
    if re.search(r"^##\s+azione\s+concreta\s*$", lower, re.MULTILINE):
        return (
            "ERRORE: usa '## Metti in pratica' (breve) invece di '## Azione concreta'."
        )
    return None


def _completa_lezioni_da_fonte(course: MicrolearningCourse, workspace: Path) -> int:
    """Riempie contenuto insufficiente leggendo il markdown sorgente."""
    aggiornati = 0
    for mod in course.moduli:
        if mod.tipo != "lezione":
            continue
        if len(mod.contenuto.strip()) >= _MIN_CONTENUTO_LEZIONE:
            continue
        estratto = _estrai_testo_fonte(workspace, mod.fonte)
        if len(estratto) < 200:
            continue
        intro = mod.sintesi_breve.strip()
        if intro:
            mod.contenuto = f"{intro}\n\n---\n\n{estratto}"
        else:
            mod.contenuto = estratto
        if len(mod.contenuto) >= _MIN_CONTENUTO_LEZIONE:
            aggiornati += 1
    return aggiornati


def build_course_tools(workspace_dir: str, course_store: _CourseStore) -> list:
    workspace = Path(workspace_dir).resolve()

    @tool
    def trova_sezione(
        percorso: Annotated[str, "Markdown del libro, es. sources/test_doc_001.md"],
        titolo_sezione: Annotated[str, "Titolo o parola chiave della sezione (es. Chapter 3, Funzioni)"],
    ) -> str:
        """Trova riga_inizio e riga_fine di una sezione nel markdown."""
        try:
            path = _resolve_workspace_file(workspace, percorso, kind="sources")
        except (ValueError, FileNotFoundError) as e:
            return _tool_path_error(e)
        percorso = str(path.relative_to(workspace))
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        try:
            start, end = _find_section_lines(lines, titolo_sezione)
        except ValueError as e:
            pass
            return str(e)
        pass
        return json.dumps(
            {
                "percorso": percorso,
                "titolo_ricerca": titolo_sezione,
                "riga_inizio": start,
                "riga_fine": end,
                "anteprima": lines[start - 1][:120] if start <= len(lines) else "",
            },
            ensure_ascii=False,
        )

    @tool
    def leggi_gerarchia_documento(
        percorso_hierarchy: Annotated[
            str,
            "JSON gerarchia da reports, es. reports/test_doc_001_hierarchy.json",
        ],
    ) -> str:
        """Legge macro-argomenti e sintesi già prodotte dal DocumentAgent."""
        try:
            path = _resolve_workspace_file(
                workspace,
                percorso_hierarchy,
                kind="hierarchy",
            )
        except (ValueError, FileNotFoundError) as e:
            return _tool_path_error(e)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return _tool_path_error(e)
        macro = data.get("macro_argomenti", [])
        mappa = data.get("mappa_sintesi", {})
        narrative("Leggo l'indice dei capitoli già sintetizzati…", percent=phase_percent_for("microlearning_agent", 0.25))
        righe = []
        for titolo in macro[:40]:
            sint = (mappa.get(titolo) or "")[:280]
            righe.append(f"- **{titolo}**: {sint}")
        extra = len(macro) - 40
        if extra > 0:
            righe.append(f"... altri {extra} argomenti")
        return "\n".join(righe)

    @tool
    def leggi_indice_chunks(
        percorso_chunks: Annotated[
            str,
            "JSON chunk (opzionale: vuoto = auto da source_id), es. chunks/nome_chunks.json",
        ] = "",
        max_voci: Annotated[int, "Quante voci mostrare"] = 30,
    ) -> str:
        """Riassume i chunk (titoli sezione) per orientarsi nel libro."""
        try:
            path = _resolve_workspace_file(
                workspace,
                percorso_chunks,
                kind="chunks",
            )
        except (ValueError, FileNotFoundError) as e:
            return _tool_path_error(e)
        try:
            chunks = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return _tool_path_error(e)
        if not isinstance(chunks, list):
            return "ERRORE: il file chunk non contiene una lista JSON."
        pass
        righe = []
        for c in chunks[:max_voci]:
            titolo = c.get("section_path", ["?"])[-1]
            righe.append(
                f"- {c.get('chunk_id')}: {titolo} "
                f"(token≈{c.get('token_estimate')}, pagine {c.get('page_refs')})"
            )
        if len(chunks) > max_voci:
            righe.append(f"... altri {len(chunks) - max_voci} chunk")
        rel = path.relative_to(workspace).as_posix()
        return f"File: {rel}\n" + "\n".join(righe)

    @tool
    def imposta_corso(
        titolo_corso: Annotated[str, "Titolo del corso microlearning in italiano"],
        descrizione: Annotated[str, "Descrizione breve del percorso formativo in italiano"],
    ) -> str:
        """Imposta titolo e descrizione del corso; salva subito il JSON su disco."""
        return course_store.init_meta(titolo_corso, descrizione)

    @tool
    def aggiungi_modulo_corso(
        id_modulo: Annotated[str, "Identificativo es. mod_001"],
        ordine: Annotated[int, "Posizione nel percorso (1, 2, 3...)"],
        argomento: Annotated[str, "Titolo dell'argomento in italiano"],
        contenuto: Annotated[
            str,
            f"Lezione completa in italiano: spiegazione estesa, esempi, minimo {_MIN_CONTENUTO_LEZIONE} caratteri",
        ],
        percorso_fonte: Annotated[str, "File sorgente relativo, es. sources/test_doc_001.md"],
        riga_inizio: Annotated[int, "Riga dove inizia l'argomento nel file"],
        riga_fine: Annotated[Optional[int], "Riga fine sezione; opzionale"] = None,
        sintesi_breve: Annotated[str, "Sintesi iniziale 2-3 frasi (opzionale)"] = "",
        obiettivi: Annotated[
            list[str],
            "Lista obiettivi di apprendimento in italiano",
        ] = [],
        durata_minuti: Annotated[int, "Durata stimata modulo"] = 12,
        prerequisiti: Annotated[list[str], "ID moduli prerequisito"] = [],
        fonti_aggiuntive: Annotated[
            list[dict],
            "Altre fonti della stessa lezione integrata: "
            "[{percorso, riga_inizio, riga_fine}] (corpus multi-libro)",
        ] = [],
    ) -> str:
        """Aggiunge una LEZIONE strutturata (non un articolo o checklist); salva subito il JSON."""
        testo = (contenuto or "").strip()
        if len(testo) < _MIN_CONTENUTO_LEZIONE:
            return (
                f"ERRORE: contenuto troppo corto ({len(testo)} caratteri). "
                f"Leggi la sezione con leggi_file e scrivi almeno {_MIN_CONTENUTO_LEZIONE} caratteri "
                f"in italiano seguendo la struttura lezione del prompt."
            )
        err_struct = _valida_struttura_lezione(testo)
        if err_struct:
            return err_struct
        extra_fonti: list[FonteRiferimento] = []
        for i, raw in enumerate(fonti_aggiuntive or []):
            if isinstance(raw, str):
                return f"ERRORE fonti_aggiuntive[{i}]: passa un oggetto JSON, non una stringa."
            percorso = str(raw.get("percorso", "")).strip()
            if not percorso:
                return f"ERRORE fonti_aggiuntive[{i}]: percorso mancante."
            extra_fonti.append(
                FonteRiferimento(
                    percorso=percorso,
                    riga_inizio=int(raw.get("riga_inizio", 1)),
                    riga_fine=raw.get("riga_fine"),
                )
            )
        modulo = ModuloMicrolearning(
            id=id_modulo,
            ordine=ordine,
            tipo="lezione",
            argomento=argomento,
            sintesi_breve=sintesi_breve or testo[:280],
            contenuto=testo,
            fonte=FonteRiferimento(
                percorso=percorso_fonte,
                riga_inizio=riga_inizio,
                riga_fine=riga_fine,
            ),
            fonti_aggiuntive=extra_fonti,
            obiettivi_apprendimento=obiettivi or [],
            durata_stimata_minuti=durata_minuti,
            prerequisiti=prerequisiti or [],
        )
        return course_store.add_module(modulo)

    @tool
    def aggiungi_quiz_corso(
        id_quiz: Annotated[str, "Identificativo es. quiz_003"],
        ordine: Annotated[int, "Posizione nel percorso (dopo la lezione verificata)"],
        titolo: Annotated[str, "Titolo quiz in italiano, es. Verifica: Variabili in Python"],
        dopo_modulo_id: Annotated[str, "ID della lezione che il quiz verifica (es. mod_002)"],
        domande: Annotated[
            list[dict],
            "Lista domande: [{testo, opzioni: [..], indice_corretto: 0, spiegazione}]",
        ],
        percorso_fonte: Annotated[str, "Stesso file della lezione collegata"] = "",
        riga_inizio: Annotated[int, "Riga fonte (della lezione)"] = 1,
        riga_fine: Annotated[Optional[int], "Riga fine fonte"] = None,
        durata_minuti: Annotated[int, "Durata stimata quiz"] = 5,
    ) -> str:
        """Aggiunge un QUIZ di verifica dopo una lezione; compare nel grafo come nodo separato."""
        if len(domande) < _MIN_DOMANDE_QUIZ:
            return f"ERRORE: servono almeno {_MIN_DOMANDE_QUIZ} domande per il quiz."

        parsed: list[DomandaQuiz] = []
        for i, d in enumerate(domande):
            if isinstance(d, str):
                return f"ERRORE domanda {i + 1}: passa un oggetto JSON, non una stringa."
            opts = d.get("opzioni") or []
            if len(opts) < 2:
                return f"ERRORE domanda {i + 1}: servono almeno 2 opzioni."
            idx = int(d.get("indice_corretto", 0))
            if idx < 0 or idx >= len(opts):
                return f"ERRORE domanda {i + 1}: indice_corretto fuori range."
            parsed.append(
                DomandaQuiz(
                    testo=str(d.get("testo", "")).strip(),
                    opzioni=[str(o) for o in opts],
                    indice_corretto=idx,
                    spiegazione=str(d.get("spiegazione", "")).strip(),
                )
            )

        lezione = next(
            (m for m in course_store.course.moduli if m.id == dopo_modulo_id),
            None,
        )
        fonte_path = percorso_fonte
        r_start = riga_inizio
        r_end = riga_fine
        if lezione:
            fonte_path = fonte_path or lezione.fonte.percorso
            r_start = lezione.fonte.riga_inizio
            r_end = lezione.fonte.riga_fine

        if not fonte_path:
            return "ERRORE: specifica percorso_fonte o un dopo_modulo_id valido."

        modulo = ModuloMicrolearning(
            id=id_quiz,
            ordine=ordine,
            tipo="quiz",
            argomento=titolo,
            sintesi_breve=f"Quiz di verifica dopo {dopo_modulo_id}",
            contenuto="",
            fonte=FonteRiferimento(
                percorso=fonte_path,
                riga_inizio=r_start,
                riga_fine=r_end,
            ),
            obiettivi_apprendimento=[],
            durata_stimata_minuti=durata_minuti,
            prerequisiti=[dopo_modulo_id],
            domande=parsed,
        )
        return course_store.add_module(modulo)

    return [
        trova_sezione,
        leggi_gerarchia_documento,
        leggi_indice_chunks,
        imposta_corso,
        aggiungi_modulo_corso,
        aggiungi_quiz_corso,
    ]


_LEZIONE_TEMPLATE = """
STRUTTURA OBBLIGATORIA del campo `contenuto` (markdown, in italiano):

## Introduzione
2-3 paragrafi: contesto, perché conta per uno sviluppatore, collegamento alla lezione precedente se c'è.

## Concetti chiave
Spiegazione didattica (NON una checklist numerata tipo blog). Usa ### sotto-sezioni per ogni idea.
Includi almeno un esempio concreto (scenario, dialogo, mini-caso).

## Esempio pratico
Un situazione reale applicata passo passo.

## Riepilogo
3-5 punti essenziali in elenco puntato (cosa portarsi a casa).

## Metti in pratica (opzionale, max 5 righe)
Una sola micro-attività riflessiva, separata dalla spiegazione. NON sostituire le sezioni sopra.

VIETATO:
- Titolo H2 duplicato del campo argomento all'inizio (es. argomento già dice "Obiettivi di carriera" → non ripetere come primo ##).
- Liste 1. 2. 3. come unico corpo della lezione senza narrativa.
- Sezione "## Azione concreta" (usa "## Metti in pratica").
- Articolo motivazionale senza insegnare concetti.
"""

_SYSTEM_PROMPT = f"""Sei un agente esperto di instructional design che progetta LEZIONI microlearning in ITALIANO.

Hai accesso al workspace con libri convertiti in markdown (sources/), chunk (chunks/) e report (reports/).

TOOL:
- Esplorazione corso (sola lettura): ls, read_file, grep, glob su /sources, /chunks, /reports.
- Libreria globale (radice `/`: **stessa per tutti i corsi**, non legata al workspace):
  - /notes/ playbook generici, /scripts/ helper riusabili, /memory/miglioramenti.md.
  - write_file/edit_file solo per migliorare quella libreria (contenuti trasversali).
  - execute: `python3 scripts/...` — i script usano WORKSPACE_ROOT solo a runtime per il corso corrente.
  - VIETATO salvare in /notes o /scripts piani o dump specifici di un singolo corso.
- Dominio: trova_sezione, leggi_gerarchia_documento, leggi_indice_chunks.
- Corso (JSON finale): imposta_corso, aggiungi_modulo_corso, aggiungi_quiz_corso — NON scrivere il JSON a mano.

OBIETTIVO:
0. Leggi /README.md, /notes/percorsi_filesystem.md e /notes/workflow_microlearning.md; riusa script in /scripts/.
1. Esplora il corso corrente su /sources, /chunks, /reports (tool dominio + script); piano solo in write_todos o tool corso.
2. Chiama imposta_corso una volta.
3. Per ogni LEZIONE: se il punto corrente in corso_plan.json ha segmenti_fonte, leggi OGNI segmento
   (read_file su ogni markdown/righe), poi aggiungi_modulo_corso con:
   - argomento = titolo breve della lezione (una riga);
   - contenuto = lezione markdown strutturata (min {_MIN_CONTENUTO_LEZIONE} caratteri);
   - obiettivi_apprendimento = 3-4 verbi d'azione (usati anche nella UI, non ripetere tutto il testo lì);
   - fonte con righe verificate.
4. Inserisci QUIZ con aggiungi_quiz_corso dopo blocchi importanti (ogni 2-3 lezioni):
   - almeno {_MIN_DOMANDE_QUIZ} domande; dopo_modulo_id = lezione verificata.
5. Riepilogo finale senza altri tool.

{_LEZIONE_TEMPLATE}

REGOLE:
- Copri il piano strutturale (punti_taglio / gerarchia): una lezione per argomento significativo, non un riassunto di pochi capitoli.
- Corso corpus (reports/corso_plan.json con più sorgenti): ogni punto_taglio con segmenti_fonte
  richiede UNA lezione che integra tutti i libri elencati (leggi ogni segmento, sintetizza in italiano,
  collega i concetti). Usa fonti_aggiuntive per le sorgenti oltre la prima. NON alternare lezioni
  separate per libro.
- L'obiettivo preciso (min/target lezioni e quiz) è nel messaggio utente iniziale: prosegui finché non lo raggiungi.
- Inserisci quiz ogni 2-3 lezioni fino a soddisfare il minimo quiz richiesto.
- Riscrivi in italiano didattico (non copiare l'inglese grezzo).
- Ogni lezione deve INSEGNARE, non solo elencare consigli.
- Non inventare righe fonte: verificale con i tool.
- PATH: solo path virtuali del corso (/sources, /chunks, /reports). MAI path assoluti su disco (/home/...).
  Se read_file fallisce su assoluto, non esplorare /home o / — vedi /notes/percorsi_filesystem.md.
- Dopo 1-2 esplorazioni (gerarchia + chunk o script) passa subito a imposta_corso e alle lezioni;
  per ogni lezione: trova_sezione/read_file → aggiungi_modulo_corso (2-4 tool max).
- Se il messaggio utente dice RIPRESA: NON rifare imposta_corso né lezioni già elencate; aggiungi SOLO moduli mancanti.
- Quando obiettivo lezioni/quiz raggiunto, rispondi in testo senza altri tool (zero chiamate tool).

QUIZ: id quiz_001…; domande chiare, 3-4 opzioni, spiegazione breve.
"""


class MicrolearningPlanningAgent:
    """Pianificatore microlearning basato su LangChain Deep Agents."""

    def __init__(
        self,
        workspace_dir: str,
        course_output_path: Optional[str] = None,
        *,
        max_steps: Optional[int] = None,
    ):
        _register_microlearning_harness()
        self.workspace_dir = str(Path(workspace_dir).resolve())
        ws = Path(self.workspace_dir)
        default_out = ws / "reports" / "microlearning_course.json"
        self.course_path = Path(
            course_output_path or os.getenv("MICROLEARNING_COURSE_PATH", str(default_out)),
        )
        if not self.course_path.is_absolute():
            self.course_path = ws / self.course_path

        self.max_steps = _compute_max_steps(ws, max_steps)
        self.llm_usage = LLMUsageAccumulator()
        self.llm, self._model_name, self._provider = create_chat_model()
        _register_microlearning_harness_for_model(self.llm, self._model_name, self._provider)
        self._shared_home = setup_shared_agent_home()
        self._course_store = _CourseStore(self.course_path, ws)
        course_tools = build_course_tools(self.workspace_dir, self._course_store)
        agent_kwargs: dict = {
            "model": self.llm,
            "tools": course_tools,
            "system_prompt": _SYSTEM_PROMPT,
            "backend": build_course_backend(ws, self._shared_home),
        }
        perms = agent_filesystem_permissions()
        if perms is not None:
            agent_kwargs["permissions"] = perms
        self._agent = create_deep_agent(**agent_kwargs)

    def _record_usage_from_messages(self, messages: list) -> None:
        step = 0
        for msg in messages:
            if not isinstance(msg, AIMessage):
                continue
            tool_calls = getattr(msg, "tool_calls", None) or []
            content = getattr(msg, "content", None) or ""
            if not tool_calls and not content:
                continue
            step += 1
            sub = min(step, self.max_steps) / self.max_steps
            narrative(
                f"Sto progettando il microlearning (passo {step})…",
                percent=phase_percent_for("microlearning_agent", sub),
            )
            record_llm_response(
                self.llm_usage,
                operation=f"microlearning_step_{step}",
                model=self._model_name,
                duration_s=0.0,
                prompt_chars=len(str(content)),
                raw_message=msg,
                progress=(min(step, self.max_steps), self.max_steps),
            )

    def _bootstrap_message(self, *, resume: bool) -> str:
        """Panoramica iniziale del workspace per guidare l'esplorazione."""
        ws = Path(self.workspace_dir)
        shared = shared_agent_home_path()
        course = self._course_store.course
        min_lez, target_lez, min_quiz = _target_course_size(ws)
        threshold = _completion_lesson_threshold(min_lez, target_lez)
        lez, quiz = _count_modules(course)
        next_mod, next_quiz, next_ord = _next_module_ids(course)
        plan_n = _plan_point_count(ws)

        if resume and course.moduli:
            lines = [
                "RIPRESA corso microlearning (NON ricominciare da zero).",
                f"Corso: «{course.titolo_corso}» — già presenti {lez} lezioni e {quiz} quiz.",
                f"Obiettivo: ≥{threshold} lezioni (target {target_lez}, min {min_lez}) e ≥{min_quiz} quiz.",
                "",
                "Moduli già salvati (NON duplicare):",
            ]
            for m in sorted(course.moduli, key=lambda x: x.ordine):
                lines.append(f"  - {m.id} ({m.tipo}): {m.argomento[:70]}")
            lines.extend([
                "",
                f"Prossimi id suggeriti: lezione {next_mod}, quiz {next_quiz}, ordine da {next_ord}.",
                "VIETATO: imposta_corso, riesplorazione lunga, path assoluti su disco, script non necessari.",
                "Se obiettivo già raggiunto → rispondi solo testo di chiusura, zero tool.",
                "Altrimenti aggiungi SOLO le lezioni/quiz mancanti (1-2 tool per lezione).",
            ])
            lines.extend(_corpus_bootstrap_lines(ws, course))
        else:
            lines = [
                "Pianifica un corso microlearning completo in italiano.",
                "PATH: leggi /notes/percorsi_filesystem.md — usa solo /sources, /chunks, /reports (mai /home/...).",
                f"Obiettivo: ≥{threshold} lezioni (target {target_lez}, min {min_lez}) e ≥{min_quiz} quiz.",
                f"Piano strutturale: {plan_n} punti_taglio nel report — copri la maggior parte con lezioni dedicate.",
                f"Corso corrente (WORKSPACE_ROOT): {self.workspace_dir}",
                f"Libreria globale agente (condivisa): {shared}",
                f"Output JSON: {self.course_path.relative_to(ws) if self.course_path.is_relative_to(ws) else self.course_path}",
                "",
                "Materiali di QUESTO corso (sola lettura):",
            ]
            sid = detect_source_id(ws)
            for sub in ("sources", "chunks", "reports"):
                d = ws / sub
                if d.exists():
                    files = [p.name for p in sorted(d.iterdir()) if p.is_file()]
                    lines.append(f"  /{sub}/: " + ", ".join(files) if files else f"  /{sub}/: (vuoto)")
            if sid:
                lines.append("")
                lines.append(
                    f"Usa leggi_gerarchia_documento su reports/{sid}_hierarchy.json "
                    f"(NON leggere tutto il chunk index se non serve)."
                )
            lines.extend([
                "",
                "Esplorazione minima (1-2 tool), poi imposta_corso, poi lezioni+quiz.",
                "Non creare file in /notes con nomi di questo corso.",
            ])
            lines.extend(_corpus_bootstrap_lines(ws, course))

        return "\n".join(lines)

    @staticmethod
    def _message_content_text(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    parts.append(str(block.get("text") or block.get("content") or ""))
                else:
                    parts.append(str(block))
            return " ".join(p for p in parts if p).strip()
        return str(content).strip()

    def _log_stream_update(self, node: str, update: Any) -> None:
        if not isinstance(update, dict):
            return
        msgs = update.get("messages") or []
        if node == "model":
            for msg in msgs:
                if not isinstance(msg, AIMessage):
                    continue
                tool_calls = getattr(msg, "tool_calls", None) or []
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        name = tc.get("name") or "tool"
                        args = tc.get("args")
                    else:
                        name = getattr(tc, "name", None) or "tool"
                        args = getattr(tc, "args", None)
                    deep_agent_tool_call(name, args)
                text = self._message_content_text(getattr(msg, "content", None))
                if text and not tool_calls:
                    deep_agent_say(
                        f"Modello: {text[:220]}{'…' if len(text) > 220 else ''}",
                        kind="llm",
                    )
        elif node == "tools":
            for msg in msgs:
                if isinstance(msg, ToolMessage):
                    deep_agent_tool_result(
                        msg.name or "tool",
                        self._message_content_text(getattr(msg, "content", None)),
                    )

    def _invoke_agent_round(self, *, resume: bool, recursion_limit: int) -> list:
        inputs = {"messages": [HumanMessage(content=self._bootstrap_message(resume=resume))]}
        config = {"recursion_limit": recursion_limit}
        deep_agent_say(
            f"Avvio round ({'ripresa' if resume else 'nuovo'}), budget {recursion_limit} passi…",
            kind="phase",
        )
        final_state: dict | None = None
        for item in self._agent.stream(inputs, config=config, stream_mode=["updates", "values"]):
            if isinstance(item, tuple) and len(item) == 2:
                mode, payload = item
            else:
                mode, payload = "updates", item

            if mode == "values" and isinstance(payload, dict):
                final_state = payload
                continue
            if mode != "updates" or not isinstance(payload, dict):
                continue
            for node, update in payload.items():
                if "Middleware" in node or node.startswith("Patch"):
                    continue
                self._log_stream_update(node, update)

        return (final_state or {}).get("messages", [])

    def run(self) -> MicrolearningCourse:
        """Esegue il deep agent; riprende da disco e ripete fino a obiettivo o max round."""
        ws = Path(self.workspace_dir)
        min_lez, max_lez, min_quiz = _target_course_size(ws)
        threshold = _completion_lesson_threshold(min_lez, max_lez)
        max_rounds = int(os.getenv("MICROLEARNING_MAX_ROUNDS", "8"))
        cont_steps = int(os.getenv("MICROLEARNING_CONTINUATION_STEPS", "80"))

        with phase("microlearning_planning", workspace=self.workspace_dir):
            course = self._course_store.course
            lez, quiz = _count_modules(course)
            if _is_course_sufficient(
                course, workspace=ws, min_lez=min_lez, max_lez=max_lez, min_quiz=min_quiz,
            ):
                narrative(
                    f"Corso già completo: {lez} lezioni e {quiz} quiz "
                    f"(obiettivo ≥{threshold} lezioni, ≥{min_quiz} quiz).",
                    percent=phase_percent_for("microlearning_agent", 1.0),
                )
                return course

            if course.moduli:
                narrative(
                    f"Riprendo il corso esistente: {lez} lezioni, {quiz} quiz — "
                    f"obiettivo ≥{threshold} lezioni (target {max_lez}).",
                    percent=phase_percent_for("microlearning_agent", 0.05),
                )
            else:
                narrative(
                    "Esploro i materiali e compongo il corso in italiano (Deep Agent)…",
                    percent=phase_percent_for("microlearning_agent", 0.05),
                )

            t0 = time.perf_counter()
            total_ai_steps = 0

            for round_idx in range(1, max_rounds + 1):
                course = self._course_store.course
                if _is_course_sufficient(
                course, workspace=ws, min_lez=min_lez, max_lez=max_lez, min_quiz=min_quiz,
            ):
                    break

                resume = bool(course.moduli)
                budget = cont_steps if resume else self.max_steps
                narrative(
                    f"Round {round_idx}/{max_rounds}: budget {budget} passi "
                    f"({'ripresa' if resume else 'avvio'}).",
                    percent=phase_percent_for(
                        "microlearning_agent",
                        0.1 + (round_idx - 1) * 0.15,
                    ),
                )
                deep_agent_say(
                    f"Round {round_idx}/{max_rounds} — Deep Agent attivo.",
                    percent=phase_percent_for("microlearning_agent", 0.1 + (round_idx - 1) * 0.15),
                    kind="phase",
                )

                messages: list = []
                try:
                    messages = self._invoke_agent_round(
                        resume=resume,
                        recursion_limit=budget,
                    )
                except GraphRecursionError:
                    narrative(
                        f"Limite {budget} passi nel round {round_idx}: conservo il progresso su disco.",
                        level="warn",
                    )

                if self.course_path.exists():
                    try:
                        self._course_store.course = MicrolearningCourse(
                            **json.loads(self.course_path.read_text(encoding="utf-8")),
                        )
                    except (json.JSONDecodeError, OSError, ValueError):
                        pass

                if messages:
                    self._record_usage_from_messages(messages)
                    total_ai_steps += sum(
                        1
                        for m in messages
                        if isinstance(m, AIMessage)
                        and (getattr(m, "tool_calls", None) or getattr(m, "content", None))
                    )

                lez, quiz = _count_modules(self._course_store.course)
                if _is_course_sufficient(
                    self._course_store.course,
                    workspace=ws,
                    min_lez=min_lez,
                    max_lez=max_lez,
                    min_quiz=min_quiz,
                ):
                    narrative(
                        f"Obiettivo raggiunto dopo il round {round_idx}.",
                        percent=phase_percent_for("microlearning_agent", 0.95),
                    )
                    break

            elapsed = time.perf_counter() - t0
            course = self._course_store.course
            lez, quiz = _count_modules(course)
            if not _is_course_sufficient(
                course, workspace=ws, min_lez=min_lez, max_lez=max_lez, min_quiz=min_quiz,
            ):
                narrative(
                    f"Dopo {max_rounds} round: {lez} lezioni e {quiz} quiz "
                    f"(obiettivo ≥{threshold}, target {max_lez}). Rilancia microlearning per continuare "
                    f"o alza MICROLEARNING_MAX_STEPS / MICROLEARNING_MAX_ROUNDS.",
                    level="warn",
                )

            narrative(
                f"Microlearning in {int(elapsed)} s ({total_ai_steps} turni modello totali).",
                percent=phase_percent_for("microlearning_agent", 0.98),
            )
            self.llm_usage.log_summary()
            n_fix = _completa_lezioni_da_fonte(course, ws)
            if n_fix:
                narrative(
                    f"Ho arricchito {n_fix} lezioni con testo dalla fonte (contenuto troppo corto).",
                )
                self._course_store.course = course
                self._course_store._flush("post_arricchimento", silent=True)

            n_lez = sum(1 for m in course.moduli if m.tipo == "lezione")
            n_quiz = sum(1 for m in course.moduli if m.tipo == "quiz")
            narrative(
                f"Corso «{course.titolo_corso}»: {n_lez} lezioni, {n_quiz} quiz.",
                percent=phase_percent_for("microlearning_agent", 1.0),
            )
            return course


if __name__ == "__main__":
    os.chdir(BACKEND_ROOT)
    setup_logging()

    workspace = os.getenv(
        "MICROLEARNING_WORKSPACE",
        str(BACKEND_ROOT / "workspace" / "think_python"),
    )
    agent = MicrolearningPlanningAgent(workspace_dir=workspace)
    corso = agent.run()
    print(json.dumps(corso.model_dump(), indent=2, ensure_ascii=False)[:2000])
