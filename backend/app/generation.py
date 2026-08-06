"""Steps 14-16 - augmentation control, tailored CV, tailored cover letter.

Generation only ever happens when the user explicitly asks for it.
The model returns structured content; it never controls document formatting.
"""

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .ai import complete_structured, complete_text
from .humanize import clean_text, find_tells, reads_monotonous, vacancy_allowed_cliches
from .models import (
    Augmentation,
    GeneratedCV,
    InterviewPrepData,
    JobGapAnalysis,
    Profile,
)

log = logging.getLogger(__name__)

# The writing pass sees a trimmed description because it also receives the structured
# vacancy analysis; the analysis pass gets far more, because the requirements that
# differentiate a role live in the preferred-qualifications section at the very end.
DESCRIPTION_CHARS = 4000
ANALYSIS_DESCRIPTION_CHARS = 16000

# Enforced, not requested. See _clean_cv.
MAX_SKILLS = 24

# Step 14. The only thing that varies is how far the model may go beyond the profile.
#
# Every level uses the same six headings. That is deliberate: a rule can then never be
# silently absent, and the difference between levels reads as a diff on fixed axes rather
# than three differently-shaped paragraphs. No absolute prohibition lives anywhere outside
# these blocks - CV_CRAFT below is level-agnostic on purpose.
AUGMENTATION_POLICY: dict[str, str] = {
    "accurate": """Use only information present in the candidate profile. Reword, reorder,
re-emphasise and restructure to fit the vacancy, and use the job's vocabulary for things
the candidate demonstrably did.

WHAT YOU MAY DO. Rewrite any wording. Reorder roles, bullets and skills so the most
relevant material leads. Drop anything the vacancy has no use for.

WHAT YOU MAY NEVER DO. Add a skill, tool, responsibility or employer that is not in the
profile. Assert anything the profile does not already say.

METRICS. Only numbers already present in the profile, attached to the same work they
describe there.

JOB TITLES. Exactly as the profile states them.

PROJECTS AND EDUCATION. Copied from the profile. Descriptions may be reworded, nothing
may be added.

FLAGGING. Mark nothing as inferred, because nothing should be. Leave flagged_additions
empty.""",
    "enhanced": """Present this candidate as a strong, well-matched applicant for this
specific vacancy. Reshape the CV around what the role asks for.

WHAT YOU MAY DO. Reframe every role, bullet and project in the vacancy's own vocabulary.
Make explicit the skills and responsibilities the candidate's real work clearly implies
but never spelled out: someone who shipped a RAG chatbot did chunking, embedding and
retrieval evaluation, so say so. Reorder and reweight so the most relevant role leads and
the least relevant shrinks to a line. Add tools to the skills list where the described
work could not have happened without them.

WHAT YOU MAY NEVER DO. Name a system, product or initiative the profile does not mention.
Add an employer. Claim a responsibility the candidate's real work does not imply.

METRICS. Use only numbers already in the profile. Write qualitatively everywhere else.

JOB TITLES. Exactly as the profile states them.

PROJECTS AND EDUCATION. Re-describe existing projects toward the vacancy. Add nothing.
Education is copied verbatim.

FLAGGING. Set inferred=true on any bullet asserting something the profile does not state
outright, so the user can review it before export.""",
    "aggressive": """The candidate has authorised this level of extrapolation and reviews
every claim before sending. Write each claim as settled fact, in the past tense, with no
hedging language.

You are not summarising this candidate. You are building the CV that gets shortlisted for
this exact vacancy, using their real career as the raw material. Work from the VACANCY
ANALYSIS in the user message: every requirement marked must-have or strong-plus is to be
visibly answered somewhere in the CV, in the vacancy's own terminology, attached to a real
employer.

WHAT YOU MAY DO. Name initiatives, systems, services and workstreams under the candidate's
real employers and describe what they did on them. "Built the evaluation harness for the
retrieval pipeline, with golden datasets and LLM-as-judge scoring" is exactly the kind of
bullet to write when the vacancy asks for it and the employer plausibly needed it. Rewrite
job titles toward this vacancy at the same employer, the same dates and the same seniority.
Attach any tool, framework, cloud service or practice the vacancy names to specific work at
a specific employer rather than dropping it into the skills list alone. Replace weak
bullets outright: a bullet that does nothing for this vacancy should be rewritten into one
that does, not kept out of loyalty to the original CV. Replacing a bullet never means
removing a role. Every employer in the profile still appears.

WHAT YOU MAY NEVER DO. Add an employer or alter a company name. Change employment dates.
Raise the seniority a title implies. Add degrees, institutions, certifications or
graduation years. Add a Projects entry that is not in the profile. Claim anything outside
what that employer could credibly have done, because a construction-data company did not
run a trading desk.

METRICS. State the numbers this work would have produced: volumes, latencies, throughput,
cost reductions, coverage percentages, team sizes, user counts. Keep them in the range a
real engineer at this seniority would produce, and keep them consistent across the whole
document. Where the VACANCY ANALYSIS supplies a metric hint, stay inside its magnitude
band.

JOB TITLES. "Graduate Software Engineer" may become "Graduate Software Engineer, AI
Platform". It may not become "Senior Staff Engineer".

PROJECTS AND EDUCATION. Existing projects may be re-described freely and pointed straight
at the vacancy. Education is copied verbatim.

FLAGGING. Set inferred=true only on bullets asserting specifics that are not in the
profile: a system it does not mention, or a number that was never measured. Do not flag a
bullet that merely rewords real work, or the review panel fills with noise and stops being
read.""",
}

