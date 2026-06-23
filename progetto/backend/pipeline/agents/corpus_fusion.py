"""
Fusione semantica dei punti_taglio multi-libro per il piano corpus.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from pipeline.core.embedding_client import (
    EmbeddingCache,
    cosine_similarity,
    embed_texts,
    resolve_embedding_model,
)
from pipeline.core.workspace_io import read_lines
from pipeline.models.schemas import PuntoTaglio, SegmentoFonte

FusedGroup = Tuple[List[SegmentoFonte], List[str], int, float]


@dataclass(frozen=True)
class _IndexedPunto:
    bucket_idx: int
    punto_idx: int
    source_id: str
    markdown: str
    punto: PuntoTaglio
    embed_text: str
    embedding: List[float]


def _snippet_chars() -> int:
    raw = os.getenv("CORPUS_EMBEDDING_SNIPPET_CHARS", "1000").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 1000


def _min_similarity() -> float:
    raw = os.getenv("CORPUS_EMBEDDING_MIN_SIMILARITY", "0.28").strip()
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.28


def _make_segmento(source_id: str, markdown: str, pt: PuntoTaglio) -> SegmentoFonte:
    return SegmentoFonte(
        source_id=source_id,
        markdown_sorgente=markdown,
        riga_inizio=pt.riga_inizio,
        riga_fine=pt.riga_fine,
        titolo_originale=pt.titolo,
    )


def _read_snippet(ws: Path, markdown: str, start: int, end: int, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    path = ws / markdown
    if not path.exists():
        for name in (markdown, f"sources/{Path(markdown).name}"):
            candidate = ws / name
            if candidate.exists():
                path = candidate
                break
        else:
            return ""
    lines = read_lines(path)
    lo = max(1, start)
    hi = min(len(lines), end)
    text = "\n".join(lines[lo - 1 : hi]).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:max_chars]


def build_punto_embed_text(ws: Path, markdown: str, pt: PuntoTaglio) -> str:
    """Testo da embeddare: titolo, concetti e estratto del segmento."""
    parts = [pt.titolo.strip()]
    if pt.concetti_chiave:
        clean = [c for c in pt.concetti_chiave if c and len(c) > 2][:10]
        if clean:
            parts.append("Concetti: " + ", ".join(clean))
    snippet = _read_snippet(ws, markdown, pt.riga_inizio, pt.riga_fine, _snippet_chars())
    if snippet:
        parts.append(snippet)
    return "\n".join(parts)


def _group_metrics(segmenti: List[SegmentoFonte], concetti: List[str], durata: int, carico: float) -> FusedGroup:
    return (segmenti, concetti, durata, carico)


def _merge_segmenti(
    segmenti: List[SegmentoFonte],
    concetti: List[str],
    durata: int,
    carico: float,
    seg: SegmentoFonte,
    pt: PuntoTaglio,
) -> FusedGroup:
    segmenti = segmenti + [seg]
    concetti = list(dict.fromkeys(concetti + list(pt.concetti_chiave)))[:16]
    durata += pt.durata_stimata_minuti
    carico = max(carico, pt.carico_cognitivo)
    return segmenti, concetti, durata, carico


def fuse_buckets_semantic(
    ws: Path,
    buckets: List[tuple[str, str, List[PuntoTaglio]]],
) -> List[FusedGroup]:
    """
    Accoppia i punti_taglio tra libri per similarità semantica (embedding OpenRouter).
    La sorgente primaria (primo bucket) definisce l'ordine pedagogico.
    """
    if len(buckets) <= 1:
        fused: List[FusedGroup] = []
        for sid, md, pts in buckets:
            for pt in pts:
                seg = _make_segmento(sid, md, pt)
                fused.append(_group_metrics([seg], list(pt.concetti_chiave), pt.durata_stimata_minuti, pt.carico_cognitivo))
        return fused

    model = resolve_embedding_model()
    cache_path = ws / "reports" / "corpus_embeddings_cache.json"
    cache = EmbeddingCache(cache_path, model)

    indexed: List[_IndexedPunto] = []
    embed_inputs: List[str] = []
    for bi, (sid, md, pts) in enumerate(buckets):
        for pi, pt in enumerate(pts):
            text = build_punto_embed_text(ws, md, pt)
            indexed.append(
                _IndexedPunto(
                    bucket_idx=bi,
                    punto_idx=pi,
                    source_id=sid,
                    markdown=md,
                    punto=pt,
                    embed_text=text,
                    embedding=[],
                )
            )
            embed_inputs.append(text)

    vectors = embed_texts(embed_inputs, model=model, cache=cache)
    indexed = [
        _IndexedPunto(
            bucket_idx=item.bucket_idx,
            punto_idx=item.punto_idx,
            source_id=item.source_id,
            markdown=item.markdown,
            punto=item.punto,
            embed_text=item.embed_text,
            embedding=vectors[i],
        )
        for i, item in enumerate(indexed)
    ]

    by_bucket: List[List[_IndexedPunto]] = [[] for _ in buckets]
    for item in indexed:
        by_bucket[item.bucket_idx].append(item)

    min_sim = _min_similarity()
    used: List[set[int]] = [set() for _ in buckets]
    groups: List[dict] = []

    primary = by_bucket[0]
    for anchor in primary:
        bi = anchor.bucket_idx
        used[bi].add(anchor.punto_idx)
        segmenti = [_make_segmento(anchor.source_id, anchor.markdown, anchor.punto)]
        concetti = list(anchor.punto.concetti_chiave)
        durata = anchor.punto.durata_stimata_minuti
        carico = anchor.punto.carico_cognitivo

        for other_bi in range(1, len(buckets)):
            best: _IndexedPunto | None = None
            best_sim = -1.0
            for cand in by_bucket[other_bi]:
                if cand.punto_idx in used[other_bi]:
                    continue
                sim = cosine_similarity(anchor.embedding, cand.embedding)
                if sim > best_sim:
                    best_sim = sim
                    best = cand
            if best is not None and best_sim >= min_sim:
                used[other_bi].add(best.punto_idx)
                segmenti, concetti, durata, carico = _merge_segmenti(
                    segmenti, concetti, durata, carico,
                    _make_segmento(best.source_id, best.markdown, best.punto),
                    best.punto,
                )

        groups.append(
            {
                "order_key": anchor.punto_idx,
                "segmenti": segmenti,
                "concetti": concetti,
                "durata": durata,
                "carico": carico,
                "anchor_emb": anchor.embedding,
            }
        )

    # Seconda passata: punti non ancora usati → unisci al gruppo più simile se possibile
    orphans: List[_IndexedPunto] = []
    for bi in range(1, len(buckets)):
        for item in by_bucket[bi]:
            if item.punto_idx not in used[bi]:
                orphans.append(item)

    for orphan in sorted(orphans, key=lambda x: (x.bucket_idx, x.punto_idx)):
        best_gi: int | None = None
        best_sim = -1.0
        for gi, group in enumerate(groups):
            if any(s.source_id == orphan.source_id for s in group["segmenti"]):
                continue
            sim = cosine_similarity(orphan.embedding, group["anchor_emb"])
            if sim > best_sim:
                best_sim = sim
                best_gi = gi
        if best_gi is not None and best_sim >= min_sim:
            g = groups[best_gi]
            seg = _make_segmento(orphan.source_id, orphan.markdown, orphan.punto)
            seg_list, conc, dur, car = _merge_segmenti(
                g["segmenti"], g["concetti"], g["durata"], g["carico"], seg, orphan.punto,
            )
            g["segmenti"] = seg_list
            g["concetti"] = conc
            g["durata"] = dur
            g["carico"] = car
            used[orphan.bucket_idx].add(orphan.punto_idx)
        else:
            groups.append(
                {
                    "order_key": 10_000 + orphan.punto_idx,
                    "segmenti": [_make_segmento(orphan.source_id, orphan.markdown, orphan.punto)],
                    "concetti": list(orphan.punto.concetti_chiave),
                    "durata": orphan.punto.durata_stimata_minuti,
                    "carico": orphan.punto.carico_cognitivo,
                    "anchor_emb": orphan.embedding,
                }
            )
            used[orphan.bucket_idx].add(orphan.punto_idx)

    groups.sort(key=lambda g: g["order_key"])
    return [
        _group_metrics(g["segmenti"], g["concetti"], g["durata"], g["carico"])
        for g in groups
    ]
