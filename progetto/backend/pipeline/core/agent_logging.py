"""
Log in linguaggio naturale + avanzamento percentuale per pipeline e UI.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

# Logger tecnico (solo errori/debug se LOG_VERBOSE=1)
_technical = logging.getLogger("pipeline.technical")
_user = logging.getLogger("pipeline")

_current_run: ContextVar[Optional["RunLog"]] = ContextVar("pipeline_run", default=None)

# Peso % sulla pipeline totale (inizio, fine)
_PIPELINE_WEIGHTS: dict[str, tuple[float, float]] = {
    "acquisition": (0, 8),
    "document_agent": (8, 52),
    "planning_agent": (52, 65),
    "segmentation_agent": (65, 78),
    "validation_agent": (78, 92),
    "microlearning_agent": (92, 100),
}

_PHASE_MESSAGES: dict[str, tuple[str, str]] = {
    "acquisition": ("Acquisizione", "Sto registrando il file che hai caricato…"),
    "document_agent": ("Conversione", "Sto convertendo il libro in testo e preparando i capitoli…"),
    "estrazione_testo": ("Estrazione", "Sto estraendo il testo dal documento…"),
    "normalizzazione": ("Pulizia", "Sto ripulendo e sistemando il testo…"),
    "analisi_struttura": ("Struttura", "Sto analizzando titoli e sezioni del documento…"),
    "llm_globale": ("Analisi IA", "Sto analizzando qualità e sintesi con l'intelligenza artificiale…"),
    "planning_agent": ("Pianificazione", "Sto costruendo la mappa del corso e i punti di taglio…"),
    "planning": ("Pianificazione", "Sto calcolando carico cognitivo e durata delle lezioni…"),
    "segmentation_agent": ("Segmentazione", "Sto dividendo il testo in moduli didattici…"),
    "segmentation": ("Segmentazione", "Sto tagliando il contenuto secondo il piano…"),
    "validation_agent": ("Validazione", "Sto controllando coerenza e prerequisiti…"),
    "validation": ("Validazione", "Sto verificando che ogni modulo sia comprensibile da solo…"),
    "microlearning_agent": ("Microlearning", "Sto progettando il corso microlearning in italiano…"),
    "microlearning_planning": ("Microlearning", "Sto esplorando il materiale e scrivendo le lezioni…"),
}


def setup_logging(level: str | None = None) -> None:
    lvl_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    level_num = getattr(logging, lvl_name, logging.INFO)
    verbose = os.getenv("LOG_VERBOSE", "").lower() in ("1", "true", "yes")

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.WARNING,
            format="%(message)s",
            datefmt="%H:%M:%S",
        )

    _user.setLevel(level_num)
    _technical.setLevel(logging.DEBUG if verbose else logging.ERROR)

    # Silenzia rumore HTTP/OpenAI/LangChain (non è log per l'utente)
    for noisy in (
        "httpx", "httpcore", "openai", "langchain", "langchain_core",
        "langchain_openai", "langchain_groq", "urllib3", "uvicorn", "uvicorn.error",
        "fastapi", "main",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING if verbose else logging.ERROR)

    for h in logging.getLogger().handlers:
        if not verbose:
            h.addFilter(lambda r: r.name == "pipeline")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_clock() -> str:
    return datetime.now().strftime("%H:%M:%S")


@dataclass
class LogEntry:
    time: str
    message: str
    percent: float = 0.0
    level: str = "info"
    channel: str = "pipeline"  # pipeline | deep_agent
    kind: str = "info"  # info | phase | tool_call | tool_result | llm


@dataclass
class RunLog:
    """Log narrativo di una esecuzione pipeline (per UI e file)."""
    course_id: str
    entries: list[LogEntry] = field(default_factory=list)
    percent: float = 0.0
    status: str = "idle"  # idle | running | done | error
    result: Optional[dict] = None
    error: Optional[str] = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _log_path: Optional[Path] = field(default=None, repr=False)

    def bind_workspace(self, workspace_dir: str | Path) -> None:
        ws = Path(workspace_dir)
        self._log_path = ws / "activity.log"

    def say(
        self,
        message: str,
        *,
        percent: Optional[float] = None,
        level: str = "info",
        channel: str = "pipeline",
        kind: str = "info",
    ) -> None:
        with self._lock:
            if percent is not None:
                self.percent = min(100.0, max(0.0, percent))
            entry = LogEntry(
                time=_now_clock(),
                message=message,
                percent=self.percent,
                level=level,
                channel=channel,
                kind=kind,
            )
            self.entries.append(entry)
            if len(self.entries) > 800:
                self.entries = self.entries[-600:]

        prefix = "🤖 " if channel == "deep_agent" else ""
        line = f"[{entry.percent:5.1f}%] {prefix}{message}"
        if level == "error":
            _user.error(line)
        elif level == "warn":
            _user.warning(line)
        else:
            _user.info(line)

        if self._log_path:
            try:
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass

    def snapshot(self) -> dict:
        with self._lock:
            recent = self.entries[-120:]
            deep = [e for e in recent if e.channel == "deep_agent"]
            return {
                "course_id": self.course_id,
                "status": self.status,
                "percent": round(self.percent, 1),
                "error": self.error,
                "has_result": self.result is not None,
                "entries": [
                    {
                        "time": e.time,
                        "message": e.message,
                        "percent": e.percent,
                        "level": e.level,
                        "channel": e.channel,
                        "kind": e.kind,
                    }
                    for e in self.entries[-80:]
                ],
                "deep_agent_entries": [
                    {
                        "time": e.time,
                        "message": e.message,
                        "percent": e.percent,
                        "level": e.level,
                        "kind": e.kind,
                    }
                    for e in deep[-100:]
                ],
            }


# Registry globale per polling UI
_active_runs: dict[str, RunLog] = {}
_runs_lock = threading.Lock()


def start_run(course_id: str, workspace_dir: Optional[str] = None) -> RunLog:
    run = RunLog(course_id=course_id, status="running", percent=0.0)
    if workspace_dir:
        run.bind_workspace(workspace_dir)
        Path(workspace_dir, "activity.log").write_text("", encoding="utf-8")
    with _runs_lock:
        _active_runs[course_id] = run
    _current_run.set(run)
    run.say(f"Inizio lavorazione del corso «{course_id}».", percent=0)
    return run


def finish_run(
    course_id: str,
    success: bool = True,
    message: str = "",
    *,
    result: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    with _runs_lock:
        run = _active_runs.get(course_id)
    if not run:
        return
    run.status = "done" if success else "error"
    run.result = result
    run.error = error
    if message:
        run.say(message, percent=100.0 if success else run.percent, level="info" if success else "error")
    elif success:
        run.say("Ho finito: il corso è pronto.", percent=100.0)
    elif error:
        run.say(f"Operazione interrotta: {error}", level="error")
    _current_run.set(None)


def get_run(course_id: str) -> Optional[RunLog]:
    with _runs_lock:
        return _active_runs.get(course_id)


def narrative(message: str, *, percent: Optional[float] = None, level: str = "info") -> None:
    """Messaggio in linguaggio naturale se c'è una run attiva."""
    run = _current_run.get()
    if run:
        run.say(message, percent=percent, level=level)
    elif level == "error":
        _user.error(message)
    else:
        _user.info(message)


