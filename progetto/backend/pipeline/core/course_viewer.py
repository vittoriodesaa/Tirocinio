"""
Dati per grafo e catalogo del corso microlearning (solo microlearning_course.json).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pipeline.core.workspace_io import load_json


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _resolve_prereq(
    ref: str,
    by_id: dict[str, dict],
    by_label: dict[str, str],
    by_ordine: dict[int, str],
) -> str | None:
    ref = (ref or "").strip()
    if not ref:
        return None
    if ref in by_id:
        return ref
    low = _norm(ref)
    if low in by_label:
        return by_label[low]
    m = re.match(r"pt_(\d+)", ref, re.I)
    if m and int(m.group(1)) in by_ordine:
        return by_ordine[int(m.group(1))]
    return None


def _modulo_label(m: dict) -> str:
    t = m.get("tipo", "lezione")
    tit = (m.get("argomento") or m.get("titolo") or m.get("id") or "Modulo").strip()
    if t == "quiz":
        return f"Quiz: {tit}" if not tit.lower().startswith("quiz") else tit
    return tit


def _modulo_body(m: dict) -> str:
    if m.get("tipo") == "quiz":
        return ""
    if m.get("contenuto"):
        return m["contenuto"]
    if m.get("sintesi_breve"):
        return m["sintesi_breve"]
    return (m.get("sintesi") or m.get("testo") or "").strip()


def build_course_viewer(ws: Path, source_id: str) -> dict[str, Any] | None:
    """Solo corso microlearning; None se il file non esiste o è vuoto."""
    micro_path = ws / "reports" / "microlearning_course.json"
    if not micro_path.exists():
        return None

    data = load_json(micro_path)
    moduli_raw = data.get("moduli", [])
    if not moduli_raw:
        return None

    moduli: list[dict] = []
    by_id: dict[str, dict] = {}
    by_label: dict[str, str] = {}
    by_ordine: dict[int, str] = {}
    n_lezioni = n_quiz = 0

    for m in moduli_raw:
        mid = m.get("id", "")
        if not mid:
            continue
        tipo = m.get("tipo", "lezione")
        if tipo not in ("lezione", "quiz"):
            tipo = "quiz" if m.get("domande") else "lezione"
        label = _modulo_label({**m, "tipo": tipo})
        ordine = int(m.get("ordine", len(moduli) + 1))
        body = _modulo_body(m)

        entry = {
            "id": mid,
            "ordine": ordine,
            "tipo": tipo,
            "titolo": label,
            "sintesi": m.get("sintesi_breve", ""),
            "contenuto": body,
            "obiettivi": m.get("obiettivi_apprendimento", []),
            "durata_stimata_minuti": m.get("durata_stimata_minuti", 5 if tipo == "quiz" else 10),
            "prerequisiti": m.get("prerequisiti", []),
            "fonte": m.get("fonte"),
            "domande": m.get("domande", []),
            "caratteri_contenuto": len(body),
        }
        moduli.append(entry)
        by_id[mid] = entry
        by_label[_norm(label)] = mid
        by_ordine[ordine] = mid
        if tipo == "quiz":
            n_quiz += 1
        else:
            n_lezioni += 1

    moduli.sort(key=lambda x: x["ordine"])

    edges: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def add_edge(frm: str, to: str, kind: str) -> None:
        if frm == to or frm not in by_id or to not in by_id:
            return
        key = (frm, to, kind)
        if key in seen:
            return
        seen.add(key)
        edges.append({"from": frm, "to": to, "type": kind})

    for m in moduli:
        for pre in m.get("prerequisiti") or []:
            pid = _resolve_prereq(str(pre), by_id, by_label, by_ordine)
            if pid:
                kind = "quiz_after" if m["tipo"] == "quiz" else "prerequisite"
                add_edge(pid, m["id"], kind)

    prereq_count = sum(1 for e in edges if e["type"] != "sequence")
    if prereq_count < max(2, len(moduli) // 3):
        for i in range(1, len(moduli)):
            add_edge(moduli[i - 1]["id"], moduli[i]["id"], "sequence")

    nodes = []
    for m in moduli:
        short = m["titolo"][:44] + ("…" if len(m["titolo"]) > 44 else "")
        if m["tipo"] == "quiz":
            group = "quiz"
            shape = "diamond"
        else:
            group = "lezione"
            shape = "box"
        nodes.append({
            "id": m["id"],
            "label": f"{m['ordine']}. {short}",
            "title": m["titolo"],
            "ordine": m["ordine"],
            "durata": m["durata_stimata_minuti"],
            "tipo": m["tipo"],
            "group": group,
            "shape": shape,
        })

    return {
        "titolo_corso": data.get("titolo_corso", source_id),
        "descrizione": data.get("descrizione", ""),
        "lingua": data.get("lingua", "it"),
        "formato": "microlearning",
        "moduli": moduli,
        "graph": {"nodes": nodes, "edges": edges},
        "stats": {
            "moduli": len(moduli),
            "lezioni": n_lezioni,
            "quiz": n_quiz,
            "archi": len(edges),
            "durata_totale_minuti": sum(m["durata_stimata_minuti"] for m in moduli),
        },
    }
