"""Job listing, detail, status, refresh and dashboard stats."""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from ..db import connect
from ..models import Job, JobListResponse, RefreshStatus, Stats, StatusUpdate
from ..pipeline import get_status, is_running, mark_queued, run_refresh

router = APIRouter(prefix="/api", tags=["jobs"])

GOOD_MATCH_THRESHOLD = 70.0

_JOB_COLUMNS = """
    id, source, source_job_id, title, company, location, is_remote, job_url,
    job_url_direct, date_posted, job_type, salary_min, salary_max, salary_currency,
    salary_interval, status, relevance_score, first_seen_at, last_seen_at
"""


def _to_job(row, include_description: bool = False) -> Job:
    data = dict(row)
    data["is_remote"] = None if data.get("is_remote") is None else bool(data["is_remote"])
    if not include_description:
        data["description"] = None
    return Job.model_validate(data)


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    q: str | None = None,
    source: str | None = None,
    status: str | None = None,
    posted_within_days: int | None = Query(default=None, ge=1, le=365),
    min_score: float | None = Query(default=None, ge=0, le=100),
    sort: Literal["newest", "best"] = "newest",
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
    if posted_within_days is not None:
        cutoff = (date.today() - timedelta(days=posted_within_days)).isoformat()
        # Undated postings are kept rather than silently hidden.
        where.append("(date_posted IS NULL OR date_posted >= ?)")
        params.append(cutoff)
    if min_score is not None:
        where.append("relevance_score >= ?")
        params.append(min_score)

    clause = f"WHERE {' AND '.join(where)}" if where else ""
    # Scores are NULL until step 10, so 'best' still needs a stable secondary key.
    order = (
        "ORDER BY relevance_score DESC NULLS LAST, date_posted DESC NULLS LAST, id DESC"
        if sort == "best"
        else "ORDER BY date_posted DESC NULLS LAST, id DESC"
    )

    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n FROM jobs {clause}", params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT {_JOB_COLUMNS} FROM jobs {clause} {order} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()

    return JobListResponse(
        items=[_to_job(r) for r in rows], total=total, limit=limit, offset=offset
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
    return _to_job(row, include_description=True)


@router.patch("/jobs/{job_id}", response_model=Job)
def update_status(job_id: int, payload: StatusUpdate) -> Job:
    with connect() as conn:
        cur = conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (payload.status, job_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Job not found")
        row = conn.execute(
            f"SELECT {_JOB_COLUMNS}, description FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return _to_job(row, include_description=True)


@router.get("/stats", response_model=Stats)
def stats() -> Stats:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(status = 'new'), 0) AS new_jobs,
                   COALESCE(SUM(relevance_score >= ?), 0) AS good_matches,
                   COALESCE(SUM(status = 'generated'), 0) AS generated
              FROM jobs
            """,
            (GOOD_MATCH_THRESHOLD,),
        ).fetchone()
        last = conn.execute(
            "SELECT MAX(finished_at) AS last FROM refresh_runs"
        ).fetchone()

    return Stats(
        total_jobs=row["total"],
        new_jobs=row["new_jobs"],
        good_matches=row["good_matches"],
        generated_applications=row["generated"],
        last_refresh_at=last["last"] if last else None,
    )
