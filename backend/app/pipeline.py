"""Refresh orchestration: collect -> normalise -> filter -> score -> dedup -> store -> rank.

Runs on a FastAPI background task with an in-memory status the UI polls.
No worker/queue infrastructure.
"""

import json
import logging
import threading
import uuid
from datetime import datetime, timezone

from .db import connect
from .models import RefreshError, RefreshStatus, SearchSettings
from .normalise import content_key, dedup_key, norm_text
from .scoring import matching_terms, score_job
from .settings_store import load_settings
from .sources.base import RawJob
from .sources.registry import get_source, label_for

log = logging.getLogger(__name__)

_lock = threading.Lock()
_status = RefreshStatus()


def get_status() -> RefreshStatus:
    with _lock:
        return _status.model_copy(deep=True)


def is_running() -> bool:
    with _lock:
        return _status.running


def mark_queued() -> RefreshStatus:
    """Flip to running when the request is accepted.

    BackgroundTasks only fires after the response is sent, so without this the
    first poll would report 'not running' and the UI would flicker.
    """
    global _status
    with _lock:
        _status = RefreshStatus(running=True, started_at=_now(), current="Starting...")
        return _status.model_copy(deep=True)


def _update(**kwargs) -> None:
    with _lock:
        for key, value in kwargs.items():
            setattr(_status, key, value)


