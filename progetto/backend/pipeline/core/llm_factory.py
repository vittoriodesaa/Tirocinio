"""
Factory LLM: OpenRouter (default) o Groq con rate limiter.
"""
from __future__ import annotations

import os
from typing import Tuple

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter


def resolve_llm_max_workers(provider: str) -> str:
    """
    Worker LLM per DocumentAgent (analisi parallele).
    - OpenRouter: tutte in parallelo (max) se LLM_MAX_WORKERS non è impostato.
    - Groq: default conservativo (rate limit); override con LLM_MAX_WORKERS.
    """
    explicit = os.getenv("LLM_MAX_WORKERS", "").strip()
    if explicit:
        return explicit
    if provider == "openrouter":
        return "max"
    return os.getenv("GROQ_LLM_MAX_WORKERS", "12").strip() or "12"


def resolve_llm_provider() -> str:
    """openrouter | groq. Se LLM_PROVIDER non è impostato, inferisce dalle API key."""
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit in ("openrouter", "groq"):
        return explicit
    if os.getenv("GROQ_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
        return "groq"
    return "openrouter"


def _groq_rate_limiter() -> InMemoryRateLimiter:
    """Limite richieste Groq (default ~30 RPM sul tier free)."""
    rps = float(os.getenv("GROQ_REQUESTS_PER_SECOND", "0.5"))
    max_bucket = float(os.getenv("GROQ_RATE_LIMITER_MAX_BUCKET", "1"))
    return InMemoryRateLimiter(
        requests_per_second=rps,
        check_every_n_seconds=0.1,
        max_bucket_size=max_bucket,
    )


def create_chat_model() -> Tuple[BaseChatModel, str, str]:
    """
    Restituisce (llm, model_name, provider).
    provider è 'openrouter' o 'groq'.
    """
    provider = resolve_llm_provider()

    if provider == "groq":
        from langchain_groq import ChatGroq

        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "1024"))
        llm = ChatGroq(
            model=model,
            temperature=0,
            max_tokens=max_tokens,
            api_key=os.getenv("GROQ_API_KEY"),
            rate_limiter=_groq_rate_limiter(),
        )
        return llm, model, provider

    from langchain_openai import ChatOpenAI

    model = os.getenv(
        "OPENROUTER_MODEL",
        "meta-llama/llama-3.1-8b-instruct",
    )
    llm = ChatOpenAI(
        model=model,
        temperature=0,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )
    return llm, model, "openrouter"
