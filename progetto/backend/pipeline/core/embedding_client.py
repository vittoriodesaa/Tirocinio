"""
Embedding via OpenRouter (API compatibile OpenAI /v1/embeddings).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from pipeline.paths import ENV_FILE

load_dotenv(ENV_FILE)

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1"


def resolve_embedding_model() -> str:
    return os.getenv(
        "OPENROUTER_EMBEDDING_MODEL",
        "openai/text-embedding-3-small",
    ).strip()


def embedding_batch_size() -> int:
    raw = os.getenv("CORPUS_EMBEDDING_BATCH_SIZE", "48").strip()
    try:
        return max(1, min(128, int(raw)))
    except ValueError:
        return 48


def _client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY mancante: necessaria per gli embedding del piano corpus."
        )
    return OpenAI(api_key=api_key, base_url=OPENROUTER_EMBEDDINGS_URL)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


class EmbeddingCache:
    """Cache locale per evitare richieste duplicate durante il planning corpus."""

    def __init__(self, path: Path, model: str):
        self.path = path
        self.model = model
        self._vectors: dict[str, List[float]] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("model") == model:
                    self._vectors = data.get("vectors") or {}
            except (json.JSONDecodeError, OSError):
                self._vectors = {}

    def get(self, text: str) -> Optional[List[float]]:
        return self._vectors.get(_text_hash(text))

    def set(self, text: str, vector: List[float]) -> None:
        self._vectors[_text_hash(text)] = vector

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"model": self.model, "vectors": self._vectors}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )


def embed_texts(
    texts: List[str],
    *,
    model: Optional[str] = None,
    cache: Optional[EmbeddingCache] = None,
) -> List[List[float]]:
    """Calcola embedding per ogni testo; riusa la cache quando possibile."""
    if not texts:
        return []

    model = model or resolve_embedding_model()
    out: List[Optional[List[float]]] = [None] * len(texts)
    pending_idx: List[int] = []
    pending_texts: List[str] = []

    for i, text in enumerate(texts):
        if cache is not None:
            hit = cache.get(text)
            if hit is not None:
                out[i] = hit
                continue
        pending_idx.append(i)
        pending_texts.append(text)

    if pending_texts:
        client = _client()
        batch = embedding_batch_size()
        for start in range(0, len(pending_texts), batch):
            chunk = pending_texts[start : start + batch]
            response = client.embeddings.create(model=model, input=chunk)
            ordered = sorted(response.data, key=lambda d: d.index)
            for j, row in enumerate(ordered):
                vec = list(row.embedding)
                global_i = pending_idx[start + j]
                out[global_i] = vec
                if cache is not None:
                    cache.set(texts[global_i], vec)

    if cache is not None:
        cache.save()

    return [v if v is not None else [] for v in out]
