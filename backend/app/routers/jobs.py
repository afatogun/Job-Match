"""Job listing, detail, status, refresh and dashboard stats."""

import json
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from ..db import connect
from ..models import Job, JobListResponse, RefreshStatus, Stats, StatusUpdate
from ..pipeline import get_status, is_running, mark_queued, run_refresh
from ..profile_store import active_profile_id

router = APIRouter(prefix="/api", tags=["jobs"])

GOOD_MATCH_THRESHOLD = 70.0

# The score shown and sorted on: AI when we have it, local otherwise.
DISPLAY_SCORE = "COALESCE(ai_score, local_score)"

_JOB_COLUMNS = f"""
    id, source, source_job_id, title, company, location, is_remote, job_url,
    job_url_direct, date_posted, job_type, salary_min, salary_max, salary_currency,
    salary_interval, status, local_score, ai_score, ai_reason, ai_matching_skills,
    ai_missing_skills, ai_seniority_fit, ai_ranked_at, matching_terms,
    first_seen_at, last_seen_at, profile_id,
    {DISPLAY_SCORE} AS relevance_score,
    EXISTS(SELECT 1 FROM applications a WHERE a.job_id = jobs.id) AS has_application
"""


def _json_list(value) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return []
    return [str(x) for x in parsed] if isinstance(parsed, list) else []


def row_to_job(row, include_description: bool = False) -> Job:
    data = dict(row)
    data["is_remote"] = None if data.get("is_remote") is None else bool(data["is_remote"])
    data["has_application"] = bool(data.get("has_application"))
    data["ai_matching_skills"] = _json_list(data.get("ai_matching_skills"))
    data["ai_missing_skills"] = _json_list(data.get("ai_missing_skills"))
    data["matching_terms"] = _json_list(data.get("matching_terms"))
    if not include_description:
        data["description"] = None
    return Job.model_validate(data)


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    q: str | None = None,
    source: str | None = None,
    status: str | None = None,
    profile_id: str | None = None,
    posted_within_days: int | None = Query(default=None, ge=1, le=365),
    min_score: float | None = Query(default=None, ge=0, le=100),
    salary_min: float | None = Query(default=None, ge=0),
    salary_max: float | None = Query(default=None, ge=0),
    sort: Literal["newest", "best", "salary_high"] = "newest",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobListResponse:
    where: list[str] = []
    params: list[object] = []

    if q:
        where.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
        like = f"%{q.strip()}%"
        params += [like, like, like]
    if source:
        where.append("source = ?")
        params.append(source)
    if status:
        where.append("status = ?")
        params.append(status)
    if profile_id:
        where.append("profile_id = ?")
        params.append(profile_id)
    if posted_within_days is not None:
        cutoff = (date.today() - timedelta(days=posted_within_days)).isoformat()
        # Undated postings are kept rather than silently hidden.
        where.append("(date_posted IS NULL OR date_posted >= ?)")
        params.append(cutoff)
    if min_score is not None:
        where.append(f"{DISPLAY_SCORE} >= ?")
        params.append(min_score)
    if salary_min is not None:
        where.append("COALESCE(salary_max, salary_min) >= ?")
        params.append(salary_min)
    if salary_max is not None:
        where.append("COALESCE(salary_min, salary_max) <= ?")
        params.append(salary_max)

    clause = f"WHERE {' AND '.join(where)}" if where else ""
    if sort == "best":
        order = f"ORDER BY {DISPLAY_SCORE} DESC NULLS LAST, date_posted DESC NULLS LAST, id DESC"
    elif sort == "salary_high":
        order = (
            f"ORDER BY COALESCE(salary_max, salary_min) DESC NULLS LAST, "
            f"{DISPLAY_SCORE} DESC NULLS LAST, date_posted DESC NULLS LAST, id DESC"
        )
    else:
        order = "ORDER BY date_posted DESC NULLS LAST, id DESC"

    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n FROM jobs {clause}", params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT {_JOB_COLUMNS} FROM jobs {clause} {order} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()

    return JobListResponse(
        items=[row_to_job(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/jobs/refresh/status", response_model=RefreshStatus)
def refresh_status() -> RefreshStatus:
    return get_status()


@router.post("/jobs/refresh", response_model=RefreshStatus)
def start_refresh(background: BackgroundTasks) -> RefreshStatus:
    if is_running():
        raise HTTPException(status_code=409, detail="A refresh is already running")
    status = mark_queued()
    background.add_task(run_refresh)
    return status


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: int) -> Job:
    with connect() as conn:
        row = conn.execute(
            f"SELECT {_JOB_COLUMNS}, description FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return row_to_job(row, include_description=True)


@router.patch("/jobs/{job_id}", response_model=Job)
def update_status(job_id: int, payload: StatusUpdate) -> Job:
    with connect() as conn:
        cur = conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (payload.status, job_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Job not found")
        row = conn.execute(
            f"SELECT {_JOB_COLUMNS}, description FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return row_to_job(row, include_description=True)


@router.get("/stats", response_model=Stats)
def stats() -> Stats:
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(status = 'new'), 0) AS new_jobs,
                   COALESCE(SUM({DISPLAY_SCORE} >= ?), 0) AS good_matches
              FROM jobs
            """,
            (GOOD_MATCH_THRESHOLD,),
        ).fetchone()
        generated = conn.execute("SELECT COUNT(*) AS n FROM applications").fetchone()["n"]
        last = conn.execute("SELECT MAX(finished_at) AS last FROM refresh_runs").fetchone()

    return Stats(
        total_jobs=row["total"],
        new_jobs=row["new_jobs"],
        good_matches=row["good_matches"],
        generated_applications=generated,
        last_refresh_at=last["last"] if last else None,
    )


@router.delete("/jobs", status_code=204)
def clear_jobs(profile_id: str | None = None) -> None:
    """Delete jobs for one profile while keeping generated applications intact."""
    target_profile_id = profile_id or active_profile_id()
    with connect() as conn:
        if target_profile_id:
            # Keep jobs that already have generated applications so app history survives.
            conn.execute(
                """
                DELETE FROM jobs
                 WHERE (profile_id = ? OR profile_id IS NULL)
                   AND NOT EXISTS (
                        SELECT 1 FROM applications a
                         WHERE a.job_id = jobs.id
                   )
                """,
                (target_profile_id,),
            )
        else:
            conn.execute(
                """
                DELETE FROM jobs
                 WHERE profile_id IS NULL
                   AND NOT EXISTS (
                        SELECT 1 FROM applications a
                         WHERE a.job_id = jobs.id
                   )
                """
            )
