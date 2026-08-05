"""Shared shapes every job source returns. Adding a source means producing these."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..models import SearchSettings


@dataclass
class RawJob:
    source: str
    title: str
    job_url: str
    source_job_id: str | None = None
    company: str | None = None
    location: str | None = None
    is_remote: bool | None = None
    job_url_direct: str | None = None
    date_posted: str | None = None
    job_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None
    description: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceResult:
    source: str
    search_term: str
    ok: bool
    jobs: list[RawJob] = field(default_factory=list)
    error: str | None = None


class JobSource(Protocol):
    def __call__(self, settings: SearchSettings, search_term: str) -> SourceResult: ...
