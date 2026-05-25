"""
Server FastAPI — pipeline multi-agente didattica + UI web.
Ogni corso vive in workspace/{course_id}/.
"""
from __future__ import annotations

import logging
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pipeline.config.settings import get_config_report
from pipeline.core.agent_logging import finish_run, get_run, setup_logging, start_run
from pipeline.core.course_viewer import build_course_viewer
from pipeline.core.pipeline_state import PIPELINE_STEPS, STEP_ORDER, analyze_course_workspace
from pipeline.core.supervisor import Supervisor
from pipeline.core.workspace_io import load_json
from pipeline.models.schemas import FullPipelineOutput, JobBatchInput, JobBatchOutput
from pipeline.paths import ENV_FILE, STATIC_DIR

load_dotenv(ENV_FILE)
setup_logging()
logger = logging.getLogger("main")

app = FastAPI(
    title="Pipeline Backend Didattico",
    description="Pipeline multi-agente per corso — una cartella per corso, ripresa da step",
    version="2.2.0",
)

orchestratore = Supervisor()

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def home():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Pipeline Didattica</h1>")


@app.get("/api/v1/health")
async def health():
    return {
        "status": "ok",
        "steps": [{"id": s[0], "label": s[1]} for s in PIPELINE_STEPS],
    }


@app.get("/api/v1/config")
async def runtime_config():
    """Configurazione effettiva (.env + default). Le API key sono mascherate."""
    return get_config_report()


@app.get("/api/v1/courses")
async def list_courses():
    """Elenco corsi (sottocartelle workspace + legacy temp/workspace)."""
    return {"courses": orchestratore.list_courses()}


@app.get("/api/v1/courses/{course_id}/status")
async def course_status(course_id: str):
    try:
        return orchestratore.get_course_status(course_id).model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Corso '{course_id}' non trovato")


def _run_pipeline_task(
    *,
    course_id: str,
    from_step: str,
    source_id: Optional[str],
    run_microlearning: bool,
    file_bytes: Optional[bytes],
    filename: Optional[str],
    language_hint: str,
):
    try:
        if file_bytes and filename and from_step in ("acquisition", "full", "document"):
            orchestratore.acquisisci_ed_elabora(
                file_bytes,
                filename,
                source_id or course_id,
                course_id=course_id,
                language_hint=language_hint,
                run_microlearning=run_microlearning,
                from_step=from_step,
            )
        else:
            ws = str(orchestratore.course_workspace(course_id))
            start_run(course_id, ws)
            result = orchestratore.resume_pipeline(
                course_id,
                from_step if from_step != "full" else "full",
                source_id=source_id,
                run_microlearning=run_microlearning,
            )
            out = FullPipelineOutput(
                job_id=course_id,
                workspace_dir=ws,
                sources=[result],
                microlearning_course_ref=result.microlearning_ref,
                log_summary=["Completato."],
            )
            finish_run(course_id, success=True, result=out.model_dump())
    except Exception as e:
        logger.exception("Pipeline background: %s", e)
        finish_run(course_id, success=False, error=str(e))


@app.get("/api/v1/courses/{course_id}/activity")
async def course_activity(course_id: str):
    """Log narrativo in tempo reale + percentuale (polling UI)."""
    run = get_run(course_id)
    if run:
        snap = run.snapshot()
        if run.result:
            snap["result"] = run.result
        return snap
    ws = orchestratore.resolve_course_path(course_id)
    log_file = ws / "activity.log"
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")[-40:]
        return {
            "course_id": course_id,
            "status": "idle",
            "percent": 100.0,
            "entries": [{"time": "", "message": ln, "percent": 0, "level": "info"} for ln in lines],
        }
    return {"course_id": course_id, "status": "idle", "percent": 0, "entries": []}


@app.post("/api/v1/pipeline/run-async")
async def run_pipeline_async(
    background_tasks: BackgroundTasks,
    source_id: str = Form(...),
    course_id: Optional[str] = Form(None),
    language_hint: str = Form("it"),
    run_microlearning: bool = Form(True),
    from_step: str = Form("full"),
    file: UploadFile | None = File(None),
):
    """Avvia pipeline in background; usa GET .../activity per seguire i log."""
    cid = course_id or source_id
    orchestratore.course_workspace(cid)

    data = None
    fname = None
    if file and file.filename:
        data = await file.read()
        fname = file.filename

    background_tasks.add_task(
        _run_pipeline_task,
        course_id=cid,
        from_step=from_step,
        source_id=source_id,
        run_microlearning=run_microlearning,
        file_bytes=data,
        filename=fname,
        language_hint=language_hint,
    )
    return {"course_id": cid, "status": "started", "message": "Elaborazione avviata. Aggiorna i log."}


