"""Indeed Ireland via python-jobspy."""

import logging

from ..models import SearchSettings
from ..normalise import (
    clean_bool,
    clean_date,
    clean_float,
    clean_location,
    clean_str,
    clean_value,
)
from .base import RawJob, SourceResult

log = logging.getLogger(__name__)

SOURCE = "indeed"

# Kept out of raw_json - large, and not useful for matching.
_RAW_SKIP = {"description", "company_logo", "company_description"}


def _to_raw_job(row) -> RawJob | None:
    title = clean_str(row.get("title"))
    job_url = clean_str(row.get("job_url"))
    if not title or not job_url:
        return None  # unusable without an identity and a real link

    raw = {}
    for key, value in row.items():
        if key in _RAW_SKIP:
            continue
        value = clean_value(value)
        if value is None:
            continue
        raw[key] = value if isinstance(value, (str, int, float, bool)) else str(value)

    return RawJob(
        source=SOURCE,
        source_job_id=clean_str(row.get("id")),
        title=title,
        company=clean_str(row.get("company")),
        location=clean_location(row.get("location")),
        is_remote=clean_bool(row.get("is_remote")),
        job_url=job_url,
        job_url_direct=clean_str(row.get("job_url_direct")),
        date_posted=clean_date(row.get("date_posted")),
        job_type=clean_str(row.get("job_type")),
        salary_min=clean_float(row.get("min_amount")),
        salary_max=clean_float(row.get("max_amount")),
        salary_currency=clean_str(row.get("currency")),
        salary_interval=clean_str(row.get("interval")),
        description=clean_str(row.get("description")),
        raw=raw,
    )


def fetch(settings: SearchSettings, search_term: str) -> SourceResult:
    """One search term against Indeed Ireland. Never raises - failures come back as ok=False."""
    from jobspy import scrape_jobs  # imported lazily; pulls in pandas

    kwargs = dict(
        site_name=["indeed"],
        search_term=search_term,
        location=settings.location,
        country_indeed="Ireland",
        results_wanted=settings.results_per_title,
        hours_old=settings.max_job_age_days * 24,
        description_format="markdown",
        verbose=0,
    )
    # jobspy validates is_remote as a strict bool, so the kwarg must be omitted
    # rather than passed as None. Hybrid/on-site have no equivalent and are
    # filtered locally in the pipeline.
    if settings.work_mode == "remote":
        kwargs["is_remote"] = True

    try:
        df = scrape_jobs(**kwargs)
    except Exception as exc:  # noqa: BLE001 - one failing term must not stop the run
        log.warning("Indeed search failed for %r: %s", search_term, exc)
        return SourceResult(SOURCE, search_term, ok=False, error=f"{type(exc).__name__}: {exc}")

    jobs: list[RawJob] = []
    if df is not None and not df.empty:
        for record in df.to_dict("records"):
            job = _to_raw_job(record)
            if job:
                jobs.append(job)

    log.info("Indeed %r -> %d jobs", search_term, len(jobs))
    return SourceResult(SOURCE, search_term, ok=True, jobs=jobs)