# The letter is written after the CV and must not contradict it. Kept separate from the CV
# policy because the failure mode is different: the risk is not timidity, it is two
# documents making different specific claims.
LETTER_POLICY: dict[str, str] = {
    "accurate": (
        "Use only what the candidate profile states. The CV you have been given is drawn "
        "from the same profile; do not go beyond either of them."
    ),
    "enhanced": (
        "The CV you have been given is the source of truth for this application. You may "
        "restate anything it claims. Do not introduce a claim or a number it does not make."
    ),
    "aggressive": (
        "The CV you have been given is the source of truth for this application. You may "
        "restate anything it claims, including its numbers, exactly as it states them. Do "
        "not introduce any claim or number the CV does not make, and never contradict it."
    ),
}

# Applied to both the CV and the cover letter. Rhythm matters more than vocabulary:
# banned-word lists are easy to satisfy while still sounding synthetic.
HUMAN_STYLE = """WRITE LIKE A PERSON, NOT A LANGUAGE MODEL

Punctuation and typography:
- Never use em dashes or en dashes. Use commas, full stops or brackets.
- Straight quotes and apostrophes only. No curly quotes, no ellipsis character.
- Do not chain clauses with semicolons. Start a new sentence.

Never use these words and phrases. They are the clearest machine tells:
delve, leverage, utilise, robust, seamless, seamlessly, spearheaded, orchestrated,
pivotal, crucial, testament, showcase, underscore, foster, facilitate, harness,
empower, elevate, unlock, realm, landscape, tapestry, myriad, plethora, meticulous,
holistic, cutting-edge, state-of-the-art, game-changer, transformative, synergy,
streamline, wealth of experience, proven track record, uniquely positioned, deep
dive, ever-evolving, at the intersection of, in today's fast-paced world, it is
worth noting, "not only ... but also", I am excited to, I am thrilled to, resonates
with me, I believe I would be a great fit, passionate, dynamic, team player,
detail-oriented, results-driven, hit the ground running.

Exception: if the vacancy itself names one of these as a real requirement (a job
asking for "robust distributed systems"), you may use it once where it genuinely
describes the candidate's work. The ban is on using them as filler.

Rhythm, which matters more than word choice:
- Vary sentence length hard. Follow a long sentence with a short one.
- Do not write everything in threes. Lists of exactly three items are the single
  most recognisable machine habit. Use two, or four, or one.
- Do not start consecutive sentences or bullets with the same grammatical shape.
- Avoid the participial opener ("Leveraging X, achieved Y"). Say what happened.
- Never end a paragraph with a sentence that restates the paragraph.

Tone:
- Concrete nouns and verbs. Name the actual technology, team, number or outcome.
- Prefer the plain word. Use, not utilise. Built, not architected. Cut, not reduced.
- A claim with no evidence attached reads as filler. Cut it rather than soften it.
"""

CV_ROLE = """You write tailored, ATS-friendly CVs for one candidate and one vacancy.

The AUGMENTATION POLICY below is the authority on how far you may go beyond the candidate
profile. Where anything later in this prompt appears to conflict with it, the policy wins.
"""

