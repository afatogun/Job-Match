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
MID_SYNONYMS = {"mid", "middle", "medior", "ii", "2"}  # common ways mid-level is written

LEVEL_ALIASES: dict[str, set[str]] = {
    "junior": {"junior", "jr", "entry", "entry-level", "graduate", "intern", "internship", "trainee"},
    "mid": {"mid", "middle", "medior", "intermediate", "ii", "2"},
    "senior": {
        "senior",
        "sr",
        "lead",
        "principal",
        "staff",
        "manager",
        "head",
        "director",
        "vp",
        "chief",
    },
}

YEARS_RANGE_RE = re.compile(
    r"\b(?P<low>\d{1,2})\s*(?:-|to)\s*(?P<high>\d{1,2})\s*\+?\s*(?:years?|yrs?)\b"
)
YEARS_SINGLE_RE = re.compile(r"\b(?P<num>\d{1,2})\s*\+\s*(?:years?|yrs?)\b")
YEARS_AT_LEAST_RE = re.compile(r"\b(?:at\s+least|minimum\s+of)\s*(?P<num>\d{1,2})\s*(?:years?|yrs?)\b")

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
    if not wanted:
        return 0.5
    if wanted == location or wanted in location:
        return 1.0
    # Word-overlap rather than a hardcoded country name, so any configured
    # location - not just Ireland - gets proportional credit.
    wanted_tokens = _tokens(settings.location)
    if not wanted_tokens:
        return 0.5
    overlap = len(wanted_tokens & _tokens(job.location)) / len(wanted_tokens)
    return max(0.25, overlap)


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


def _seniority_score(title: str, desired_levels: list[str]) -> float:
    return _seniority_years_score(title, None, desired_levels, None, None)


def _normalize_desired_levels(levels: list[str]) -> set[str]:
    out: set[str] = set()
    for lv in levels:
        n = norm_text(lv)
        if not n:
            continue
        if n in LEVEL_ALIASES:
            out.add(n)
            continue
        for canonical, aliases in LEVEL_ALIASES.items():
            if n in aliases:
                out.add(canonical)
                break
    return out


def _infer_level(title: str, description: str | None) -> str | None:
    words = _tokens(f"{title} {description or ''}")
    if words & JUNIOR_WORDS:
        return "junior"
    if words & MID_SYNONYMS:
        return "mid"
    if words & SENIOR_WORDS:
        return "senior"
    for canonical, aliases in LEVEL_ALIASES.items():
        if words & aliases:
            return canonical
    return None


def _infer_years_range(title: str, description: str | None) -> tuple[int | None, int | None]:
    text = norm_text(f"{title} {description or ''}")
    ranges: list[tuple[int, int]] = []

    for m in YEARS_RANGE_RE.finditer(text):
        lo = int(m.group("low"))
        hi = int(m.group("high"))
        if lo > hi:
            lo, hi = hi, lo
        ranges.append((lo, hi))

    for m in YEARS_SINGLE_RE.finditer(text):
        lo = int(m.group("num"))
        ranges.append((lo, lo + 8))

    for m in YEARS_AT_LEAST_RE.finditer(text):
        lo = int(m.group("num"))
        ranges.append((lo, lo + 8))

    if ranges:
        return min(lo for lo, _ in ranges), max(hi for _, hi in ranges)

    inferred_level = _infer_level(title, description)
    if inferred_level == "junior":
        return (0, 3)
    if inferred_level == "mid":
        return (2, 6)
    if inferred_level == "senior":
        return (5, 15)
    return (None, None)


def _ranges_overlap(a_min: int, a_max: int, b_min: int, b_max: int) -> bool:
    return a_min <= b_max and b_min <= a_max


def _seniority_years_score(
    title: str,
    description: str | None,
    desired_levels: list[str],
    min_years_pref: int | None,
    max_years_pref: int | None,
) -> float:
    inferred_level = _infer_level(title, description)
    wanted_levels = _normalize_desired_levels(desired_levels)

    if wanted_levels:
        if inferred_level and inferred_level in wanted_levels:
            level_score = 1.0
        elif inferred_level and inferred_level not in wanted_levels:
            # Strong soft-penalty: visible but pushed down when level is clearly off-target.
            level_score = 0.25
        else:
            level_score = 0.7
    else:
        level_score = 1.0

    pref_min = min_years_pref
    pref_max = max_years_pref
    years_min, years_max = _infer_years_range(title, description)
    if pref_min is None and pref_max is None:
        return level_score
    if pref_min is None:
        pref_min = 0
    if pref_max is None:
        pref_max = 40

    if years_min is not None and years_max is not None:
        if _ranges_overlap(years_min, years_max, pref_min, pref_max):
            return min(1.0, level_score + 0.05)
        return level_score * 0.35

    # We do not know the years range: keep result soft-penalized rather than excluded.
    return level_score * 0.85


def score_job(job: RawJob, settings: SearchSettings) -> float:
    """0-100. Deterministic and cheap; never calls out to anything."""
    parts = {
        "title": _title_score(job.title, settings.target_titles),
        "keywords": _keyword_score(job, settings.keywords),
        "location": _location_score(job, settings),
        "freshness": _freshness_score(job.date_posted, settings.max_job_age_days),
        "seniority": _seniority_years_score(
            job.title,
            job.description,
            settings.target_levels,
            settings.min_years_experience,
            settings.max_years_experience,
        ),
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
