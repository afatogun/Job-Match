"""Application packs: generate, persist, render, and track bulk runs."""

import hashlib
import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import GENERATED_DIR
from .db import connect
from .documents import (
    PdfUnavailable,
    application_folder,
    docx_to_pdf,
    render_cv_pdf_simple,
    render_cover_letter_docx,
    render_cv_docx,
    slugify,
)
from .gap_analysis import analyse_gap
from .generation import generate_cover_letter, generate_cv, generate_interview_prep
from .interview_external import fetch_external_interview_prep
from .humanize import (
    clean_text,
    find_hedges,
    find_tells,
    reads_monotonous,
    vacancy_allowed_cliches,
)
from .models import (
    APPLICATION_STAGES,
    Application,
    ApplicationStage,
    Augmentation,
    GeneratedCV,
    GenerationStatus,
    InterviewPrepData,
    Job,
    JobGapAnalysis,
    Profile,
)
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
    prep = None
    prep_raw = row["interview_prep_json"] if "interview_prep_json" in row.keys() else None
    if prep_raw:
        try:
            prep = InterviewPrepData.model_validate_json(prep_raw)
        except ValueError:
            prep = None

    # Words the advert itself uses are not tells. Only available when the caller kept the
    # description; without it the check is simply stricter than it needs to be.
    allow = vacancy_allowed_cliches(job.description if job else None)
    notes = find_tells(cv_text, letter, allow=allow)
    if row["augmentation"] == "aggressive":
        # Hedging is only a defect here, where the whole point is to state things outright.
        notes += [f"hedged: {h}" for h in find_hedges(cv_text)]

    return Application(
        id=row["id"],
        job_id=row["job_id"],
        augmentation=row["augmentation"],
        cv=cv,
        cover_letter_text=row["cover_letter_text"],
        flagged_additions=json.loads(row["flagged_additions"] or "[]"),
        style_notes=notes,
        monotonous=reads_monotonous(letter),
        folder=folder,
        has_cv_docx=exists(row["cv_docx"]),
        has_cv_pdf=exists(row["cv_pdf"]),
        has_cover_letter_docx=exists(row["cover_letter_docx"]),
        model=row["model"],
        profile_id=row["profile_id"] if "profile_id" in row.keys() else None,
        stage=(
            row["stage"]
            if "stage" in row.keys() and row["stage"] in APPLICATION_STAGES
            else "generated"
        ),
        stage_updated_at=row["stage_updated_at"] if "stage_updated_at" in row.keys() else None,
        interview_prep=prep,
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
    candidate_slug = slugify(app_model.cv.full_name if app_model.cv else "", "candidate")
    company_slug = slugify(job.get("company", ""), "company")
    prefix = f"{candidate_slug}-{company_slug}"
    cv_docx = folder / f"{prefix}-cv.docx"
    cover_docx = folder / f"{prefix}-cover-letter.docx"
    cv_pdf = folder / f"{prefix}-cv.pdf"

    render_cv_docx(app_model.cv, cv_docx)
    if app_model.cover_letter_text:
        render_cover_letter_docx(app_model.cover_letter_text, app_model.cv, cover_docx)

    pdf_ok, pdf_error = True, None
    try:
        docx_to_pdf(cv_docx, cv_pdf)
    except PdfUnavailable as exc:
        try:
            render_cv_pdf_simple(app_model.cv, cv_pdf)
        except Exception as fallback_exc:  # noqa: BLE001
            pdf_ok, pdf_error = False, f"{exc}; fallback PDF render failed: {fallback_exc}"
        else:
            pdf_ok, pdf_error = True, None

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


_NUMBER = re.compile(r"\d[\d,.]*%?")


def _check_level_respected(level: Augmentation, result, profile: Profile) -> None:
    """Warn when generation did something it should not have.

    Only ever logged, never raised. The user can see and fix a bad CV; they cannot fix a
    pack that was never generated, so a false positive must not cost them the run.
    """
    # Asked to drop bullets that do nothing for the vacancy, a model will sometimes drop
    # the whole role. A CV with a hole in its employment history is rejected on sight.
    real = {e.company.strip().lower() for e in profile.experience if e.company.strip()}
    written = {e.company.strip().lower() for e in result.cv.experience if e.company.strip()}
    if real - written:
        log.warning(
            "Generation dropped %d employer(s) from the CV: %s",
            len(real - written),
            sorted(real - written),
        )

    if level != "accurate":
        return

    if result.flagged_additions or any(
        b.inferred for e in result.cv.experience for b in e.bullets
    ):
        log.warning("Accurate mode returned inferred content, which it should not have")

    from .generation import _profile_text

    known = set(_NUMBER.findall(_profile_text(profile)))
    cv_text = " ".join(
        [result.cv.summary, *(b.text for e in result.cv.experience for b in e.bullets)]
    )
    unknown = sorted(set(_NUMBER.findall(cv_text)) - known)
    if unknown:
        log.warning("Accurate mode produced numbers absent from the profile: %s", unknown)


def _analysis_key(job: dict, profile: Profile) -> str:
    """Identity of the two inputs the analysis actually depends on.

    Not the augmentation level: the analysis describes the full picture and is narrowed
    per level in Python, so one cached result serves all three. Profile.updated_at moves
    on every profile save, which is what invalidates it when the candidate changes.
    """
    payload = f"{job.get('description') or ''}\x00{profile.updated_at}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_or_create_gap_analysis(
    job_id: int, job: dict, profile: Profile, model: str, refresh: bool = False
) -> JobGapAnalysis:
    """Cached per job, because regenerating at a different level is the common case.

    Reads the cache here; the write happens in the same upsert that stores the pack, so
    the very first generation (which has no applications row yet) still populates it.
    """
    key = _analysis_key(job, profile)

    if not refresh:
        with connect() as conn:
            row = conn.execute(
                "SELECT gap_analysis_json, gap_analysis_key FROM applications WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row and row["gap_analysis_json"] and row["gap_analysis_key"] == key:
            try:
                analysis = JobGapAnalysis.model_validate_json(row["gap_analysis_json"])
                log.info("Gap analysis cache hit for job %s", job_id)
                return analysis
            except ValueError:
                pass  # Stale shape from an older release; recompute.

    return analyse_gap(profile, job, model)


def generate_for_job(
    job_id: int,
    augmentation: Augmentation | None = None,
    refresh_analysis: bool = False,
) -> Application:
    """Full pack for one job. Only ever called when the user asks."""
    from .profile_store import active_profile_id
    pid = active_profile_id()
    settings = load_settings(pid)
    profile = load_profile()
    if profile is None:
        raise ValueError("Upload your master CV on the Profile page first")

    level: Augmentation = augmentation or settings.default_augmentation

    with connect() as conn:
        job = _job_row(conn, job_id)

    # Accurate has no gaps to close, so it never sees an analysis at all - the bridge
    # claims must not be anywhere in its context.
    analysis = None
    if level != "accurate":
        try:
            analysis = load_or_create_gap_analysis(
                job_id, job, profile, settings.openai_model, refresh=refresh_analysis
            )
        except Exception as exc:  # noqa: BLE001 - never let the new call break generation
            log.warning(
                "Gap analysis failed for job %s, generating without it: %s", job_id, exc
            )

    result = generate_cv(profile, job, level, settings.openai_model, analysis=analysis)
    cover = generate_cover_letter(
        profile, job, result.cv, level, settings.openai_model, analysis=analysis
    )
    _check_level_respected(level, result, profile)

    now = _now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO applications (job_id, augmentation, cv_json, cover_letter_text,
                                      flagged_additions, model, profile_id, stage,
                                      stage_updated_at, gap_analysis_json, gap_analysis_key,
                                      gap_analysis_generated_at, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(job_id) DO UPDATE SET
                augmentation      = excluded.augmentation,
                cv_json           = excluded.cv_json,
                cover_letter_text = excluded.cover_letter_text,
                flagged_additions = excluded.flagged_additions,
                model             = excluded.model,
                profile_id        = excluded.profile_id,
                stage             = COALESCE(applications.stage, excluded.stage),
                stage_updated_at  = COALESCE(applications.stage_updated_at, excluded.stage_updated_at),
                gap_analysis_json = COALESCE(excluded.gap_analysis_json, applications.gap_analysis_json),
                gap_analysis_key  = COALESCE(excluded.gap_analysis_key, applications.gap_analysis_key),
                gap_analysis_generated_at = COALESCE(excluded.gap_analysis_generated_at,
                                                     applications.gap_analysis_generated_at),
                updated_at        = excluded.updated_at
            """,
            (
                job_id,
                level,
                result.cv.model_dump_json(),
                cover,
                json.dumps(result.flagged_additions),
                settings.openai_model,
                pid,
                "generated",
                now,
                analysis.model_dump_json() if analysis else None,
                _analysis_key(job, profile) if analysis else None,
                now if analysis else None,
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


def update_application_stage(job_id: int, stage: ApplicationStage) -> Application:
    """Update application stage progression for interview tracking."""
    now = _now()
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE applications
               SET stage = ?, stage_updated_at = ?, updated_at = ?
             WHERE job_id = ?
            """,
            (stage, now, now, job_id),
        )
        if cur.rowcount == 0:
            raise ValueError("No application generated for this job yet")
    app_model = get_application(job_id)
    assert app_model is not None
    return app_model


def delete_application(job_id: int) -> None:
    """Delete one generated application and best-effort cleanup generated files."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT folder, cv_docx, cv_pdf, cover_letter_docx
              FROM applications
             WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            raise ValueError("No application generated for this job yet")

        conn.execute("DELETE FROM applications WHERE job_id = ?", (job_id,))
        conn.execute(
            "UPDATE jobs SET status = 'saved' WHERE id = ? AND status = 'generated'",
            (job_id,),
        )

    folder = Path(row["folder"]).resolve() if row["folder"] else None
    if folder is None:
        return

    try:
        generated_root = GENERATED_DIR.resolve()
    except OSError:
        return

    # Only delete files inside our managed generated directory.
    if folder != generated_root and generated_root not in folder.parents:
        return

    for name in (row["cv_docx"], row["cv_pdf"], row["cover_letter_docx"]):
        if not name:
            continue
        try:
            path = folder / name
            if path.is_file():
                path.unlink()
        except OSError as exc:
            log.warning("Could not remove generated file %s: %s", path, exc)

    try:
        if folder.exists() and folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    except OSError:
        # Folder may contain other artifacts (for example interview prep exports).
        pass


def generate_application_interview_prep(job_id: int) -> Application:
    """Generate AI interview preparation content for an existing application."""
    settings = load_settings()
    profile = load_profile()
    if profile is None:
        raise ValueError("Upload your master CV on the Profile page first")

    with connect() as conn:
        app_row = conn.execute("SELECT id FROM applications WHERE job_id = ?", (job_id,)).fetchone()
        if app_row is None:
            raise ValueError("No application generated for this job yet")
        job = _job_row(conn, job_id)

    prep = None
    if settings.enable_external_interview_data:
        try:
            prep = fetch_external_interview_prep(job)
        except Exception as exc:  # noqa: BLE001 - external discovery is best effort
            log.warning("External interview lookup failed for job %s: %s", job_id, exc)

    if prep is None:
        prep = generate_interview_prep(profile, job, settings.openai_model)
        if settings.enable_external_interview_data:
            prep.source_note = (
                "External interview lookup is enabled, but no reliable external questions were found for "
                "this role right now. Showing AI-generated prep instead."
            )
    elif prep.source == "external":
        prep.source_note = (
            prep.source_note
            or "External interview data may be incomplete or noisy; treat as guidance and verify against the posting."
        )

    now = _now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE applications
               SET interview_prep_json = ?, interview_prep_generated_at = ?, updated_at = ?
             WHERE job_id = ?
            """,
            (prep.model_dump_json(), prep.generated_at or now, now, job_id),
        )

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