# Craft rules only. Everything that varies by augmentation level lives in the policy blocks
# above, so that nothing here can contradict them.
CV_CRAFT = """HOW TO WRITE IT

Optimise for:
- relevance to this specific vacancy, leading with what matters most to it
- ATS keyword coverage drawn from the job description, used naturally
- concise writing; no filler, no first person, no pronouns
- strong action verbs opening every bullet
- accomplishment-oriented bullets, not duty lists
- Google XYZ style ("Accomplished X, as measured by Y, by doing Z") wherever the
  augmentation policy allows you a number

Every role in the candidate profile appears in the CV, in the profile's order. A role the
vacancy has no use for shrinks to a single line. It is never deleted: a CV with a hole in
its employment history is rejected on sight, whatever else it says.

Section by section:
- headline: 3 to 8 words in the vacancy's own title vocabulary. Not a sentence, not a
  self-description, no adjectives about the candidate.
- summary: 2 to 3 sentences. Name the target role's domain in the first clause.
- skills: ordered by this vacancy's priority, must-haves first, using the job ad's exact
  spelling of each. 12 to 24 items. Drop profile skills the vacancy has no use for; a
  front-end framework the ad never mentions is costing you a line.
- experience: 4 to 6 bullets on the most relevant role, 3 to 4 on the next, 1 to 2 on the
  least relevant. Lead every role with its most vacancy-relevant bullet.
- projects: keep the profile's projects when they demonstrate something this vacancy asks
  for, re-described to point at it. Drop one only when it is genuinely irrelevant to the
  role. Never add a project that is not in the profile. Real shipped work is evidence, so
  do not discard it to save space.
- education: qualification, institution and year, copied from the profile.

Length budget: 18 bullets across all roles at the very most, 24 skills, and a document
that lands on two pages.
"""

COVER_LETTER_SYSTEM = """You write cover letters that a hiring manager would actually finish.

Rules:
- 250-350 words, 3-4 paragraphs, no postal addresses or letterhead
- greeting: name the team or company if the vacancy gives you one ("Dear Marsh
  Innovation team,"). "Dear Hiring Team," is acceptable. Never "To Whom It May
  Concern" and never "Dear Sir/Madam"
- the first sentence must say something only someone who read THIS posting could
  write. Never open with "I am writing to apply" or a statement of enthusiasm
- middle paragraphs give concrete evidence from the candidate's real work, chosen
  because it answers what this vacancy actually asks for
- do not restate the CV as prose. Pick two things and go deeper on them
- naming one thing the candidate has not done reads as honest and almost nothing else
  does, but only pick something the CV has not already claimed. If you are given a
  "cannot credibly claim" list, take it from there. If you are not, skip this entirely
  rather than undercutting the CV
- plain confident tone, active voice, British/Irish spelling
- close in one line. No "at your earliest convenience", no "thank you for your time
  and consideration"
- output the letter body only, starting with the greeting
"""


INTERVIEW_PREP_SYSTEM = """You generate interview preparation tailored to one vacancy and one candidate profile.

Rules:
- Produce 5 to 7 realistic interview questions for this role and level.
- Each question must include a short "why relevant" note tied to concrete evidence in the job description.
- Mix technical and behavioural questions where appropriate.
- Do not invent candidate experience. Questions can probe gaps, but never claim the candidate has done something.
- Keep wording concise and practical.
"""


class GeneratedCVWithFlags(BaseModel):
    cv: GeneratedCV
    flagged_additions: list[str] = Field(
        default_factory=list,
        description="Plain-language list of anything inferred beyond the profile.",
    )


def _profile_text(profile: Profile) -> str:
    parts = [
        f"Name: {profile.personal.full_name}",
        f"Contact: {profile.personal.email} | {profile.personal.phone} | "
        f"{profile.personal.location}",
        f"Links: {profile.personal.linkedin} {profile.personal.github} {profile.personal.website}".strip(),
        f"\nProfessional summary:\n{profile.professional_summary}",
        f"\nSkills: {', '.join(profile.skills)}",
    ]

    parts.append("\nExperience:")
    for exp in profile.experience:
        parts.append(
            f"- {exp.role} at {exp.company}, {exp.location} "
            f"({exp.start_date} - {exp.end_date})\n  {exp.summary}"
        )
        for a in exp.achievements:
            parts.append(f"    * {a}")
        if exp.technologies:
            parts.append(f"    tech: {', '.join(exp.technologies)}")

    if profile.achievements:
        parts.append("\nAchievements:")
        parts += [f"- {a}" for a in profile.achievements]

    if profile.projects:
        parts.append("\nProjects:")
        for p in profile.projects:
            parts.append(f"- {p.name}: {p.description} ({', '.join(p.technologies)})")

    if profile.education:
        parts.append("\nEducation:")
        for e in profile.education:
            parts.append(f"- {e.qualification}, {e.institution} ({e.year}) {e.details}")

    for label, value in (
        ("Additional experience", profile.additional_experience),
        ("Additional projects", profile.additional_projects),
        ("Additional skills", profile.additional_skills),
        ("Notes about the candidate", profile.notes_for_ai),
    ):
        if value.strip():
            parts.append(f"\n{label}:\n{value}")

    return "\n".join(parts)


