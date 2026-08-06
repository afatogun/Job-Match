"""Steps 15-19 - generation, editing, download and bulk runs."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from .. import applications as service
from ..ai import MissingAPIKey
from ..db import connect
from ..models import (
    Application,
    ApplicationStageUpdate,
    BulkGenerateRequest,
    CoverLetterUpdate,
    CVUpdate,
    GenerateRequest,
    GenerationStatus,
)
from ..ranking import rank_specific_jobs
from ..settings_store import load_settings
from .jobs import row_to_job

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["applications"])

DOWNLOADS = {
    "cv.docx": ("cv_docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "cv.pdf": ("cv_pdf", "application/pdf"),
    "cover-letter.docx": ("cover_letter_docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}


def _handle_ai_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MissingAPIKey):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=502, detail=f"Generation failed: {exc}")


@router.get("/applications", response_model=list[Application])
def list_applications() -> list[Application]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT job_id FROM applications ORDER BY updated_at DESC"
        ).fetchall()
    out = []
    for row in rows:
        app_model = service.get_application(row["job_id"])
        if app_model:
            with connect() as conn:
                job_row = conn.execute(
                    "SELECT * FROM jobs WHERE id = ?", (row["job_id"],)
                ).fetchone()
            if job_row:
                app_model.job = row_to_job(job_row, include_description=False)
            out.append(app_model)
    return out


@router.get("/jobs/{job_id}/application", response_model=Application | None)
def get_application(job_id: int) -> Application | None:
    return service.get_application(job_id)


@router.delete("/jobs/{job_id}/application", status_code=204)
def delete_application(job_id: int) -> None:
    try:
        service.delete_application(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/generate", response_model=Application)
def generate(job_id: int, payload: GenerateRequest) -> Application:
    try:
        return service.generate_for_job(job_id, payload.augmentation)
    except Exception as exc:  # noqa: BLE001 - mapped to a clean HTTP error
        raise _handle_ai_error(exc) from exc


@router.put("/jobs/{job_id}/application/cv", response_model=Application)
def edit_cv(job_id: int, payload: CVUpdate) -> Application:
    try:
        return service.update_cv(job_id, payload.cv)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/jobs/{job_id}/application/cover-letter", response_model=Application)
def edit_cover_letter(job_id: int, payload: CoverLetterUpdate) -> Application:
    try:
        return service.update_cover_letter(job_id, payload.cover_letter_text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/jobs/{job_id}/application/stage", response_model=Application)
def update_application_stage(job_id: int, payload: ApplicationStageUpdate) -> Application:
    try:
        return service.update_application_stage(job_id, payload.stage)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/application/interview-prep", response_model=Application)
def generate_interview_prep(job_id: int) -> Application:
    try:
        return service.generate_application_interview_prep(job_id)
    except Exception as exc:  # noqa: BLE001 - mapped to a clean HTTP error
        raise _handle_ai_error(exc) from exc


@router.post("/jobs/{job_id}/rerank", response_model=dict)
def rerank(job_id: int) -> dict:
    try:
        ranked = rank_specific_jobs([job_id], load_settings())
    except Exception as exc:  # noqa: BLE001
        raise _handle_ai_error(exc) from exc
    return {"ranked": ranked}


@router.get("/jobs/{job_id}/download/{filename}")
def download(job_id: int, filename: str):
    if filename not in DOWNLOADS:
        raise HTTPException(status_code=404, detail="Unknown document")

    column, media_type = DOWNLOADS[filename]
    with connect() as conn:
        row = conn.execute(
            f"SELECT folder, {column} AS name FROM applications WHERE job_id = ?", (job_id,)
        ).fetchone()
    if row is None or not row["folder"] or not row["name"]:
        raise HTTPException(status_code=404, detail="That document has not been generated")

    path = Path(row["folder"]) / row["name"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="File is missing from the generated folder")

    return FileResponse(path, media_type=media_type, filename=row["name"])


# ------------------------------------------------------------------ bulk


@router.get("/generate/status", response_model=GenerationStatus)
def generation_status() -> GenerationStatus:
    return service.get_generation_status()


@router.post("/generate/bulk", response_model=GenerationStatus)
def generate_bulk(payload: BulkGenerateRequest, background: BackgroundTasks) -> GenerationStatus:
    if service.generation_running():
        raise HTTPException(status_code=409, detail="A generation run is already in progress")
    if not payload.job_ids:
        raise HTTPException(status_code=400, detail="Select at least one job")

    status = service.mark_bulk_queued(len(payload.job_ids))
    background.add_task(service.run_bulk_generation, payload.job_ids, payload.augmentation)
    return status
