"""Pydantic models for the API surface."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

WorkMode = Literal["any", "remote", "hybrid", "onsite"]
JobStatus = Literal["new", "saved", "generated", "applied", "interview", "rejected"]

JOB_STATUSES: tuple[str, ...] = (
    "new",
    "saved",
    "generated",
    "applied",
    "interview",
    "rejected",
)

DEFAULT_TITLES = [
    "Software Engineer",
    "AI Engineer",
    "AI Enablement Engineer",
    "Backend Engineer",
    "Full Stack Engineer",
]


def _clean_list(v: list[str]) -> list[str]:
    """Drop blanks and duplicates while preserving the user's ordering."""
    seen: set[str] = set()
    out: list[str] = []
    for item in v:
        item = (item or "").strip()
        if item and item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


class SearchSettings(BaseModel):
    target_titles: list[str] = Field(default_factory=lambda: list(DEFAULT_TITLES))
    keywords: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    excluded_title_words: list[str] = Field(default_factory=list)
    location: str = "Ireland"
    max_job_age_days: int = Field(default=7, ge=1, le=90)
    work_mode: WorkMode = "any"
    results_per_title: int = Field(default=40, ge=5, le=200)
    sources: list[str] = Field(default_factory=lambda: ["indeed"])

    @field_validator(
        "target_titles",
        "keywords",
        "excluded_keywords",
        "excluded_title_words",
        "sources",
    )
    @classmethod
    def _strip_lists(cls, v: list[str]) -> list[str]:
        return _clean_list(v)

    @field_validator("location")
    @classmethod
    def _strip_location(cls, v: str) -> str:
        return v.strip() or "Ireland"


class Job(BaseModel):
    id: int
    source: str
    source_job_id: str | None = None
    title: str
    company: str | None = None
    location: str | None = None
    is_remote: bool | None = None
    job_url: str
    job_url_direct: str | None = None
    date_posted: str | None = None
    job_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None
    description: str | None = None
    status: str = "new"
    relevance_score: float | None = None
    first_seen_at: str
    last_seen_at: str


class JobListResponse(BaseModel):
    items: list[Job]
    total: int
    limit: int
    offset: int


class Stats(BaseModel):
    total_jobs: int
    new_jobs: int
    good_matches: int
    generated_applications: int
    last_refresh_at: str | None = None


class StatusUpdate(BaseModel):
    status: JobStatus


class RefreshError(BaseModel):
    source: str
    search_term: str
    error: str


class RefreshStatus(BaseModel):
    running: bool = False
    run_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    current: str | None = None
    completed: int = 0
    total: int = 0
    found: int = 0
    inserted: int = 0
    updated: int = 0
    filtered: int = 0
    errors: list[RefreshError] = Field(default_factory=list)


class OpenAIKeyUpdate(BaseModel):
    api_key: str