def _truncate_middle(text: str, max_chars: int) -> str:
    """Keep the head and the tail, drop the middle.

    Job ads put the requirements that actually differentiate a role - preferred
    qualifications, tooling, governance expectations - at the very end, after the
    boilerplate. Cutting from the tail removes exactly the part worth reading.
    """
    if len(text) <= max_chars:
        return text
    marker = "\n\n[...]\n\n"
    budget = max_chars - len(marker)
    head = int(budget * 0.6)
    return text[:head] + marker + text[-(budget - head):]


def _job_text(job: dict, max_chars: int = DESCRIPTION_CHARS) -> str:
    description = job.get("description") or "(no description available)"
    return (
        f"Job title: {job.get('title')}\n"
        f"Company: {job.get('company') or 'Unknown'}\n"
        f"Location: {job.get('location') or 'Unknown'}\n"
        f"Description:\n{_truncate_middle(description, max_chars)}"
    )


def _cv_system(augmentation: Augmentation) -> str:
    """Policy first, so it frames everything; recalled last, so recency does not bury it.

    The old assembly put CV_SYSTEM's absolute prohibitions ahead of the policy meant to
    override them, with the whole of HUMAN_STYLE in between. A prohibition stated first
    and contradicted sixty lines later wins, which is why aggressive read as timid.
    """
    return "\n\n".join(
        [
            CV_ROLE,
            f"AUGMENTATION POLICY: {augmentation.upper()}\n"
            f"This section overrides every other instruction in this prompt.\n\n"
            f"{AUGMENTATION_POLICY[augmentation]}",
            CV_CRAFT,
            HUMAN_STYLE,
            f"Reminder: you are writing in {augmentation.upper()} mode. Re-read the "
            f"augmentation policy above before you answer.",
        ]
    )


def _clean_cv(cv: GeneratedCV) -> GeneratedCV:
    """Enforce the typography rather than requesting it.

    A model will not obey "never use an em dash" across a whole document, and this is
    cheap and idempotent, so it runs after every pass that can touch the text.
    """
    cv.headline = clean_text(cv.headline)
    cv.summary = clean_text(cv.summary)
    # Skills come back ordered by vacancy relevance, so the tail is the least relevant.
    # Enforcing the budget here rather than asking for it stops the list running to
    # thirty-odd entries, where the keyword stuffing at the end dilutes the real matches.
    cv.skills = [clean_text(s) for s in cv.skills if s.strip()][:MAX_SKILLS]
    for exp in cv.experience:
        exp.role = clean_text(exp.role)
        exp.company = clean_text(exp.company)
        exp.location = clean_text(exp.location)
        exp.dates = clean_text(exp.dates)
        for bullet in exp.bullets:
            bullet.text = clean_text(bullet.text)
    for proj in cv.projects:
        proj.name = clean_text(proj.name)
        proj.description = clean_text(proj.description)
        proj.technologies = [clean_text(t) for t in proj.technologies if t.strip()]
    for edu in cv.education:
        edu.qualification = clean_text(edu.qualification)
        edu.institution = clean_text(edu.institution)
    return cv


