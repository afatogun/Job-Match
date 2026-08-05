"""Step 13 - AI job ranking.

Jobs are ranked in batches so we never make one API call per vacancy. Only jobs
that already cleared the cheap local score are considered.
"""

import json
import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .ai import complete_structured
from .db import connect
from .models import SearchSettings
from .profile_store import load_profile

log = logging.getLogger(__name__)

BATCH_SIZE = 8
DESCRIPTION_CHARS = 2500

SYSTEM = """You assess how well a candidate matches job vacancies.

For each job you are given, return an honest assessment. Be discriminating: most
jobs are a partial fit, and a score above 85 should be rare. Judge on evidence in
the candidate profile only - never assume skills that are not shown.

score:         0-100 overall match
reason:        one sentence, max 25 words, concrete and specific to this job
matching_skills: skills the candidate genuinely has that this job asks for
missing_skills:  important requirements the candidate does not evidence
seniority_fit:   one of "below", "good", "above"
"""


class JobAssessment(BaseModel):
    job_id: int
    score: float = Field(ge=0, le=100)
    reason: str = ""
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    seniority_fit: str = "good"


class BatchAssessment(BaseModel):
    assessments: list[JobAssessment]


def _profile_brief(max_chars: int = 4000) -> str:
    profile = load_profile()
    if profile is None:
        return ""
    lines = [
        f"Name: {profile.personal.full_name}",
        f"Summary: {profile.professional_summary}",
        f"Skills: {', '.join(profile.skills)}",
    ]
    for exp in profile.experience[:6]:
        lines.append(
            f"- {exp.role} at {exp.company} ({exp.start_date} - {exp.end_date}): {exp.summary}"
        )
        for a in exp.achievements[:3]:
            lines.append(f"    * {a}")
    if profile.additional_skills:
        lines.append(f"Additional skills: {profile.additional_skills}")
    if profile.notes_for_ai:
        lines.append(f"Notes: {profile.notes_for_ai}")
    return "\n".join(lines)[:max_chars]


def _fetch_candidates(settings: SearchSettings) -> list[dict]:
    """Highest locally-scored jobs that have not been AI-ranked yet."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, company, location, description, local_score
              FROM jobs
             WHERE ai_score IS NULL
               AND COALESCE(local_score, 0) >= ?
             ORDER BY local_score DESC, date_posted DESC
             LIMIT ?
            """,
            (settings.min_score_to_rank, settings.ai_rank_top_n),
        ).fetchall()
    return [dict(r) for r in rows]


def _persist(assessments: list[JobAssessment]) -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    written = 0
    with connect() as conn:
        for a in assessments:
            cur = conn.execute(
                """
                UPDATE jobs
                   SET ai_score = ?, ai_reason = ?, ai_matching_skills = ?,
                       ai_missing_skills = ?, ai_seniority_fit = ?, ai_ranked_at = ?
                 WHERE id = ?
                """,
                (
                    a.score,
                    a.reason.strip(),
                    json.dumps(a.matching_skills[:10]),
                    json.dumps(a.missing_skills[:10]),
                    a.seniority_fit,
                    now,
                    a.job_id,
                ),
            )
            written += cur.rowcount
    return written


def rank_pending_jobs(settings: SearchSettings) -> int:
    """-> number of jobs ranked. Raises if the API is unusable (no key, etc.)."""
    candidates = _fetch_candidates(settings)
    if not candidates:
        return 0

    profile = _profile_brief()
    if not profile:
        # Without a profile there is nothing to match against; local scores stand.
        log.info("Skipping AI ranking: no candidate profile yet")
        return 0

    ranked = 0
    for start in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[start : start + BATCH_SIZE]
        jobs_text = "\n\n".join(
            f"--- JOB {j['id']} ---\n"
            f"Title: {j['title']}\n"
            f"Company: {j['company'] or 'Unknown'}\n"
            f"Location: {j['location'] or 'Unknown'}\n"
            f"Description:\n{(j['description'] or '(no description)')[:DESCRIPTION_CHARS]}"
            for j in batch
        )
        user = (
            f"CANDIDATE PROFILE\n{profile}\n\n"
            f"Assess these {len(batch)} jobs. Return one assessment per job, "
            f"using the exact job_id values shown.\n\n{jobs_text}"
        )

        try:
            result = complete_structured(
                model=settings.openai_model,
                system=SYSTEM,
                user=user,
                schema_model=BatchAssessment,
            )
        except Exception as exc:  # noqa: BLE001 - one bad batch shouldn't lose the rest
            log.warning("Ranking batch failed: %s", exc)
            if start == 0:
                raise  # first batch failing means the API is unusable - surface it
            continue

        valid_ids = {j["id"] for j in batch}
        good = [a for a in result.assessments if a.job_id in valid_ids]
        ranked += _persist(good)

    log.info("AI ranked %d jobs", ranked)
    return ranked


def rank_specific_jobs(job_ids: list[int], settings: SearchSettings) -> int:
    """Re-rank named jobs on demand, ignoring the already-ranked filter."""
    if not job_ids:
        return 0
    placeholders = ",".join("?" * len(job_ids))
    with connect() as conn:
        rows = conn.execute(
            f"SELECT id, title, company, location, description, local_score "
            f"FROM jobs WHERE id IN ({placeholders})",
            job_ids,
        ).fetchall()
    if not rows:
        return 0

    profile = _profile_brief()
    if not profile:
        raise RuntimeError("Add a candidate profile before ranking jobs with AI")

    candidates = [dict(r) for r in rows]
    ranked = 0
    for start in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[start : start + BATCH_SIZE]
        jobs_text = "\n\n".join(
            f"--- JOB {j['id']} ---\nTitle: {j['title']}\nCompany: {j['company'] or 'Unknown'}\n"
            f"Description:\n{(j['description'] or '')[:DESCRIPTION_CHARS]}"
            for j in batch
        )
        result = complete_structured(
            model=settings.openai_model,
            system=SYSTEM,
            user=f"CANDIDATE PROFILE\n{profile}\n\nAssess these jobs.\n\n{jobs_text}",
            schema_model=BatchAssessment,
        )
        valid_ids = {j["id"] for j in batch}
        ranked += _persist([a for a in result.assessments if a.job_id in valid_ids])
    return ranked
