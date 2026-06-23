"""
Configurazione effettiva: variabili in .env vs default del codice.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from pipeline.core.llm_factory import create_chat_model, resolve_llm_max_workers, resolve_llm_provider

from pipeline.paths import BACKEND_ROOT, ENV_FILE

_ENV_PATH = ENV_FILE

load_dotenv(_ENV_PATH)

_SECRET_KEYS = frozenset(
    k.lower()
    for k in (
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "API_KEY",
        "SECRET",
        "PASSWORD",
        "TOKEN",
    )
)


def _is_secret(name: str) -> bool:
    n = name.lower()
    return any(s in n for s in _SECRET_KEYS)


def _mask(name: str, value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if not _is_secret(name):
        return value
    if len(value) <= 12:
        return "***"
    return f"{value[:10]}…{value[-4:]} (len={len(value)})"


def _parse_env_file() -> dict[str, str]:
    """Solo righe attive nel file .env (non i commenti)."""
    if not _ENV_PATH.exists():
        return {}
    out: dict[str, str] = {}
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        key, _, val = s.partition("=")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def _entry(
    name: str,
    *,
    default: Any = None,
    effective: Any = None,
    in_file: dict[str, str],
) -> dict[str, Any]:
    file_val = in_file.get(name)
    env_val = os.getenv(name)
    eff = effective if effective is not None else (env_val if env_val is not None else default)
    if file_val is not None:
        source = "file .env"
    elif env_val is not None:
        source = "variabile d'ambiente (non nel file)"
    elif default is not None:
        source = "default codice"
    else:
        source = "non impostata"

    return {
        "nome": name,
        "fonte": source,
        "nel_file_env": _mask(name, file_val) if file_val else None,
        "in_processo": _mask(name, env_val) if env_val else None,
        "effettivo": _mask(name, str(eff)) if eff is not None and str(eff) != "" else None,
    }


def get_config_report() -> dict[str, Any]:
    in_file = _parse_env_file()
    provider = resolve_llm_provider()
    try:
        _, model, prov = create_chat_model()
    except Exception as e:
        model = f"(errore init: {e})"
        prov = provider
    workers = resolve_llm_max_workers(prov)

    openrouter_key = bool(os.getenv("OPENROUTER_API_KEY"))
    groq_key = bool(os.getenv("GROQ_API_KEY"))

    provider_note = "LLM_PROVIDER nel .env" if in_file.get("LLM_PROVIDER") else (
        "inferito: Groq (solo GROQ_API_KEY)"
        if groq_key and not openrouter_key
        else "inferito: OpenRouter (default o OPENROUTER_API_KEY)"
    )

    workers_note = (
        "LLM_MAX_WORKERS nel .env"
        if in_file.get("LLM_MAX_WORKERS") or os.getenv("LLM_MAX_WORKERS")
        else (
            f"default per {prov}: tutte in parallelo (max)"
            if prov == "openrouter"
            else "default per groq: 12 (GROQ_LLM_MAX_WORKERS)"
        )
    )

    sections = {
        "llm": {
            "provider_effettivo": prov,
            "modello_effettivo": model,
            "nota_provider": provider_note,
            "llm_max_workers_effettivo": workers,
            "nota_workers": workers_note,
            "chiavi": {
                "OPENROUTER_API_KEY": "presente" if openrouter_key else "assente",
                "GROQ_API_KEY": "presente" if groq_key else "assente",
            },
            "variabili": [
                _entry("LLM_PROVIDER", in_file=in_file),
                _entry("OPENROUTER_API_KEY", in_file=in_file),
                _entry("OPENROUTER_MODEL", default="meta-llama/llama-3.1-8b-instruct", effective=model if prov == "openrouter" else None, in_file=in_file),
                _entry("OPENROUTER_EMBEDDING_MODEL", default="openai/text-embedding-3-small", in_file=in_file),
                _entry("GROQ_API_KEY", in_file=in_file),
                _entry("GROQ_MODEL", default="llama-3.1-8b-instant", in_file=in_file),
                _entry("GROQ_MAX_TOKENS", default="1024", in_file=in_file),
                _entry("GROQ_REQUESTS_PER_SECOND", default="0.5", in_file=in_file),
                _entry("LLM_MAX_WORKERS", effective=workers, in_file=in_file),
                _entry("GROQ_LLM_MAX_WORKERS", default="12", in_file=in_file),
            ],
        },
        "logging": {
            "variabili": [
                _entry("LOG_LEVEL", default="INFO", effective=os.getenv("LOG_LEVEL", "INFO"), in_file=in_file),
                _entry("LOG_VERBOSE", default="0 (disattivo)", effective="1" if os.getenv("LOG_VERBOSE", "").lower() in ("1", "true", "yes") else "0", in_file=in_file),
                _entry("OPENROUTER_INPUT_PRICE_PER_M", in_file=in_file),
                _entry("OPENROUTER_OUTPUT_PRICE_PER_M", in_file=in_file),
            ],
        },
        "pipeline": {
            "variabili": [
                _entry("PLANNING_MIN_WORDS", default="80", in_file=in_file),
                _entry("CORPUS_EMBEDDING_MIN_SIMILARITY", default="0.28", in_file=in_file),
                _entry("CORPUS_EMBEDDING_SNIPPET_CHARS", default="1000", in_file=in_file),
                _entry("CORPUS_EMBEDDING_BATCH_SIZE", default="48", in_file=in_file),
                _entry("VALIDATION_USE_LLM", default="off", in_file=in_file),
                _entry("MICROLEARNING_MAX_STEPS", default="(auto)", in_file=in_file),
                _entry("MICROLEARNING_TARGET_MAX_LESSONS", default="40", in_file=in_file),
                _entry("MICROLEARNING_TARGET_LESSONS_CAP", default="120", in_file=in_file),
                _entry("MICRO_MIN_CONTENUTO_CHARS", default="500", in_file=in_file),
                _entry("MICRO_MIN_QUIZ_DOMANDE", default="3", in_file=in_file),
                _entry("MICRO_MIN_H2_SECTIONS", default="3", in_file=in_file),
            ],
        },
    }

    return {
        "env_file": str(_ENV_PATH),
        "env_file_esiste": _ENV_PATH.exists(),
        "righe_attive_nel_file": len(in_file),
        "chiavi_nel_file": sorted(in_file.keys()),
        "sezioni": sections,
        "sintesi": {
            "provider": prov,
            "modello": model,
            "parallelismo_llm": workers,
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
        },
    }
