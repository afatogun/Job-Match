"""Step 14a - read the vacancy properly before writing anything.

One call cannot both work out what a job ad demands and write a CV against it. Asked to
do both, a model does the easy half: it restates the profile in the ad's vocabulary and
calls that tailoring. So the ad is read on its own first, diffed against the profile, and
the result handed to the writing pass as a list of things to say rather than a problem to
solve.

The analysis is deliberately level-independent. It describes the full picture, including
bridges that only aggressive is allowed to use, and `filter_for_level` narrows it in
Python afterwards. That is what lets one cached analysis serve all three levels and every
regeneration.
"""

import logging
from datetime import datetime, timezone

from .ai import complete_structured
from .generation import (
    ANALYSIS_DESCRIPTION_CHARS,
    _job_text,
    _profile_text,
)
from .humanize import clean_text
from .models import Augmentation, JobGapAnalysis, Profile
from .normalise import json_list

log = logging.getLogger(__name__)

# Seniority works in both directions. A reframed title must not gain a senior word it
# never had, and must not quietly shed the junior one it did: dropping "Graduate" from
# "Graduate Software Engineer" is a promotion by deletion.
SENIORITY_TOKENS = (
    "senior", "lead", "principal", "staff", "head", "vp", "vice president",
    "director", "manager", "chief", "architect",
)
JUNIOR_TOKENS = (
    "graduate", "junior", "intern", "trainee", "apprentice", "placement", "associate",
)

# The only things that genuinely cannot be bridged. Everything else - a framework, a
# cloud service, an architecture pattern - is what the bridges are for.
HARD_BLOCKER_TOKENS = (
    "certification", "certified", "licence", "license", "clearance", "accredit",
    "chartered", "phd", "doctorate", "master's degree", "degree in", "native speaker",
    "fluent in", "years of experience", "years' experience", "+ years", "visa",
    "right to work", "must be based", "qualified accountant", "registered",
)
MAX_HARD_BLOCKERS = 3