def _brief_tool_args(args: Any, *, max_len: int = 120) -> str:
    if not args:
        return ""
    try:
        import json

        s = json.dumps(args, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(args)
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def deep_agent_say(
    message: str,
    *,
    percent: Optional[float] = None,
    level: str = "info",
    kind: str = "info",
) -> None:
    """Log dedicato al deep agent (UI sezione live)."""
    run = _current_run.get()
    if run:
        run.say(
            message,
            percent=percent,
            level=level,
            channel="deep_agent",
            kind=kind,
        )
    elif level == "error":
        _user.error(f"[deep] {message}")
    else:
        _user.info(f"[deep] {message}")


def deep_agent_tool_call(name: str, args: Any, *, percent: Optional[float] = None) -> None:
    brief = _brief_tool_args(args)
    msg = f"→ {name}({brief})" if brief else f"→ {name}()"
    deep_agent_say(msg, percent=percent, kind="tool_call")


def deep_agent_tool_result(name: str, preview: str, *, percent: Optional[float] = None) -> None:
    text = (preview or "").replace("\n", " ").strip()
    if len(text) > 160:
        text = text[:159] + "…"
    deep_agent_say(f"✓ {name}: {text or '(vuoto)'}", percent=percent, kind="tool_result")


def narrative_llm_done(
    cosa: str,
    *,
    durata_s: float,
    percent: Optional[float] = None,
) -> None:
    sec = int(durata_s)
    narrative(f"Ho completato «{cosa}» in {sec} secondi.", percent=percent)


def narrative_llm_batch(done: int, total: int, label: str = "analisi") -> None:
    if total <= 0:
        return
    pct = int(done / total * 100)
    narrative(
        f"Sto ancora con l'{label}: completate {done} su {total} richieste ({pct}%).",
    )


def phase_percent_for(name: str, sub: float = 0.0) -> float:
    """sub in [0,1] avanzamento dentro la fase."""
    bounds = _PIPELINE_WEIGHTS.get(name)
    if not bounds:
        return sub * 100
    lo, hi = bounds
    return lo + (hi - lo) * max(0.0, min(1.0, sub))


@contextmanager
def phase(name: str, **details: Any) -> Iterator[None]:
    """Fase con messaggio naturale in italiano."""
    title, start_msg = _PHASE_MESSAGES.get(name, (name, f"Sto eseguendo {name}…"))
    pct_start = phase_percent_for(name, 0.0)

    extra = ""
    if details.get("source_id"):
        extra = f" (documento {details['source_id']})"
    elif details.get("course"):
        extra = f" (corso {details['course']})"

    narrative(f"▸ {title}{extra}: {start_msg}", percent=pct_start)
    t0 = time.perf_counter()
    try:
        yield
    except Exception as exc:
        narrative(
            f"✗ Qualcosa è andato storto durante «{title}»: {exc}",
            percent=pct_start,
            level="error",
        )
        _technical.exception("Errore in fase %s", name)
        raise
    else:
        elapsed = time.perf_counter() - t0
        sec = int(elapsed)
        narrative(
            f"✓ {title} completato in {sec} s.",
            percent=phase_percent_for(name, 1.0),
        )


# --- LLM usage (riepilogo naturale) ---


@dataclass
class LLMCallRecord:
    operation: str
    model: str
    started_at: str
    duration_s: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: Optional[float] = None
    prompt_chars: int = 0


@dataclass
class LLMUsageAccumulator:
    model: str = ""
    calls: list[LLMCallRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.calls)

    @property
    def completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return sum(c.total_tokens for c in self.calls)

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd or 0.0 for c in self.calls)

    def add(self, record: LLMCallRecord) -> None:
        with self._lock:
            self.calls.append(record)
            if record.model:
                self.model = record.model

    def log_summary(self) -> None:
        if not self.calls:
            narrative("Non ho usato l'IA in questa fase.", percent=None)
            return
        cost = self.total_cost_usd
        cost_txt = f"circa ${cost:.4f}" if cost else "costo non disponibile"
        narrative(
            f"Riepilogo IA: {len(self.calls)} chiamate, "
            f"{self.total_tokens:,} token totali, {cost_txt}.",
        )