def _bump(**kwargs) -> None:
    with _lock:
        for key, value in kwargs.items():
            setattr(_status, key, getattr(_status, key) + value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_excluded(job: RawJob, settings: SearchSettings) -> str | None:
    """The brief's 'reject obviously irrelevant jobs' - explicit exclusions only.

    Scored relevance is handled separately; this stage is deliberately dumb.
    """
    title = norm_text(job.title)
    for word in settings.excluded_title_words:
        if norm_text(word) and norm_text(word) in title:
            return f"excluded title word: {word}"

    haystack = f"{title} {norm_text(job.description)}"
    for word in settings.excluded_keywords:
        if norm_text(word) and norm_text(word) in haystack:
            return f"excluded keyword: {word}"

    # jobspy has no hybrid/onsite filter, so approximate it from the text we have.
    if settings.work_mode in ("hybrid", "onsite"):
        text = f"{norm_text(job.location)} {haystack}"
        if settings.work_mode == "hybrid" and "hybrid" not in text:
            return "not hybrid"
        if settings.work_mode == "onsite" and job.is_remote is True:
            return "remote, wanted on-site"
    return None


def _store(conn, job: RawJob, dkey: str, ckey: str, score: float, terms: list[str]) -> str:
    """-> 'inserted' | 'updated'. Existing rows are refreshed, never duplicated."""
    now = _now()

    row = conn.execute(
        "SELECT id, description FROM jobs WHERE dedup_key = ? LIMIT 1", (dkey,)
    ).fetchone()

    # Same vacancy reached us under a different identity (e.g. another board).
    if row is None:
        row = conn.execute(
            "SELECT id, description FROM jobs WHERE content_key = ? LIMIT 1", (ckey,)
        ).fetchone()

    if row is not None:
        conn.execute(
            """
            UPDATE jobs
               SET last_seen_at   = ?,
                   description    = COALESCE(NULLIF(description, ''), ?),
                   job_url_direct = COALESCE(job_url_direct, ?),
                   local_score    = ?,
                   matching_terms = ?
             WHERE id = ?
            """,
            (now, job.description, job.job_url_direct, score, json.dumps(terms), row["id"]),
        )
        return "updated"

    conn.execute(
        """
        INSERT INTO jobs (
            dedup_key, content_key, source, source_job_id, title, company, location,
            is_remote, job_url, job_url_direct, date_posted, job_type,
            salary_min, salary_max, salary_currency, salary_interval,
            description, status, local_score, matching_terms,
            first_seen_at, last_seen_at, raw_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'new',?,?,?,?,?)
        """,
        (
            dkey,
            ckey,
            job.source,
            job.source_job_id,
            job.title,
            job.company,
            job.location,
            None if job.is_remote is None else int(job.is_remote),
            job.job_url,
            job.job_url_direct,
            job.date_posted,
            job.job_type,
            job.salary_min,
            job.salary_max,
            job.salary_currency,
            job.salary_interval,
            job.description,
            score,
            json.dumps(terms),
            now,
            now,
            json.dumps(job.raw, default=str),
        ),
    )
    return "inserted"


def _record_run(conn, run_id: str, started: str, result_source: str, term: str,
                ok: bool, found: int, inserted: int, error: str | None) -> None:
    conn.execute(
        """
        INSERT INTO refresh_runs (run_id, started_at, finished_at, source, search_term,
                                  ok, found, inserted, error)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (run_id, started, _now(), result_source, term, int(ok), found, inserted, error),
    )


def run_refresh() -> None:
    """Entry point for the background task. Swallows nothing silently - all errors surface."""
    run_id = uuid.uuid4().hex[:12]
    settings = load_settings()

    tasks = [
        (source_name, term)
        for source_name in settings.sources
        for term in settings.target_titles
    ]

    global _status
    with _lock:
        _status = RefreshStatus(
            running=True, run_id=run_id, started_at=_now(), total=len(tasks)
        )

    seen_this_run: set[str] = set()

    try:
        for source_name, term in tasks:
            _update(current=f"{label_for(source_name)} - {term}")
            started = _now()
            source = get_source(source_name)

            if source is None:
                msg = f"unknown source '{source_name}'"
                with _lock:
                    _status.errors.append(RefreshError(source=source_name, search_term=term, error=msg))
                with connect() as conn:
                    _record_run(conn, run_id, started, source_name, term, False, 0, 0, msg)
                _bump(completed=1)
                continue

            result = source(settings, term)
            inserted = updated = filtered = 0

            if result.ok:
                with connect() as conn:
                    for job in result.jobs:
                        reason = is_excluded(job, settings)
                        if reason:
                            filtered += 1
                            continue

                        ckey = content_key(job.company, job.title, job.location)
                        dkey = dedup_key(job.source, job.source_job_id, job.job_url, ckey)
                        if dkey in seen_this_run:
                            continue  # duplicate within this run's own results
                        seen_this_run.add(dkey)

                        score = score_job(job, settings)
                        terms = matching_terms(job, settings)

                        try:
                            if _store(conn, job, dkey, ckey, score, terms) == "inserted":
                                inserted += 1
                            else:
                                updated += 1
                        except Exception as exc:  # noqa: BLE001 - one bad row must not kill the batch
                            log.warning("Failed to store %r from %s: %s", job.title, job.source, exc)
                    _record_run(conn, run_id, started, source_name, term, True,
                                len(result.jobs), inserted, None)
                _bump(found=len(result.jobs), inserted=inserted, updated=updated, filtered=filtered)
            else:
                with _lock:
                    _status.errors.append(
                        RefreshError(source=source_name, search_term=term, error=result.error or "unknown error")
                    )
                with connect() as conn:
                    _record_run(conn, run_id, started, source_name, term, False, 0, 0, result.error)

            _bump(completed=1)

        _rank_with_ai(settings)
    except Exception as exc:  # noqa: BLE001 - never leave the UI stuck on "running"
        log.exception("Refresh run failed")
        with _lock:
            _status.errors.append(RefreshError(source="refresh", search_term="-", error=str(exc)))
    finally:
        _update(running=False, finished_at=_now(), current=None)
        log.info("Refresh %s complete", run_id)


def _rank_with_ai(settings: SearchSettings) -> None:
    """Best-effort AI ranking of the strongest unranked jobs. Never fails a refresh."""
    if settings.ai_rank_top_n <= 0:
        return

    from .ranking import rank_pending_jobs  # local import: keeps refresh usable without a key

    try:
        _update(current="Ranking best matches with AI...")
        ranked = rank_pending_jobs(settings)
        _bump(ranked=ranked)
    except Exception as exc:  # noqa: BLE001 - discovery must still succeed
        log.warning("AI ranking skipped: %s", exc)
        with _lock:
            _status.errors.append(
                RefreshError(source="openai", search_term="ranking", error=str(exc))
            )
