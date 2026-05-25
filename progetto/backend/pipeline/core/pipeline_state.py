"""
Rilevamento stato pipeline per corso (workspace/{course_id}/).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

PIPELINE_STEPS = [
    ("acquisition", "Acquisizione", 0),
    ("document", "Document", 1),
    ("planning", "Planning", 2),
    ("segmentation", "Segmentation", 3),
    ("validation", "Validation", 4),
    ("microlearning", "Microlearning", 5),
]

STEP_ORDER = [s[0] for s in PIPELINE_STEPS]


class StepStatus(BaseModel):
    id: str
    label: str
    ordine: int
    completato: bool = False
    artifact: Optional[str] = None
    dettaglio: Optional[str] = None


class WarningCount(BaseModel):
    messaggio: str
    occorrenze: int


class ModuleWarningSample(BaseModel):
    modulo_id: str
    titolo: str = ""
    stato: str
    messaggi: List[str] = Field(default_factory=list)


class PipelineWarnings(BaseModel):
    """Sintesi avvisi da validazione moduli e report qualità documento."""
    stato_globale: Optional[str] = None
    stato_label: str = ""
    moduli_approvati: int = 0
    moduli_in_revisione: int = 0
    moduli_respinti: int = 0
    raccomandazione: str = ""
    messaggi_aggregati: List[WarningCount] = Field(default_factory=list)
    moduli_campione: List[ModuleWarningSample] = Field(default_factory=list)
    qualita_documento: Optional[Dict[str, Any]] = None


class CoursePipelineStatus(BaseModel):
    course_id: str
    workspace_path: str
    source_id: Optional[str] = None
    prossimo_step: str = "acquisition"
    steps: List[StepStatus] = Field(default_factory=list)
    file_count: int = 0
    warnings: Optional[PipelineWarnings] = None


_STATUS_LABELS = {
    "PASS": "Completato",
    "PASS_WITH_WARNINGS": "Completato con avvisi",
    "FAIL": "Non superato",
}


def _load_module_titles(ws: Path, source_id: str) -> dict[str, str]:
    titles: dict[str, str] = {}
    for path in (
        ws / "modules" / f"{source_id}_raw_modules.json",
        ws / "modules" / f"{source_id}_validated_modules.json",
    ):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for m in data.get("moduli", []):
            mid = m.get("id")
            if mid:
                titles[mid] = (m.get("titolo") or m.get("argomento") or mid)[:80]
    return titles


def load_pipeline_warnings(ws: Path, source_id: str) -> Optional[PipelineWarnings]:
    """Legge validation + quality report e produce sintesi per UI."""
    val_path = ws / "reports" / f"{source_id}_validation.json"
    if not val_path.exists():
        return None

    try:
        val = json.loads(val_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    titles = _load_module_titles(ws, source_id)
    msg_counter: Counter[str] = Counter()
    samples: list[ModuleWarningSample] = []

    for v in val.get("validazioni", []):
        if v.get("stato") == "approved":
            continue
        msgs = v.get("messaggi") or []
        for m in msgs:
            msg_counter[m] += 1
        if len(samples) < 12:
            mid = v.get("modulo_id", "")
            samples.append(
                ModuleWarningSample(
                    modulo_id=mid,
                    titolo=titles.get(mid, ""),
                    stato=v.get("stato", "needs_review"),
                    messaggi=msgs[:3],
                )
            )

    qualita = None
    q_path = ws / "reports" / f"{source_id}_quality.json"
    if q_path.exists():
        try:
            q = json.loads(q_path.read_text(encoding="utf-8"))
            qualita = {
                "status": q.get("status"),
                "quality_score": q.get("quality_score"),
                "recommended_action": q.get("recommended_action"),
                "issues": (q.get("issues") or [])[:8],
            }
        except (json.JSONDecodeError, OSError):
            pass

    stato = val.get("stato_globale", "")
    return PipelineWarnings(
        stato_globale=stato,
        stato_label=_STATUS_LABELS.get(stato, stato),
        moduli_approvati=int(val.get("moduli_approvati", 0)),
        moduli_in_revisione=int(val.get("moduli_in_revisione", 0)),
        moduli_respinti=int(val.get("moduli_respinti", 0)),
        raccomandazione=val.get("raccomandazione", ""),
        messaggi_aggregati=[
            WarningCount(messaggio=m, occorrenze=c)
            for m, c in msg_counter.most_common(10)
        ],
        moduli_campione=samples,
        qualita_documento=qualita,
    )


def _read_course_meta(ws: Path) -> dict:
    meta = ws / "course.json"
    if meta.exists():
        try:
            return json.loads(meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def detect_source_id(ws: Path) -> Optional[str]:
    meta = _read_course_meta(ws)
    if meta.get("source_id"):
        return meta["source_id"]

    uploads = ws / "uploads"
    if uploads.exists():
        for p in sorted(uploads.glob("*_acquisition.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("source_id"):
                    return data["source_id"]
            except json.JSONDecodeError:
                continue
        for p in uploads.iterdir():
            if p.is_file() and not p.name.endswith("_acquisition.json"):
                return p.stem.split("_")[0] if "_" in p.stem else p.stem

    sources = ws / "sources"
    if sources.exists():
        for p in sources.glob("*_clean.md"):
            return p.name.replace("_clean.md", "")
        for p in sources.glob("*.md"):
            name = p.name.replace(".md", "")
            if not name.endswith("_raw") and not name.endswith("_clean"):
                return name

    return None


def analyze_course_workspace(ws: Path, course_id: str) -> CoursePipelineStatus:
    ws = ws.resolve()
    source_id = detect_source_id(ws)
    steps_out: List[StepStatus] = []

    upload_files = list((ws / "uploads").glob("*")) if (ws / "uploads").exists() else []
    upload_files = [f for f in upload_files if f.is_file() and not f.name.endswith("_acquisition.json")]
    acq_meta = list((ws / "uploads").glob("*_acquisition.json")) if (ws / "uploads").exists() else []

    sid_early = source_id or "unknown"
    has_sources = (ws / "sources").exists() and any((ws / "sources").iterdir())
    acquisition_ok = bool(upload_files or acq_meta) or has_sources
    steps_out.append(StepStatus(
        id="acquisition",
        label="Acquisizione",
        ordine=0,
        completato=acquisition_ok,
        artifact=str(upload_files[0].relative_to(ws)) if upload_files else (
            str(acq_meta[0].relative_to(ws)) if acq_meta else None
        ),
    ))

    sid = source_id or "unknown"
    clean = ws / "sources" / f"{sid}_clean.md"
    final_md = ws / "sources" / f"{sid}.md"
    chunks = ws / "chunks" / f"{sid}_chunks.json"
    hierarchy = ws / "reports" / f"{sid}_hierarchy.json"
    quality = ws / "reports" / f"{sid}_quality.json"

    document_ok = clean.exists() or final_md.exists()
    doc_artifacts = []
    if clean.exists():
        doc_artifacts.append(str(clean.relative_to(ws)))
    if chunks.exists():
        doc_artifacts.append(str(chunks.relative_to(ws)))
    steps_out.append(StepStatus(
        id="document",
        label="Document",
        ordine=1,
        completato=document_ok and chunks.exists(),
        artifact=doc_artifacts[0] if doc_artifacts else None,
        dettaglio=f"chunk={'sì' if chunks.exists() else 'no'}, gerarchia={'sì' if hierarchy.exists() else 'no'}",
    ))

    plan = ws / "reports" / f"{sid}_plan.json"
    steps_out.append(StepStatus(
        id="planning",
        label="Planning",
        ordine=2,
        completato=plan.exists(),
        artifact=str(plan.relative_to(ws)) if plan.exists() else None,
    ))

    raw_mod = ws / "modules" / f"{sid}_raw_modules.json"
    steps_out.append(StepStatus(
        id="segmentation",
        label="Segmentation",
        ordine=3,
        completato=raw_mod.exists(),
        artifact=str(raw_mod.relative_to(ws)) if raw_mod.exists() else None,
    ))

    validation = ws / "reports" / f"{sid}_validation.json"
    validated = ws / "modules" / f"{sid}_validated_modules.json"
    steps_out.append(StepStatus(
        id="validation",
        label="Validation",
        ordine=4,
        completato=validation.exists() and validated.exists(),
        artifact=str(validation.relative_to(ws)) if validation.exists() else None,
    ))

    micro = ws / "reports" / "microlearning_course.json"
    steps_out.append(StepStatus(
        id="microlearning",
        label="Microlearning",
        ordine=5,
        completato=micro.exists(),
        artifact=str(micro.relative_to(ws)) if micro.exists() else None,
    ))

    prossimo = "acquisition"
    for s in steps_out:
        if not s.completato:
            prossimo = s.id
            break
    else:
        prossimo = "done"

    file_count = sum(1 for _ in ws.rglob("*") if _.is_file()) if ws.exists() else 0

    warnings = load_pipeline_warnings(ws, sid) if source_id else None

    return CoursePipelineStatus(
        course_id=course_id,
        workspace_path=str(ws),
        source_id=source_id,
        prossimo_step=prossimo,
        steps=steps_out,
        file_count=file_count,
        warnings=warnings,
    )


def save_course_meta(ws: Path, course_id: str, source_id: str, filename: str = "") -> None:
    ws.mkdir(parents=True, exist_ok=True)
    meta = {
        "course_id": course_id,
        "source_id": source_id,
        "filename": filename,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    (ws / "course.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