def _parse_token_usage(metadata: dict) -> dict[str, int]:
    usage = metadata.get("token_usage") or metadata.get("usage") or {}
    if not isinstance(usage, dict):
        return {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def _parse_cost_usd(metadata: dict, tokens: dict[str, int], model: str) -> Optional[float]:
    candidates: list[Any] = [
        metadata.get("total_cost"),
        metadata.get("cost"),
        metadata.get("generation_cost"),
    ]
    usage = metadata.get("token_usage")
    if isinstance(usage, dict):
        candidates.append(usage.get("cost"))
        candidates.append(usage.get("total_cost"))
    for val in candidates:
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    inp_m = os.getenv("OPENROUTER_INPUT_PRICE_PER_M") or os.getenv("GROQ_INPUT_PRICE_PER_M")
    out_m = os.getenv("OPENROUTER_OUTPUT_PRICE_PER_M") or os.getenv("GROQ_OUTPUT_PRICE_PER_M")
    if inp_m and out_m:
        try:
            return (
                float(inp_m) / 1_000_000 * tokens.get("prompt_tokens", 0)
                + float(out_m) / 1_000_000 * tokens.get("completion_tokens", 0)
            )
        except ValueError:
            pass
    return None


def _friendly_operation(operation: str) -> str:
    m = {
        "routing_estrattore": "scelta del formato file",
        "ispezione_qualita": "controllo qualità del testo",
        "sintesi_carrello": "sintesi di un blocco",
        "sintesi_strutturata": "sintesi di un capitolo",
    }
    for k, v in m.items():
        if k in operation:
            return v
    if operation.startswith("sintesi_strutturata:"):
        return "sintesi capitolo"
    if "microlearning" in operation:
        return "pianificazione lezione"
    if "validazione" in operation:
        return "controllo modulo"
    return operation.replace("_", " ")


def record_llm_response(
    accumulator: LLMUsageAccumulator,
    *,
    operation: str,
    model: str,
    duration_s: float,
    prompt_chars: int,
    raw_message: Any = None,
    progress: Optional[tuple[int, int]] = None,
) -> None:
    meta: dict = {}
    if raw_message is not None:
        meta = getattr(raw_message, "response_metadata", None) or {}
        if not isinstance(meta, dict):
            meta = {}
        usage_meta = getattr(raw_message, "usage_metadata", None)
        if usage_meta:
            um = usage_meta if isinstance(usage_meta, dict) else (
                usage_meta.model_dump() if hasattr(usage_meta, "model_dump") else {}
            )
            for k, v in um.items():
                if k not in meta and v is not None:
                    meta[k] = v

    tokens = _parse_token_usage(meta)
    if tokens.get("total_tokens", 0) == 0:
        tokens["total_tokens"] = tokens.get("prompt_tokens", 0) + tokens.get("completion_tokens", 0)

    cost = _parse_cost_usd(meta, tokens, model)
    record = LLMCallRecord(
        operation=operation,
        model=model,
        started_at=_now_iso(),
        duration_s=duration_s,
        prompt_tokens=tokens.get("prompt_tokens", 0),
        completion_tokens=tokens.get("completion_tokens", 0),
        total_tokens=tokens.get("total_tokens", 0),
        cost_usd=cost,
        prompt_chars=prompt_chars,
    )
    accumulator.add(record)

    cosa = _friendly_operation(operation)
    pct = None
    if progress:
        done, total = progress
        sub = done / total if total else 1.0
        pct = phase_percent_for("llm_globale", sub)
        if done % max(1, total // 5) == 0 or done == total:
            narrative_llm_batch(done, total, cosa)
            return

    narrative_llm_done(cosa, durata_s=duration_s, percent=pct)


# Retrocompatibilità
logger = _user
