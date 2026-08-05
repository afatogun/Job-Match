"""Cheap local relevance scoring - no AI, runs on every job at ingest.

Its job is to order the pile and cut the obvious noise so that AI ranking (step 13)
only spends tokens on plausible candidates.
"""

import re
from datetime import date

from .models import SearchSettings
from .normalise import norm_text
from .sources.base import RawJob

# Wording that signals a level well above or below an individual contributor role.
SENIOR_WORDS = {"head", "director", "vp", "chief", "principal", "staff", "lead", "manager"}
JUNIOR_WORDS = {"intern", "internship", "graduate", "trainee", "apprentice", "placement", "student"}

WEIGHTS = {
    "title": 45,
    "keywords": 25,
    "location": 10,
    "freshness": 12,
    "seniority": 8,
}


def _tokens(text: str) -> set[str]:
    return {w for w in norm_text(text).split() if len(w) > 1}


def _title_score(title: str, targets: list[str]) -> float:
    """Best overlap against any one target title, 0..1."""
    if not targets:
        return 0.5
    norm_title = norm_text(title)
    title_tokens = _tokens(title)
    best = 0.0
    for target in targets:
        target_norm = norm_text(target)
        if not target_norm:
            continue
        if target_norm == norm_title:
            return 1.0
        if target_norm in norm_title:
            best = max(best, 0.9)
            continue
        target_tokens = _tokens(target)
        if target_tokens:
            overlap = len(target_tokens & title_tokens) / len(target_tokens)
            best = max(best, overlap * 0.8)
    return best


def _keyword_score(job: RawJob, keywords: list[str]) -> float:
    if not keywords:
        return 0.5  # nothing configured: stay neutral rather than punish everything
    haystack = f"{norm_text(job.title)} {norm_text(job.description)}"
    if not haystack.strip():
        return 0.0
    hits = sum(1 for kw in keywords if norm_text(kw) and norm_text(kw) in haystack)
    # Matching roughly half the configured keywords is already a strong signal.
    return min(1.0, hits / max(1, len(keywords) * 0.5))


def _location_score(job: RawJob, settings: SearchSettings) -> float:
    location = norm_text(job.location)
    wanted = norm_text(settings.location)
    if not location:
        return 0.5
    if job.is_remote and settings.work_mode in ("any", "remote"):
        return 1.0
    if wanted and wanted != "ireland" and wanted in location:
        return 1.0
    # Searches are Ireland-wide, so anything genuinely Irish is fine.
    return 1.0 if "ireland" in location else 0.25


def _freshness_score(date_posted: str | None, max_age_days: int) -> float:
    if not date_posted:
        return 0.5
    try:
        posted = date.fromisoformat(date_posted)
    except ValueError:
        return 0.5
    age = (date.today() - posted).days
    if age <= 0:
        return 1.0
    if age >= max_age_days:
        return 0.2
    return max(0.2, 1.0 - (age / max(1, max_age_days)))


def _seniority_score(title: str) -> float:
    words = _tokens(title)
    if words & JUNIOR_WORDS:
        return 0.15
    if words & SENIOR_WORDS:
        return 0.6
    return 1.0


def score_job(job: RawJob, settings: SearchSettings) -> float:
    """0-100. Deterministic and cheap; never calls out to anything."""
    parts = {
        "title": _title_score(job.title, settings.target_titles),
        "keywords": _keyword_score(job, settings.keywords),
        "location": _location_score(job, settings),
        "freshness": _freshness_score(job.date_posted, settings.max_job_age_days),
        "seniority": _seniority_score(job.title),
    }
    total = sum(parts[k] * WEIGHTS[k] for k in WEIGHTS)
    return round(min(100.0, max(0.0, total)), 1)


def matching_terms(job: RawJob | None, settings: SearchSettings, text: str = "") -> list[str]:
    """Which configured keywords actually appear - shown on the job card."""
    haystack = text or (f"{job.title} {job.description or ''}" if job else "")
    haystack = norm_text(haystack)
    found = []
    for kw in settings.keywords:
        n = norm_text(kw)
        if n and re.search(rf"\b{re.escape(n)}\b", haystack):
            found.append(kw)
    return found[:8]