@app.post("/api/v1/courses/{course_id}/resume")
async def resume_course(
    course_id: str,
    background_tasks: BackgroundTasks,
    from_step: str = Form(...),
    source_id: Optional[str] = Form(None),
    run_microlearning: bool = Form(True),
    async_mode: bool = Form(True),
):
    if from_step not in STEP_ORDER + ["full"]:
        raise HTTPException(status_code=400, detail=f"from_step non valido: {from_step}")

    if async_mode:
        ws = str(orchestratore.course_workspace(course_id))
        start_run(course_id, ws)
        background_tasks.add_task(
            _run_pipeline_task,
            course_id=course_id,
            from_step=from_step,
            source_id=source_id,
            run_microlearning=run_microlearning,
            file_bytes=None,
            filename=None,
            language_hint="it",
        )
        return {"course_id": course_id, "status": "started"}

    try:
        result = orchestratore.resume_pipeline(
            course_id, from_step if from_step != "full" else "full",
            source_id=source_id, run_microlearning=run_microlearning,
        )
        ws = orchestratore.resolve_course_path(course_id)
        return FullPipelineOutput(
            job_id=course_id, workspace_dir=str(ws), sources=[result],
            microlearning_course_ref=result.microlearning_ref,
            log_summary=["Completato."],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/pipeline/run", response_model=FullPipelineOutput)
async def run_pipeline(
    source_id: str = Form(...),
    course_id: Optional[str] = Form(None),
    language_hint: str = Form("it"),
    run_microlearning: bool = Form(True),
    from_step: str = Form("full"),
    file: UploadFile | None = File(None),
):
    """
    Nuovo corso o ripresa. course_id = cartella in workspace/.
    File obbligatorio solo per acquisition / full / document (se non già acquisito).
    """
    cid = course_id or source_id
    upload_steps = {"acquisition", "full", "document"}

    try:
        has_file = file is not None and file.filename
        if from_step in upload_steps:
            if has_file:
                data = await file.read()
                if not data:
                    raise HTTPException(status_code=400, detail="File vuoto")
                return orchestratore.acquisisci_ed_elabora(
                    data,
                    file.filename,
                    source_id,
                    course_id=cid,
                    language_hint=language_hint,
                    run_microlearning=run_microlearning,
                    from_step=from_step,
                )
            if from_step == "document":
                st = orchestratore.get_course_status(cid)
                if not st.steps[0].completato:
                    raise HTTPException(
                        status_code=400,
                        detail="Carica il file oppure completa prima l'acquisizione",
                    )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="File richiesto per questo step",
                )

        result = orchestratore.resume_pipeline(
            cid,
            from_step if from_step != "full" else "full",
            source_id=source_id or None,
            run_microlearning=run_microlearning,
        )
        ws = orchestratore.resolve_course_path(cid)
        return FullPipelineOutput(
            job_id=cid,
            workspace_dir=str(ws),
            sources=[result],
            microlearning_course_ref=result.microlearning_ref,
            log_summary=[f"Pipeline da '{from_step}' su corso {cid}"],
        )
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Pipeline run: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/process-job", response_model=JobBatchOutput)
async def avvia_processo_documentale(job_input: JobBatchInput):
    try:
        return orchestratore.esegui_pipeline(job_input)
    except Exception as e:
        logger.exception("Errore batch: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/courses/{course_id}/files")
async def list_course_files(course_id: str):
    ws = orchestratore.resolve_course_path(course_id)
    if not ws.exists():
        raise HTTPException(status_code=404, detail="Corso non trovato")
    files = [
        {"path": p.relative_to(ws).as_posix(), "size": p.stat().st_size}
        for p in sorted(ws.rglob("*"))
        if p.is_file()
    ]
    return {"course_id": course_id, "workspace": str(ws), "files": files}


@app.get("/api/v1/courses/{course_id}/course-view")
async def get_course_view(course_id: str):
    """Grafo e catalogo del corso microlearning (lezioni + quiz)."""
    ws = orchestratore.resolve_course_path(course_id)
    if not ws.exists():
        raise HTTPException(status_code=404, detail="Corso non trovato")
    status = analyze_course_workspace(ws, course_id)
    source_id = status.source_id or course_id
    payload = build_course_viewer(ws, source_id)
    if not payload:
        raise HTTPException(
            status_code=404,
            detail="Corso microlearning non trovato. Completa lo step Microlearning.",
        )
    payload["course_id"] = course_id
    payload["source_id"] = source_id
    payload["completato"] = status.prossimo_step == "done"
    payload["microlearning_pronto"] = (ws / "reports" / "microlearning_course.json").exists()
    return payload


@app.get("/api/v1/courses/{course_id}/file")
async def get_course_file(course_id: str, path: str):
    ws = orchestratore.resolve_course_path(course_id)
    target = (ws / path).resolve()
    if not str(target).startswith(str(ws.resolve())) or not target.is_file():
        raise HTTPException(status_code=404, detail="File non trovato")
    if target.suffix.lower() == ".json":
        return JSONResponse(load_json(target))
    return FileResponse(target, media_type="text/plain; charset=utf-8")


@app.get("/api/v1/jobs")
async def list_jobs():
    return {"jobs": [c["course_id"] for c in orchestratore.list_courses()]}


@app.get("/api/v1/workspace/{job_id}/files")
async def list_workspace_files_legacy(job_id: str):
    return await list_course_files(job_id)


@app.get("/api/v1/workspace/{job_id}/file")
async def get_workspace_file_legacy(job_id: str, path: str):
    return await get_course_file(job_id, path)
