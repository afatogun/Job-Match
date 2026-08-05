"""The extension point for job sources.

Adding a source = one module exposing fetch(settings, search_term) -> SourceResult,
plus one entry here. The pipeline needs no changes.
"""

from . import jobsireland
from .base import JobSource
from .jobspy_source import make_fetcher

SOURCES: dict[str, JobSource] = {
    "indeed": make_fetcher("indeed"),
    "glassdoor": make_fetcher("glassdoor"),
    "jobsireland": jobsireland.fetch,
    # LinkedIn rate-limits aggressively without proxies. Supported, off by default.
    "linkedin": make_fetcher("linkedin"),
}

# Shown in the UI so labels stay consistent with the stored `source` value.
SOURCE_LABELS: dict[str, str] = {
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
    "jobsireland": "JobsIreland",
    "linkedin": "LinkedIn",
}

# Sources known to fail often; the UI warns rather than treating this as breakage.
UNRELIABLE_SOURCES: set[str] = {"linkedin"}


def get_source(name: str) -> JobSource | None:
    return SOURCES.get(name)


def label_for(name: str) -> str:
    return SOURCE_LABELS.get(name, name.title())