GAP_ANALYSIS_SYSTEM = """You read one job advert and one candidate profile, and produce a
structured account of what the vacancy demands and how far the candidate is from it.

You are not writing a CV. You are the research step that a CV will be written from.

Extract 12 to 18 requirements, drawn from BOTH the responsibilities and the qualifications
sections. Rank them by how central they are to the role.

Do not stop at the required qualifications. The preferred and nice-to-have section is
where the requirements that actually separate candidates live, and it is the section most
often skimmed. Every specific named tool, framework, protocol, product or technique
anywhere in the advert becomes a requirement of its own, however far down it appears:
name them one by one rather than collapsing them into "AI orchestration frameworks". A
requirement you never extract is a requirement the CV will never answer.

Every requirement goes in exactly one of `covered` or `gaps`. Never both, and never
neither. There is no third bucket: a requirement you are unsure about is a gap.

`covered` is the narrow case, capped at six entries. It means the profile proves the
WHOLE requirement, and you can quote the exact profile line that does it in
profile_evidence. strength is "direct" when the profile says it outright and "adjacent"
when the profile's work plainly required it without naming it.

A requirement that names several things is covered only if the profile evidences all of
them. "Docker and Kubernetes" where the profile has Docker alone is a GAP, not evidence.
If you catch yourself writing a caveat into profile_evidence, such as "Kubernetes not
explicitly mentioned", you have just proved it is a gap. Move it.

`gaps` is everything else, and it should be the longer list by far.

Be blunt. A requirement you record as covered when it is not both produces a CV that
collapses at interview and, worse, means nothing gets written to close it.

For every gap:
- `nearest_real_experience` is the closest true thing in the profile.
- `bridge_role` names the ONE real role from the profile this is most credibly attached
  to. Use exactly the form "Role at Company", copying both from the profile. Never invent
  an employer.
- `bridge_claim` is a single bullet-shaped sentence asserting the work, written as
  settled fact in the past tense, specific enough to be worth reading. Name the actual
  technology and what it did. Not "worked with vector databases" but "rebuilt retrieval
  on hybrid search with a reranking stage".
  A bridge_claim is always a positive statement of work done. It never says what the
  candidate did not do, and it never contains "but", "without", "no explicit" or "did
  not". Those belong in bridge_credibility, which is where your honesty about the reach
  is recorded. This field is copied almost verbatim into the CV, so a sentence describing
  an absence is worse than useless.
  Never hedge it either. No "which could relate to", no "analogous to", no "conceptually
  similar", no "supporting work that resembles". If the only honest way to write the claim
  is to hedge it, the bridge does not work: mark it implausible instead.
- `bridge_credibility` is your judgement of how far the claim reaches:
  "natural"     - the role's real work already implies this; saying it is barely a stretch
  "stretch"     - this employer could plausibly have needed it, but the profile does not
                  suggest it happened
  "implausible" - this employer would not have done this at all, or the claim needs
                  seniority, a domain or a scale the candidate has never had
- `metric_hint` says what KIND of number would be credible here and roughly how large,
  for example "retrieval latency, hundreds of milliseconds down to tens" or "document
  volume, hundreds of thousands, not millions". This is a magnitude band, not a number.
- `skill_tokens` are the exact tokens an applicant tracking system would scan for,
  spelled as the advert spells them.

A gap is not a warning. It is an instruction to write something. Expect most requirements
to be gaps: a candidate who already evidenced everything would not need this analysis.
Unless the profile genuinely covers nearly the whole advert, produce at least six gaps.

`do_not_claim` is NOT where the difficult requirements go. It is a hard-blocker list, it
is capped at three items, and most vacancies produce none at all. Something belongs there
only when no amount of reframing could ever produce it, which means exactly one of:
- a licence, certification, security clearance or degree the candidate does not hold
- a spoken language
- an explicit number of years the candidate cannot reach
- a regulated industry the candidate has demonstrably never worked in

A tool, framework, library, cloud service, architecture pattern or engineering practice
is NEVER a hard blocker and NEVER belongs in do_not_claim. Kubernetes, LangChain, MLflow,
gRPC, agentic workflows, guardrails, prompt versioning, evaluation harnesses, hybrid
search, reranking, tracing, observability, MLOps and cloud platforms are the whole reason
this analysis exists. Every one of them is a gap with a bridge_role and a bridge_claim, at
whatever credibility you honestly judge. If you put one in do_not_claim you have deleted
the work instead of doing it.

If your do_not_claim list is longer than three items, you are using it wrong. Move
everything that is a tool, a framework or a practice into gaps.

`title_reframes` suggests, per real role, a title pointed at this vacancy that keeps the
same employer, the same dates and the same seniority. "Graduate Software Engineer" may
become "Graduate Software Engineer, AI Platform". It may never gain Senior, Lead,
Principal, Staff, Head, Director, Manager or Chief. Leave the list empty if no role would
benefit.

Never suggest the advertised job title itself. A CV whose past role is named exactly after
the vacancy it is applying to reads as though the advert was pasted into it, which is the
one thing that makes the whole document obvious. Move toward the vacancy's field, not onto
its title.

`positioning_statement` is one or two sentences naming the story this CV has to tell.
`role_archetype` names the kind of engineer this advert is really looking for.
`ats_keywords` are the terms that must appear verbatim somewhere in the CV.
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _prior_assessment(job: dict) -> str:
    """The AI ranking pass already did a cheap version of this. Reuse it as a hint.

    It is a hint and not ground truth: ranking sees a 2500-char excerpt of the advert and
    caps its lists at ten items, and it has not run at all on unranked jobs.
    """
    matching = json_list(job.get("ai_matching_skills"))
    missing = json_list(job.get("ai_missing_skills"))
    reason = job.get("ai_reason") or ""
    seniority = job.get("ai_seniority_fit") or ""
    if not (matching or missing or reason or seniority):
        return ""

    lines = [
        "PRIOR MATCH ASSESSMENT",
        "A cheap earlier pass over a truncated version of this advert. Possibly "
        "incomplete and possibly wrong. Verify everything against the full description "
        "above rather than inheriting it.",
    ]
    if reason:
        lines.append(f"Verdict: {reason}")
    if seniority:
        lines.append(f"Seniority fit: {seniority}")
    if matching:
        lines.append(f"Thought to be covered: {', '.join(matching)}")
    if missing:
        lines.append(f"Thought to be missing: {', '.join(missing)}")
    return "\n".join(lines)


def _introduces_seniority(original: str, suggested: str) -> bool:
    """True when a reframe changes the level the title implies, in either direction."""
    low_original, low_suggested = original.lower(), suggested.lower()
    gained_senior = any(
        token in low_suggested and token not in low_original for token in SENIORITY_TOKENS
    )
    lost_junior = any(
        token in low_original and token not in low_suggested for token in JUNIOR_TOKENS
    )
    return gained_senior or lost_junior


def _real_blockers_only(items: list[str]) -> list[str]:
    """Stop do_not_claim being used as a bin for the hard requirements.

    Left to itself the model routes anything difficult here - Kubernetes, agentic
    workflows, LangChain, MLOps, even a cloud platform the candidate demonstrably uses -
    and every one of those then becomes forbidden vocabulary in the CV. That deletes the
    work instead of doing it, and it is the single thing most likely to leave aggressive
    reading tame. The prompt says so at length; this makes it true regardless.

    A hard blocker is a credential, a language, a stated number of years, or a right to
    work. Nothing else survives, and at most three do.
    """
    blockers = [
        item
        for item in items
        if any(token in item.lower() for token in HARD_BLOCKER_TOKENS)
    ]
    dropped = len(items) - len(blockers)
    if dropped:
        log.info("Dropped %d do_not_claim entries that were not hard blockers", dropped)
    return blockers[:MAX_HARD_BLOCKERS]


def analyse_gap(profile: Profile, job: dict, model: str) -> JobGapAnalysis:
    """One structured pass over the advert. Takes no augmentation level by design."""
    sections = [f"TARGET VACANCY\n{_job_text(job, ANALYSIS_DESCRIPTION_CHARS)}"]
    prior = _prior_assessment(job)
    if prior:
        sections.append(prior)
    sections.append(f"CANDIDATE PROFILE\n{_profile_text(profile)}")
    sections.append("Produce the analysis.")

    analysis = complete_structured(
        model=model,
        system=GAP_ANALYSIS_SYSTEM,
        user="\n\n".join(sections),
        schema_model=JobGapAnalysis,
        max_tokens=6000,
    )

    real_roles = {
        f"{exp.role} at {exp.company}".lower() for exp in profile.experience
    }

    # A bridge attached to an employer that does not exist is worse than no bridge - it
    # is the one thing no augmentation level is allowed to produce. Dropped rather than
    # forbidden: the requirement is still fair to write about, just not from that role.
    kept = []
    for gap in analysis.gaps:
        if gap.bridge_role and gap.bridge_role.lower() not in real_roles:
            log.info(
                "Dropping bridge for %r: unknown role %r", gap.requirement, gap.bridge_role
            )
            continue
        kept.append(gap)
    analysis.gaps = kept

    # A requirement claimed as covered with nothing quotable behind it is a gap wearing a
    # disguise, and the writing pass would treat it as settled evidence. Models also list
    # the same requirement in both places; where they do, the gap is the honest reading.
    gap_keys = {g.requirement.strip().lower() for g in analysis.gaps}
    analysis.covered = [
        item
        for item in analysis.covered
        if item.profile_evidence.strip()
        and item.requirement.strip().lower() not in gap_keys
    ]

    analysis.do_not_claim = _real_blockers_only(analysis.do_not_claim)

    # A past role named exactly after the vacancy is the clearest sign the advert was
    # pasted into the CV, which undoes the point of tailoring it well.
    advertised = (job.get("title") or "").strip().lower()
    analysis.title_reframes = [
        reframe
        for reframe in analysis.title_reframes
        if reframe.suggested_role
        and not _introduces_seniority(reframe.original_role, reframe.suggested_role)
        and (not advertised or reframe.suggested_role.strip().lower() != advertised)
    ]

    analysis.positioning_statement = clean_text(analysis.positioning_statement)
    analysis.headline_suggestion = clean_text(analysis.headline_suggestion)
    analysis.generated_at = analysis.generated_at or _now()
    return analysis


def filter_for_level(analysis: JobGapAnalysis, level: Augmentation) -> JobGapAnalysis:
    """Narrow the full analysis to what a given level is allowed to act on.

    Deterministic, so the model is never asked to police its own licence, and so the
    same cached analysis can serve every level.
    """
    filtered = analysis.model_copy(deep=True)

    # Implausible bridges are dropped everywhere. They become honest gaps instead, which
    # the cover letter can use.
    implausible = [g for g in filtered.gaps if g.bridge_credibility == "implausible"]
    filtered.do_not_claim = list(
        dict.fromkeys(filtered.do_not_claim + [g.requirement for g in implausible])
    )

    if level == "enhanced":
        # Enhanced may only surface what the real work already implies, and never a
        # number or a retitled role.
        filtered.gaps = [g for g in filtered.gaps if g.bridge_credibility == "natural"]
        for gap in filtered.gaps:
            gap.metric_hint = ""
        filtered.title_reframes = []
    else:
        filtered.gaps = [
            g for g in filtered.gaps if g.bridge_credibility in ("natural", "stretch")
        ]

    return filtered


def render_for_prompt(analysis: JobGapAnalysis, level: Augmentation) -> str:
    """Compact text, not JSON.

    JSON spends tokens on syntax and reads as data to be summarised. A flat outline reads
    as instructions to be followed.
    """
    view = filter_for_level(analysis, level)
    lines: list[str] = []

    if view.role_archetype:
        lines.append(f"What this advert is really hiring: {view.role_archetype}")
    if view.seniority and view.seniority != "unknown":
        lines.append(f"Seniority: {view.seniority}")
    if view.positioning_statement:
        lines.append(f"Positioning: {view.positioning_statement}")
    if view.headline_suggestion:
        lines.append(f"Suggested headline direction: {view.headline_suggestion}")
    if view.ats_keywords:
        lines.append(f"Terms that must appear verbatim: {', '.join(view.ats_keywords)}")

    if view.covered:
        lines.append("\nALREADY EVIDENCED, lead with these:")
        for item in view.covered:
            label = item.jd_phrase or item.requirement
            lines.append(f'- [{item.importance}] "{label}"')
            if item.profile_evidence:
                lines.append(f"    evidence: {item.profile_evidence}")
            if item.evidence_role:
                lines.append(f"    from: {item.evidence_role}")

    if view.gaps:
        header = (
            "\nGAPS TO CLOSE. Each is attached to a real role. Write it as fact:"
            if level == "aggressive"
            else "\nUNDER-STATED. The work implies these, so make them explicit:"
        )
        lines.append(header)
        for gap in view.gaps:
            label = gap.jd_phrase or gap.requirement
            lines.append(f'- [{gap.importance}] "{label}"')
            if gap.bridge_role:
                lines.append(f"    attach to: {gap.bridge_role}")
            if gap.bridge_claim:
                lines.append(f"    assert: {gap.bridge_claim}")
            if gap.nearest_real_experience:
                lines.append(f"    builds on: {gap.nearest_real_experience}")
            if gap.metric_hint:
                lines.append(f"    credible metric: {gap.metric_hint}")
            if gap.skill_tokens:
                lines.append(f"    keywords: {', '.join(gap.skill_tokens)}")

    if view.title_reframes:
        lines.append("\nTITLE REFRAMES. Same employer, same dates, same seniority:")
        for reframe in view.title_reframes:
            lines.append(
                f"- {reframe.company}: \"{reframe.original_role}\" -> "
                f"\"{reframe.suggested_role}\""
            )

    if view.do_not_claim:
        lines.append(
            "\nDO NOT CLAIM these. They cannot be supported and must not appear:"
        )
        lines += [f"- {item}" for item in view.do_not_claim]

    return "\n".join(lines)
