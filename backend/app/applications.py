"""Application packs: generate, persist, render, and track bulk runs."""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from .db import connect
from .documents import (
    PdfUnavailable,
    application_folder,
    docx_to_pdf,
    render_cover_letter_docx,
    render_cv_docx,
)
from .generation import generate_cover_letter, generate_cv
from .humanize import clean_text, find_tells, reads_monotonous
from .models import Application, Augmentation, GeneratedCV, GenerationStatus, Job
from .profile_store import load_profile
from .settings_store import load_settings

log = logging.getLogger(__name__)

_lock = threading.Lock()
_status = GenerationStatus()


def get_generation_status() -> GenerationStatus:
    with _lock:
        return _status.model_copy(deep=True)


def generation_running() -> bool:
    with _lock:
        return _status.running


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _job_row(conn, job_id: int) -> dict:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise ValueError(f"Job {job_id} not found")
    return dict(row)


def _row_to_application(row, job: Job | None = None) -> Application:
    folder = row["folder"]
    cv = None
    if row["cv_json"]:
        try:
            cv = GeneratedCV.model_validate_json(row["cv_json"])
        except ValueError:
            cv = None

    def exists(name: str | None) -> bool:
        return bool(name and folder and (Path(folder) / name).exists())

    cv_text = ""
    if cv:
        cv_text = " ".join(
            [cv.summary, *(b.text for e in cv.experience for b in e.bullets)]
        )
    letter = row["cover_letter_text"] or ""

    return Application(
        id=row["id"],
        job_id=row["job_id"],
        augmentation=row["augmentation"],
        cv=cv,
        cover_letter_text=row["cover_letter_text"],
        flagged_additions=json.loads(row["flagged_additions"] or "[]"),
        style_notes=find_tells(cv_text, letter),
        monotonous=reads_monotonous(letter),
        folder=folder,
        has_cv_docx=exists(row["cv_docx"]),
        has_cv_pdf=exists(row["cv_pdf"]),
        has_cover_letter_docx=exists(row["cover_letter_docx"]),
        model=row["model"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        job=job,
    )


def get_application(job_id: int) -> Application | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,)).fetchone()
    return _row_to_application(row) if row else None


def render_documents(job_id: int) -> tuple[bool, str | None]:
    """(pdf_ok, pdf_error). DOCX failures raise; PDF is best-effort."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise ValueError("No application generated for this job yet")
        job = _job_row(conn, job_id)

    app_model = _row_to_application(row)
    if app_model.cv is None:
        raise ValueError("Application has no CV content to render")

    folder = application_folder(job)
    cv_docx = folder / "cv.docx"
    cover_docx = folder / "cover-letter.docx"
    cv_pdf = folder / "cv.pdf"

    render_cv_docx(app_model.cv, cv_docx)
    if app_model.cover_letter_text:
        render_cover_letter_docx(app_model.cover_letter_text, app_model.cv, cover_docx)

    pdf_ok, pdf_error = True, None
    try:
        docx_to_pdf(cv_docx, cv_pdf)
    except PdfUnavailable as exc:
        pdf_ok, pdf_error = False, str(exc)

    with connect() as conn:
        conn.execute(
            """
            UPDATE applications
               SET folder = ?, cv_docx = ?, cv_pdf = ?, cover_letter_docx = ?, updated_at = ?
             WHERE job_id = ?
            """,
            (
                str(folder),
                cv_docx.name,
                cv_pdf.name if pdf_ok else None,
                cover_docx.name if app_model.cover_letter_text else None,
                _now(),
                job_id,
            ),
        )
    return pdf_ok, pdf_error


def generate_for_job(job_id: int, augmentation: Augmentation | None = None) -> Application:
    """Full pack for one job. Only ever called when the user asks."""
    settings = load_settings()
    profile = load_profile()
    if profile is None:
        raise ValueError("Upload your master CV on the Profile page first")

    level: Augmentation = augmentation or settings.default_augmentation

    with connect() as conn:
        job = _job_row(conn, job_id)

    result = generate_cv(profile, job, level, settings.openai_model)
    cover = generate_cover_letter(profile, job, result.cv, level, settings.openai_model)

    now = _now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO applications (job_id, augmentation, cv_json, cover_letter_text,
                                      flagged_additions, model, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(job_id) DO UPDATE SET
                augmentation      = excluded.augmentation,
                cv_json           = excluded.cv_json,
                cover_letter_text = excluded.cover_letter_text,
                flagged_additions = excluded.flagged_additions,
                model             = excluded.model,
                updated_at        = excluded.updated_at
            """,
            (
                job_id,
                level,
                result.cv.model_dump_json(),
                cover,
                json.dumps(result.flagged_additions),
                settings.openai_model,
                now,
                now,
            ),
        )
        # Statuses only move forward - don't undo 'applied' by regenerating.
        conn.execute(
            "UPDATE jobs SET status = 'generated' WHERE id = ? AND status IN ('new','saved')",
            (job_id,),
        )

    try:
        render_documents(job_id)
    except Exception as exc:  # noqa: BLE001 - content is saved; rendering can be retried
        log.warning("Document rendering failed for job %s: %s", job_id, exc)

    app_model = get_application(job_id)
    assert app_model is not None
    return app_model


def update_cv(job_id: int, cv: GeneratedCV) -> Application:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE applications SET cv_json = ?, updated_at = ? WHERE job_id = ?",
            (cv.model_dump_json(), _now(), job_id),
        )
        if cur.rowcount == 0:
            raise ValueError("No application generated for this job yet")
    render_documents(job_id)
    app_model = get_application(job_id)
    assert app_model is not None
    return app_model


def update_cover_letter(job_id: int, text: str) -> Application:
    # Edits go through the same typography pass, so a dash pasted in from
    # elsewhere does not reappear in the DOCX.
    cleaned = "\n\n".join(
        clean_text(block) for block in (text or "").replace("\r\n", "\n").split("\n\n") if block.strip()
    )
    with connect() as conn:
        cur = conn.execute(
            "UPDATE applications SET cover_letter_text = ?, updated_at = ? WHERE job_id = ?",
            (cleaned, _now(), job_id),
        )
        if cur.rowcount == 0:
            raise ValueError("No application generated for this job yet")
    render_documents(job_id)
    app_model = get_application(job_id)
    assert app_model is not None
    return app_model


def run_bulk_generation(job_ids: list[int], augmentation: Augmentation | None) -> None:
    """Step 19. Generates packs for the selected jobs only; never submits anything."""
    global _status
    with _lock:
        _status = GenerationStatus(running=True, total=len(job_ids))

    try:
        for job_id in job_ids:
            with connect() as conn:
                row = conn.execute("SELECT title, company FROM jobs WHERE id = ?", (job_id,)).fetchone()
            label = f"{row['title']} at {row['company']}" if row else f"job {job_id}"
            with _lock:
                _status.current = label

            try:
                generate_for_job(job_id, augmentation)
                with _lock:
                    _status.generated += 1
            except Exception as exc:  # noqa: BLE001 - one failure must not stop the batch
                log.warning("Bulk generation failed for job %s: %s", job_id, exc)
                with _lock:
                    _status.errors.append(f"{label}: {exc}")
            with _lock:
                _status.completed += 1
    finally:
        with _lock:
            _status.running = False
            _status.current = None


def mark_bulk_queued(total: int) -> GenerationStatus:
    global _status
    with _lock:
        _status = GenerationStatus(running=True, total=total, current="Starting...")
        return _status.model_copy(deep=True)