def generate_cv(
    profile: Profile,
    job: dict,
    augmentation: Augmentation,
    model: str,
    analysis: JobGapAnalysis | None = None,
) -> GeneratedCVWithFlags:
    # Vacancy first, profile last. Leading with the profile anchors the model on
    # reproducing it, which is the single behaviour this whole change is fighting.
    # Imported here rather than at module scope: gap_analysis reuses this module's prompt
    # payload builders, so a top-level import either way would be circular.
    from .gap_analysis import render_for_prompt

    sections = [f"TARGET VACANCY\n{_job_text(job)}"]
    if analysis is not None:
        sections.append(f"VACANCY ANALYSIS\n{render_for_prompt(analysis, augmentation)}")
    sections.append(
        "CANDIDATE PROFILE (raw material for the CV, not a document to reproduce)\n"
        f"{_profile_text(profile)}"
    )
    instruction = (
        "Write the tailored CV content. List in flagged_additions anything you asserted "
        "that the profile does not state."
    )
    if analysis is not None and augmentation == "aggressive":
        instruction = (
            "Write the tailored CV content. Before you answer, check that every must-have "
            "and strong-plus requirement in the vacancy analysis is visibly answered "
            "somewhere in the CV. List in flagged_additions anything you asserted that "
            "the profile does not state."
        )
    sections.append(instruction)

    result = complete_structured(
        model=model,
        system=_cv_system(augmentation),
        user="\n\n".join(sections),
        schema_model=GeneratedCVWithFlags,
        max_tokens=8000,
    )

    # Contact details are facts, not model output - take them from the profile.
    cv = result.cv
    p = profile.personal
    cv.full_name = p.full_name or cv.full_name
    cv.contact = [v for v in (p.email, p.phone, p.location, p.linkedin, p.github, p.website) if v]

    allow = vacancy_allowed_cliches(job.get("description") or "")
    result.cv = _clean_cv(cv)
    result.cv = _clean_cv(revise_cv_for_style(result.cv, model, allow=allow))
    result.flagged_additions = [clean_text(f) for f in result.flagged_additions]
    return result


REVISION_SYSTEM = """You are editing a cover letter that is almost finished.

Fix ONLY the problems listed. Keep every fact, every number, every example and the
overall structure exactly as they are. Do not add new claims. Do not reorder
paragraphs. Change the wording that is flagged and nothing else.

Return the revised letter only, starting with the greeting.
"""


