"""Indeed, Glassdoor and LinkedIn via python-jobspy.

All three share one implementation; they differ only in which kwargs jobspy accepts
and in how reliable they are. LinkedIn rate-limits hard without proxies, so it is
opt-in and its failures are treated as routine.
"""

import logging

from ..models import SearchSettings
from ..normalise import (
    clean_bool,
    clean_date,
    clean_float,
    clean_location,
    clean_str,
    clean_value,
    norm_text,
)
from .base import RawJob, SourceResult

log = logging.getLogger(__name__)

# Kept out of raw_json - large, and not useful for matching.
_RAW_SKIP = {"description", "company_logo", "company_description"}

# jobspy's own Country enum only accepts "uk"/"united kingdom" - these are common
# ways people actually type a UK location that it doesn't recognise natively.
_COUNTRY_ALIASES = {
    "northern ireland": "uk",
    "england": "uk",
    "scotland": "uk",
    "wales": "uk",
    "britain": "uk",
    "great britain": "uk",
    "gb": "uk",
}


def _resolve_country(explicit: str, location: str) -> str:
    """jobspy-recognised country string for the country_indeed kwarg.

    Priority: an explicit setting (unless "auto"/blank) beats inference from the
    free-text location's trailing comma segments (country conventionally comes
    last, e.g. "Belfast, Northern Ireland"), which beats the historical default.
    """
    from jobspy.model import Country  # lazy: importing jobspy pulls in pandas

    def _normalise(raw: str) -> str | None:
        token = norm_text(raw)
        if not token:
            return None
        token = _COUNTRY_ALIASES.get(token, token)
        try:
            Country.from_string(token)
        except ValueError:
            return None
        return token

    explicit_norm = norm_text(explicit)
    if explicit_norm and explicit_norm != "auto":
        resolved = _normalise(explicit_norm)
        if resolved:
            return resolved

    for segment in reversed((location or "").split(",")):
        resolved = _normalise(segment)
        if resolved:
            return resolved

    return "ireland"


def _to_raw_job(row: dict, source: str) -> RawJob | None:
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
        source=source,
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


class _ErrorCapture(logging.Handler):
    """Collects jobspy's own ERROR records.

    jobspy swallows HTTP failures internally and returns an empty DataFrame, so
    without this a blocked source is indistinguishable from "no jobs matched".

    It names its loggers "JobSpy:Indeed", "JobSpy:Glassdoor" and so on, and sets
    propagate = False on each, so neither the root logger nor a "JobSpy" parent
    ever sees these records. We have to attach to each one directly.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.messages.append(record.getMessage())
        except Exception:  # noqa: BLE001 - logging must never raise
            pass


def _jobspy_loggers() -> list[logging.Logger]:
    return [
        logging.getLogger(name)
        for name in list(logging.root.manager.loggerDict)
        if name.startswith("JobSpy")
    ]


def fetch(site: str, settings: SearchSettings, search_term: str) -> SourceResult:
    """One search term against one jobspy site. Never raises."""
    from jobspy import scrape_jobs  # imported lazily; pulls in pandas

    kwargs: dict = dict(
        site_name=[site],
        search_term=search_term,
        location=settings.location,
        results_wanted=settings.results_per_title,
        hours_old=settings.max_job_age_days * 24,
        description_format="markdown",
        verbose=0,
    )

    # country_indeed drives the regional site for both Indeed and Glassdoor.
    if site in ("indeed", "glassdoor"):
        kwargs["country_indeed"] = _resolve_country(settings.country, settings.location)

    # LinkedIn omits the description unless asked, which costs one request per job.
    if site == "linkedin":
        kwargs["linkedin_fetch_description"] = True

    # jobspy validates is_remote as a strict bool, so the kwarg must be omitted
    # rather than passed as None. Hybrid/on-site have no equivalent and are
    # filtered locally in the pipeline.
    if settings.work_mode == "remote":
        kwargs["is_remote"] = True

    capture = _ErrorCapture()
    listeners = _jobspy_loggers()
    for logger in listeners:
        logger.addHandler(capture)
    try:
        df = scrape_jobs(**kwargs)
    except Exception as exc:  # noqa: BLE001 - one failing term must not stop the run
        log.warning("%s search failed for %r: %s", site, search_term, exc)
        return SourceResult(site, search_term, ok=False, error=f"{type(exc).__name__}: {exc}")
    finally:
        for logger in listeners:
            logger.removeHandler(capture)

    jobs: list[RawJob] = []
    if df is not None and not df.empty:
        for record in df.to_dict("records"):
            job = _to_raw_job(record, site)
            if job:
                jobs.append(job)

    # Nothing returned *and* the scraper logged errors means the source is broken
    # or blocking us, not that the search genuinely had no matches.
    if not jobs and capture.messages:
        detail = "; ".join(dict.fromkeys(capture.messages))[:300]
        log.warning("%s returned nothing for %r: %s", site, search_term, detail)
        return SourceResult(site, search_term, ok=False, error=detail)

    log.info("%s %r -> %d jobs", site, search_term, len(jobs))
    return SourceResult(site, search_term, ok=True, jobs=jobs)


def make_fetcher(site: str):
    """Bind a jobspy site name into the source signature the registry expects."""

    def _fetch(settings: SearchSettings, search_term: str) -> SourceResult:
        return fetch(site, settings, search_term)

    _fetch.__name__ = f"fetch_{site}"
    return _fetch
