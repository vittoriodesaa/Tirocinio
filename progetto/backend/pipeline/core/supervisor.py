"""
Supervisor: orchestra la pipeline per corso (workspace/{course_id}/).
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import List, Optional

from pipeline.core.agent_logging import (
    finish_run,
    narrative,
    phase,
    setup_logging,
    start_run,
    get_run,
)
from pipeline.agents.acquisition_agent import AcquisitionAgent
from pipeline.agents.document_agent import DocumentAgent
from pipeline.agents.microlearning_agent import MicrolearningPlanningAgent
from pipeline.agents.planning_agent import PlanningAgent
from pipeline.agents.segmentation_agent import SegmentationAgent
from pipeline.agents.validation_agent import ValidationAgent
from pipeline.core.pipeline_state import (
    CORPUS_SOURCE_ID,
    STEP_ORDER,
    analyze_course_workspace,
    append_course_source,
    detect_source_id,
    list_course_sources,
    resolve_pipeline_source_id,
    save_course_meta,
)
from pipeline.models.schemas import (
    AcquisitionRecord,
    CourseSourceEntry,
    DocumentHierarchy,
    DocumentStatus,
    FullPipelineOutput,
    JobBatchInput,
    JobBatchOutput,
    PipelineSourceResult,
    SourceInput,
    SourceOutputOverview,
)
from pipeline.core.workspace_io import load_json

logger = logging.getLogger("supervisor")

from pipeline.paths import LEGACY_WORKSPACE, WORKSPACE_ROOT, is_course_workspace_dir

_DEFAULT_WORKSPACE_ROOT = WORKSPACE_ROOT


class Supervisor:
    def __init__(self, workspace_root: str | Path | None = None):
        self.workspace_root = Path(workspace_root or _DEFAULT_WORKSPACE_ROOT)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.document_agent = DocumentAgent()
        self.planning_agent = PlanningAgent()
        self.segmentation_agent = SegmentationAgent()
        self.validation_agent = ValidationAgent()
        setup_logging()

    def _sanitize_course_id(self, course_id: str) -> str:
        cid = re.sub(r"[^a-zA-Z0-9_-]", "_", course_id.strip())[:64]
        return cid or str(uuid.uuid4())[:8]

    def resolve_course_path(self, course_id: str) -> Path:
        """Percorso cartella del corso."""
        if course_id == "temp_workspace" and LEGACY_WORKSPACE.exists():
            return LEGACY_WORKSPACE.resolve()
        return (self.workspace_root / self._sanitize_course_id(course_id)).resolve()

    def course_workspace(self, course_id: str) -> Path:
        ws = self.resolve_course_path(course_id)
        for sub in ("uploads", "sources", "chunks", "reports", "modules"):
            (ws / sub).mkdir(parents=True, exist_ok=True)
        return ws

    def list_courses(self) -> List[dict]:
        """Elenco corsi con stato sintetico."""
        courses: List[dict] = []
        seen: set[str] = set()

        if self.workspace_root.exists():
            for d in sorted(self.workspace_root.iterdir()):
                if d.is_dir() and is_course_workspace_dir(d.name):
                    status = analyze_course_workspace(d, d.name)
                    courses.append({
                        "course_id": d.name,
                        "source_id": status.source_id,
                        "prossimo_step": status.prossimo_step,
                        "file_count": status.file_count,
                        "legacy": False,
                    })
                    seen.add(d.name)

        if LEGACY_WORKSPACE.exists() and any(LEGACY_WORKSPACE.iterdir()):
            status = analyze_course_workspace(LEGACY_WORKSPACE, "temp_workspace")
            if "think_python" not in seen:
                courses.insert(0, {
                    "course_id": "temp_workspace",
                    "source_id": status.source_id,
                    "prossimo_step": status.prossimo_step,
                    "file_count": status.file_count,
                    "legacy": True,
                })

        return courses

    def get_course_status(self, course_id: str):
        ws = self.resolve_course_path(course_id)
        if not ws.exists():
            raise FileNotFoundError(f"Corso non trovato: {course_id}")
        return analyze_course_workspace(ws, course_id)

    def _load_source_input(self, ws: Path, source_id: str) -> SourceInput:
        acq_path = ws / "uploads" / f"{source_id}_acquisition.json"
        if acq_path.exists():
            data = json.loads(acq_path.read_text(encoding="utf-8"))
            storage = data.get("storage_ref", "")
            if not Path(storage).is_absolute():
                storage = str(ws / "uploads" / Path(storage).name) if storage else ""
            uploads = list((ws / "uploads").glob(f"{source_id}*"))
            uploads = [u for u in uploads if u.is_file() and not u.name.endswith("_acquisition.json")]
            if uploads and not storage:
                storage = str(uploads[0])
            return SourceInput(
                source_id=source_id,
                filename=data.get("filename", uploads[0].name if uploads else "documento"),
                media_type=data.get("media_type", "application/octet-stream"),
                source_type_hint=data.get("estensione", ".pdf").lstrip("."),
                storage_ref=storage or str(uploads[0]) if uploads else "",
                language_hint="it",
                ocr_required=data.get("ocr_probabile", False),
            )

        uploads = [u for u in (ws / "uploads").glob(f"{source_id}*") if u.is_file()]
        if uploads:
            u = uploads[0]
            return SourceInput(
                source_id=source_id,
                filename=u.name,
                media_type="application/octet-stream",
                source_type_hint=u.suffix.lstrip(".") or "pdf",
                storage_ref=str(u),
                language_hint="it",
            )

        raise FileNotFoundError(
            f"Nessun file di acquisizione per source_id={source_id} in {ws}",
        )

    def _load_hierarchy(self, ws: Path, source_id: str) -> Optional[DocumentHierarchy]:
        path = ws / "reports" / f"{source_id}_hierarchy.json"
        if path.exists():
            return DocumentHierarchy(**load_json(path))
        return None

    def _source_id_from_filename(self, filename: str) -> str:
        stem = Path(filename).stem
        sid = re.sub(r"[^a-zA-Z0-9_-]", "_", stem)[:64]
        return sid or "doc"

    def _course_source_entries(self, ws: Path, source_id: Optional[str] = None) -> List[CourseSourceEntry]:
        raw = list_course_sources(ws)
        if raw:
            return [CourseSourceEntry(**s) for s in raw]
        sid = source_id or detect_source_id(ws)
        if sid:
            return [CourseSourceEntry(source_id=sid, order=1)]
        return []

    def _elabora_documento_sorgente(
        self,
        ws: Path,
        course_id: str,
        sid: str,
        *,
        source: Optional[SourceInput] = None,
    ):
        if source is None:
            source = self._load_source_input(ws, sid)
        with phase("document_agent", source_id=sid, course=course_id):
            return self.document_agent.elabora_sorgente(source, workspace_dir=str(ws))

    def resume_pipeline(
        self,
        course_id: str,
        from_step: str,
        *,
        source_id: Optional[str] = None,
        source: Optional[SourceInput] = None,
        run_microlearning: bool = True,
        acquisition_record: Optional[AcquisitionRecord] = None,
    ) -> PipelineSourceResult:
        """Esegue la pipeline dal passo indicato in poi."""
        if from_step not in STEP_ORDER and from_step != "full":
            raise ValueError(f"Step non valido: {from_step}. Valori: {STEP_ORDER + ['full']}")

        ws = self.course_workspace(course_id)
        entries = self._course_source_entries(ws, source_id)
        if not entries:
            raise ValueError("source_id non rilevato nel workspace del corso")

        is_corpus = len(entries) > 1
        pipeline_sid = resolve_pipeline_source_id(ws)
        start_idx = 0 if from_step == "full" else STEP_ORDER.index(from_step)
        rel = lambda p: str(p.relative_to(ws)) if p.is_relative_to(ws) else str(p)

        report = None
        gerarchia = None
        quality_score = 0.0
        doc_idx = STEP_ORDER.index("document")
        plan_idx = STEP_ORDER.index("planning")

        if start_idx <= doc_idx:
            scores: list[float] = []
            for entry in entries:
                sid = entry.source_id
                src = source if (source and source.source_id == sid) else None
                if src is None and start_idx > 0 and (ws / "chunks" / f"{sid}_chunks.json").exists():
                    qpath = ws / "reports" / f"{sid}_quality.json"
                    if qpath.exists():
                        scores.append(load_json(qpath).get("quality_score", 0.0))
                    continue
                try:
                    src = src or self._load_source_input(ws, sid)
                except FileNotFoundError:
                    if start_idx > doc_idx:
                        continue
                    raise
                _profile, _md, _chunks, report, gerarchia = self._elabora_documento_sorgente(
                    ws, course_id, sid, source=src,
                )
                scores.append(report.quality_score)
                if report.blocking and not is_corpus:
                    return PipelineSourceResult(
                        source_id=sid,
                        acquisition=acquisition_record,
                        status=report.status,
                        quality_score=report.quality_score,
                        markdown_ref=rel(ws / "sources" / f"{sid}.md"),
                        quality_report_ref=rel(ws / "reports" / f"{sid}_quality.json"),
                        ready_for_enrichment=False,
                    )
            quality_score = sum(scores) / len(scores) if scores else 0.0
        else:
            sid0 = entries[0].source_id
            qpath = ws / "reports" / f"{sid0}_quality.json"
            if qpath.exists():
                quality_score = load_json(qpath).get("quality_score", 0.0)
            gerarchia = self._load_hierarchy(ws, sid0)

        plan = None
        if start_idx <= plan_idx:
            if is_corpus:
                for entry in entries:
                    sid = entry.source_id
                    hier = self._load_hierarchy(ws, sid)
                    if not (ws / "reports" / f"{sid}_plan.json").exists():
                        self.planning_agent.pianifica(sid, str(ws), hierarchy=hier)
                with phase("planning_agent", source_id=CORPUS_SOURCE_ID):
                    plan = self.planning_agent.pianifica_corpus(course_id, str(ws), entries)
            else:
                sid = entries[0].source_id
                with phase("planning_agent", source_id=sid):
                    plan = self.planning_agent.pianifica(
                        sid, str(ws), hierarchy=gerarchia or self._load_hierarchy(ws, sid),
                    )
        else:
            from pipeline.models.schemas import StructuralPlan
            plan_path = ws / "reports" / f"{pipeline_sid}_plan.json"
            if plan_path.exists():
                plan = StructuralPlan(**load_json(plan_path))

        seg = None
        if start_idx <= STEP_ORDER.index("segmentation"):
            with phase("segmentation_agent", source_id=pipeline_sid):
                seg = self.segmentation_agent.segmenta(pipeline_sid, str(ws), plan)

        val = None
        if start_idx <= STEP_ORDER.index("validation"):
            with phase("validation_agent", source_id=pipeline_sid):
                val = self.validation_agent.valida(pipeline_sid, str(ws), seg, plan)

        if val is None:
            vpath = ws / "reports" / f"{pipeline_sid}_validation.json"
            if vpath.exists():
                from pipeline.models.schemas import ValidationReport
                val = ValidationReport(**load_json(vpath))
            else:
                val_status = DocumentStatus.PASS
                val = type("V", (), {"stato_globale": val_status})()

        micro_ref = ""
        ready = val.stato_globale != DocumentStatus.FAIL
        if run_microlearning and ready and start_idx <= STEP_ORDER.index("microlearning"):
            with phase("microlearning_agent", source_id=pipeline_sid):
                ml = MicrolearningPlanningAgent(
                    str(ws),
                    course_output_path=str(ws / "reports" / "microlearning_course.json"),
                )
                ml.run()
                micro_ref = rel(ws / "reports" / "microlearning_course.json")
        elif (ws / "reports" / "microlearning_course.json").exists():
            micro_ref = rel(ws / "reports" / "microlearning_course.json")

        primary_sid = entries[0].source_id
        return PipelineSourceResult(
            source_id=pipeline_sid if is_corpus else primary_sid,
            acquisition=acquisition_record,
            status=val.stato_globale,
            quality_score=quality_score,
            markdown_ref=rel(ws / "sources" / f"{primary_sid}.md"),
            plan_ref=rel(ws / "reports" / f"{pipeline_sid}_plan.json"),
            raw_modules_ref=rel(ws / "modules" / f"{pipeline_sid}_raw_modules.json"),
            validated_modules_ref=rel(ws / "modules" / f"{pipeline_sid}_validated_modules.json"),
            validation_ref=rel(ws / "reports" / f"{pipeline_sid}_validation.json"),
            chunks_ref=rel(ws / "chunks" / f"{primary_sid}_chunks.json"),
            hierarchy_ref=rel(ws / "reports" / f"{primary_sid}_hierarchy.json"),
            quality_report_ref=rel(ws / "reports" / f"{primary_sid}_quality.json"),
            microlearning_ref=micro_ref,
            ready_for_enrichment=ready,
        )

    def esegui_pipeline_completa(
        self,
        source: SourceInput,
        *,
        course_id: Optional[str] = None,
        run_microlearning: bool = True,
        acquisition_record=None,
    ) -> PipelineSourceResult:
        course_id = self._sanitize_course_id(course_id or source.source_id)
        save_course_meta(
            self.course_workspace(course_id),
            course_id,
            source.source_id,
            source.filename,
        )
        return self.resume_pipeline(
            course_id,
            "full",
            source_id=source.source_id,
            source=source,
            run_microlearning=run_microlearning,
            acquisition_record=acquisition_record,
        )

    def acquisisci_multi_ed_elabora(
        self,
        uploads: List[tuple[bytes, str, str]],
        *,
        course_id: str,
        language_hint: str = "it",
        run_microlearning: bool = True,
        from_step: str = "full",
    ) -> FullPipelineOutput:
        """Acquisisce più file nello stesso corso e avvia la pipeline (merge al planning)."""
        cid = self._sanitize_course_id(course_id)
        ws = self.course_workspace(cid)
        acq = AcquisitionAgent(str(ws))
        records: List[AcquisitionRecord] = []
        sources: List[SourceInput] = []

        for file_bytes, filename, source_id in uploads:
            sid = source_id.strip() if source_id else self._source_id_from_filename(filename)
            record, source = acq.acquisisci_file(
                file_bytes, filename, sid, language_hint=language_hint,
            )
            append_course_source(ws, cid, source.source_id, filename)
            records.append(record)
            sources.append(source)

        if from_step == "acquisition":
            start_run(cid, str(ws))
            names = ", ".join(f"«{u[1]}»" for u in uploads)
            finish_run(cid, success=True, message=f"File registrati: {names}.", result={"job_id": cid})
            return FullPipelineOutput(
                job_id=cid,
                workspace_dir=str(ws),
                sources=[],
                log_summary=[f"Acquisiti {len(uploads)} file → workspace/{cid}/uploads/"],
            )

        start_run(cid, str(ws))
        if from_step == "full":
            narrative(
                f"Ho ricevuto {len(uploads)} documenti e avvio l'elaborazione del corso "
                f"(merge al planning).",
            )
        else:
            narrative(f"Riprendo il corso da: {from_step}.")
        step_run = "full" if from_step == "full" else from_step
        try:
            result = self.resume_pipeline(
                cid,
                step_run,
                run_microlearning=run_microlearning,
                acquisition_record=records[0] if records else None,
            )
            out = FullPipelineOutput(
                job_id=cid,
                workspace_dir=str(ws),
                sources=[result],
                microlearning_course_ref=result.microlearning_ref,
                log_summary=[f"Corso {cid} completato ({len(uploads)} documenti)."],
            )
            finish_run(cid, success=True, result=out.model_dump())
            return out
        except Exception as e:
            finish_run(cid, success=False, error=str(e))
            raise

    def acquisisci_ed_elabora(
        self,
        file_bytes: bytes,
        filename: str,
        source_id: str,
        *,
        course_id: Optional[str] = None,
        language_hint: str = "it",
        run_microlearning: bool = True,
        from_step: str = "full",
    ) -> FullPipelineOutput:
        cid = self._sanitize_course_id(course_id or source_id)
        ws = self.course_workspace(cid)
        acq = AcquisitionAgent(str(ws))
        record, source = acq.acquisisci_file(
            file_bytes, filename, source_id, language_hint=language_hint,
        )
        append_course_source(ws, cid, source.source_id, filename)

        if from_step == "acquisition":
            start_run(cid, str(ws))
            finish_run(cid, success=True, message=f"File «{filename}» registrato.", result={"job_id": cid})
            return FullPipelineOutput(
                job_id=cid,
                workspace_dir=str(ws),
                sources=[],
                log_summary=[f"Acquisito {filename} → workspace/{cid}/uploads/"],
            )

        start_run(cid, str(ws))
        if from_step == "full":
            narrative(f"Ho ricevuto «{filename}» e avvio l'elaborazione completa del corso.")
        else:
            narrative(f"Riprendo il corso da: {from_step}.")
        step_run = "full" if from_step == "full" else from_step
        try:
            result = self.resume_pipeline(
                cid,
                step_run,
                source_id=source.source_id,
                source=source if step_run in ("document", "full") else None,
                run_microlearning=run_microlearning,
                acquisition_record=record,
            )
            out = FullPipelineOutput(
                job_id=cid,
                workspace_dir=str(ws),
                sources=[result],
                microlearning_course_ref=result.microlearning_ref,
                log_summary=[f"Corso {cid} completato."],
            )
            finish_run(cid, success=True, result=out.model_dump())
            return out
        except Exception as e:
            finish_run(cid, success=False, error=str(e))
            raise

    def esegui_pipeline(self, job: JobBatchInput) -> JobBatchOutput:
        ws = self.course_workspace(job.job_id)
        processed = passed = flagged = failed = 0
        total_score = 0.0
        overviews: List[SourceOutputOverview] = []

        for source in job.sources:
            try:
                result = self.resume_pipeline(
                    job.job_id, "full", source=source, run_microlearning=False,
                )
                processed += 1
                total_score += result.quality_score
                if result.status == DocumentStatus.PASS:
                    passed += 1
                elif result.status == DocumentStatus.PASS_WITH_WARNINGS:
                    flagged += 1
                else:
                    failed += 1
                overviews.append(
                    SourceOutputOverview(
                        source_id=source.source_id,
                        status=result.status,
                        quality_score=result.quality_score,
                        markdown_ref=result.markdown_ref,
                        chunk_index_ref=result.chunks_ref,
                        quality_report_ref=result.quality_report_ref,
                        hierarchy_ref=result.hierarchy_ref,
                    )
                )
            except Exception as e:
                logger.exception("Pipeline fallita per %s: %s", source.source_id, e)
                processed += 1
                failed += 1
                overviews.append(
                    SourceOutputOverview(
                        source_id=source.source_id,
                        status=DocumentStatus.FAIL,
                        quality_score=0.0,
                        markdown_ref="",
                        chunk_index_ref="",
                        quality_report_ref="",
                    )
                )

        avg = round(total_score / processed, 2) if processed else 0.0
        return JobBatchOutput(
            job_id=job.job_id,
            processed_sources=processed,
            passed_sources=passed,
            flagged_sources=flagged,
            failed_sources=failed,
            average_quality_score=avg,
            ready_for_planning=failed == 0 and processed > 0,
            sources=overviews,
        )

    # Alias retrocompatibilità
    def _job_workspace(self, job_id: str) -> Path:
        return self.course_workspace(job_id)