def _clean_blocks(text: str) -> str:
    return "\n\n".join(
        clean_text(block) for block in (text or "").replace("\r\n", "\n").split("\n\n") if block.strip()
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def generate_interview_prep(profile: Profile, job: dict, model: str) -> InterviewPrepData:
    prep = complete_structured(
        model=model,
        system=INTERVIEW_PREP_SYSTEM,
        user=(
            f"CANDIDATE PROFILE\n{_profile_text(profile)}\n\n"
            f"TARGET VACANCY\n{_job_text(job)}\n\n"
            "Return interview prep content with focused, role-specific questions."
        ),
        schema_model=InterviewPrepData,
        max_tokens=2500,
    )

    prep.questions = [
        q.model_copy(
            update={
                "question": clean_text(q.question),
                "why_relevant": clean_text(q.why_relevant),
            }
        )
        for q in prep.questions
        if q.question.strip()
    ]
    prep.tips = clean_text(prep.tips)
    prep.focus_areas = [clean_text(item) for item in prep.focus_areas if item.strip()]
    prep.generated_at = prep.generated_at or _now()
    prep.source = "ai"
    return prep


CV_REVISION_SYSTEM = """You are fixing the wording of finished CV lines.

You are given lines from a CV, each of which contains a word or phrase that reads as
AI-written. Rewrite each line so it says exactly the same thing in plain wording.

Keep every fact, every number, every technology name and every claim. Do not soften a
claim, do not hedge it, do not add a qualifier. Do not merge or split lines. Change only
the wording that reads as machine-written.

Return one replacement per line you were given, with the original text copied back
exactly as it was supplied so it can be matched.
"""


class StyleReplacement(BaseModel):
    original: str
    revised: str


class StyleReplacements(BaseModel):
    replacements: list[StyleReplacement] = Field(default_factory=list)


def _cv_style_strings(cv: GeneratedCV) -> list[str]:
    """Every free-text string in a CV that a reader would judge for style.

    Mirrors what applications.py concatenates for the writing-check panel, so the panel
    and the repair pass agree on what counts.
    """
    strings = [cv.headline, cv.summary]
    strings += [b.text for e in cv.experience for b in e.bullets]
    strings += [p.description for p in cv.projects]
    return [s for s in strings if s and s.strip()]


def revise_cv_for_style(
    cv: GeneratedCV, model: str, allow: set[str] | None = None
) -> GeneratedCV:
    """Repair machine-writing tells in CV text without risking the structure.

    The cover letter can be round-tripped as a single string; a CV cannot, because a
    model that drops a section silently corrupts the document. So only the offending
    leaf strings are sent, and replacements are applied by exact match. Anything that
    comes back empty, unmatched, or still carrying a tell is discarded and the original
    kept.

    Whole strings are rewritten rather than individual phrases: swapping "proven track
    record" out of a sentence on its own leaves "Track record designing and deploying".
    """
    offenders = [s for s in _cv_style_strings(cv) if find_tells(s, allow=allow)]
    if not offenders:
        return cv

    try:
        result = complete_structured(
            model=model,
            system=CV_REVISION_SYSTEM,
            user="LINES TO FIX\n" + "\n".join(f"- {s}" for s in offenders),
            schema_model=StyleReplacements,
            max_tokens=2000,
        )
    except Exception as exc:  # noqa: BLE001 - style repair must never fail generation
        log.warning("CV style repair failed, keeping original wording: %s", exc)
        return cv

    originals = set(offenders)
    mapping: dict[str, str] = {}
    for item in result.replacements:
        revised = clean_text(item.revised)
        if item.original not in originals or not revised:
            continue
        # A "fix" that reintroduces a tell is not a fix.
        if find_tells(revised, allow=allow):
            continue
        mapping[item.original] = revised

    if not mapping:
        return cv

    cv.headline = mapping.get(cv.headline, cv.headline)
    cv.summary = mapping.get(cv.summary, cv.summary)
    for exp in cv.experience:
        for bullet in exp.bullets:
            bullet.text = mapping.get(bullet.text, bullet.text)
    for proj in cv.projects:
        proj.description = mapping.get(proj.description, proj.description)
    return cv


def revise_for_style(letter: str, model: str, allow: set[str] | None = None) -> str:
    """One targeted pass when detection finds machine tells.

    A single system prompt does not reliably suppress this vocabulary, but the
    detection is deterministic, so we can name the exact problems and fix them.
    Costs one extra call, and only when something was actually found.
    """
    tells = find_tells(letter, allow=allow)
    monotonous = reads_monotonous(letter)
    if not tells and not monotonous:
        return letter

    problems = []
    if tells:
        problems.append(
            "These words and phrases read as AI-written. Replace each with plain "
            f"wording that keeps the meaning: {', '.join(tells)}."
        )
    if monotonous:
        problems.append(
            "Every sentence is a similar length, which is the strongest tell of all. "
            "Rewrite so the lengths vary sharply: include at least two sentences under "
            "eight words, and do not let three consecutive sentences be similar in length."
        )

    revised = complete_text(
        model=model,
        system=REVISION_SYSTEM,
        user=f"PROBLEMS TO FIX\n" + "\n".join(f"- {p}" for p in problems) + f"\n\nLETTER\n{letter}",
        max_tokens=1500,
    )
    revised = _clean_blocks(revised)

    # Only accept the revision if it genuinely improved things - a rewrite that
    # introduces new cliches or loses the letter is worse than the original.
    if not revised or len(revised) < len(letter) * 0.5:
        return letter
    if len(find_tells(revised, allow=allow)) > len(tells):
        return letter
    return revised


def generate_cover_letter(
    profile: Profile,
    job: dict,
    cv: GeneratedCV,
    augmentation: Augmentation,
    model: str,
    analysis: JobGapAnalysis | None = None,
) -> str:
    # Every bullet of the top three roles, not the first three of each. Under aggressive
    # the gap-closing content is often bullet four or five, and a letter that has not
    # seen it will contradict the CV it is supposed to support.
    cv_summary = (
        f"Summary: {cv.summary}\nSkills: {', '.join(cv.skills)}\n"
        + "\n".join(
            f"{e.role} at {e.company}: " + "; ".join(b.text for b in e.bullets)
            for e in cv.experience[:3]
        )
    )

    sections = [
        f"TARGET VACANCY\n{_job_text(job)}",
        f"TAILORED CV JUST WRITTEN FOR THIS ROLE\n{cv_summary}",
    ]
    if analysis is not None and analysis.do_not_claim:
        sections.append(
            "CANNOT CREDIBLY CLAIM (safe to name one of these as a gap)\n"
            + "\n".join(f"- {item}" for item in analysis.do_not_claim)
        )
    sections.append(f"CANDIDATE PROFILE (background)\n{_profile_text(profile)}")
    sections.append("Write the cover letter.")

    letter = complete_text(
        model=model,
        system=(
            f"{COVER_LETTER_SYSTEM}\n\n{HUMAN_STYLE}\n\n"
            f"CONSISTENCY POLICY\n{LETTER_POLICY[augmentation]}"
        ),
        user="\n\n".join(sections),
        max_tokens=1500,
    )
    # Clean per paragraph so blank-line structure survives, then fix any tells
    # the style rules failed to prevent.
    allow = vacancy_allowed_cliches(job.get("description") or "")
    return revise_for_style(_clean_blocks(letter), model, allow=allow)
