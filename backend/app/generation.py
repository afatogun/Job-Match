"""Steps 14-16 - augmentation control, tailored CV, tailored cover letter.

Generation only ever happens when the user explicitly asks for it.
The model returns structured content; it never controls document formatting.
"""

import logging

from pydantic import BaseModel, Field

from .ai import complete_structured, complete_text
from .humanize import clean_text, find_tells, reads_monotonous
from .models import Augmentation, GeneratedCV, Profile

log = logging.getLogger(__name__)

DESCRIPTION_CHARS = 6000

# Step 14. The only thing that varies is how far the model may go beyond the profile.
AUGMENTATION_RULES: dict[str, str] = {
    "accurate": (
        "STRICT MODE. Use only information present in the candidate profile. "
        "You may reword, reorder, re-emphasise and restructure to fit the vacancy, "
        "and you may use the job's vocabulary for things the candidate demonstrably did. "
        "Do NOT add skills, tools, responsibilities, employers or metrics that are not "
        "in the profile. Mark nothing as inferred, because nothing should be."
    ),
    "enhanced": (
        "ENHANCED MODE. Present the candidate's real experience at its strongest. "
        "You may make explicit those skills that their described work clearly required "
        "even if unnamed (e.g. someone who shipped a FastAPI service evidently used REST "
        "API design). You may not invent employers, job titles, dates or numeric metrics. "
        "Set inferred=true on any bullet that states something the profile only implies."
    ),
    "aggressive": (
        "AGGRESSIVE MODE. Make the candidate look as strong as the evidence can "
        "reasonably support. You may infer adjacent skills and responsibilities that "
        "someone in their roles would very likely have had, and frame their experience "
        "toward this vacancy. You still may NOT invent employers, job titles, dates, or "
        "fabricate numeric metrics. Set inferred=true on every bullet containing anything "
        "not directly stated in the profile, so the user can review it before export."
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

CV_SYSTEM = """You write tailored, ATS-friendly CVs.

Optimise for:
- relevance to this specific vacancy, leading with what matters most to it
- ATS keyword coverage drawn from the job description, used naturally
- concise writing; no filler, no first person, no pronouns
- strong action verbs opening every bullet
- accomplishment-oriented bullets, not duty lists
- Google XYZ style ("Accomplished X, as measured by Y, by doing Z") WHERE REAL
  METRICS ALREADY EXIST in the profile

Never invent numbers. If the profile has no metric for something, write a strong
qualitative bullet instead. A fabricated metric is worse than no metric.

Return 3-6 bullets for recent, relevant roles and 1-3 for older or less relevant ones.
The summary is 2-3 sentences. Skills are the vacancy-relevant ones the candidate has.
Set inferred=true on any bullet that goes beyond what the profile states outright.
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
- it is fine to name one thing the candidate has not done, if the letter shows the
  nearest real equivalent. That reads as honest and almost nothing else does
- plain confident tone, active voice, British/Irish spelling
- close in one line. No "at your earliest convenience", no "thank you for your time
  and consideration"
- output the letter body only, starting with the greeting
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


def _job_text(job: dict) -> str:
    return (
        f"Job title: {job.get('title')}\n"
        f"Company: {job.get('company') or 'Unknown'}\n"
        f"Location: {job.get('location') or 'Unknown'}\n"
        f"Description:\n{(job.get('description') or '(no description available)')[:DESCRIPTION_CHARS]}"
    )


def generate_cv(
    profile: Profile, job: dict, augmentation: Augmentation, model: str
) -> GeneratedCVWithFlags:
    rules = AUGMENTATION_RULES[augmentation]
    result = complete_structured(
        model=model,
        system=f"{CV_SYSTEM}\n\n{HUMAN_STYLE}\n\nAUGMENTATION POLICY\n{rules}",
        user=(
            f"CANDIDATE PROFILE\n{_profile_text(profile)}\n\n"
            f"TARGET VACANCY\n{_job_text(job)}\n\n"
            "Write the tailored CV content. List in flagged_additions anything you "
            "inferred rather than took directly from the profile."
        ),
        schema_model=GeneratedCVWithFlags,
        max_tokens=8000,
    )

    # Contact details are facts, not model output - take them from the profile.
    cv = result.cv
    p = profile.personal
    cv.full_name = p.full_name or cv.full_name
    cv.contact = [v for v in (p.email, p.phone, p.location, p.linkedin, p.github, p.website) if v]

    # The model will not obey "no em dashes" perfectly across a whole document,
    # so the typography is enforced rather than requested.
    cv.headline = clean_text(cv.headline)
    cv.summary = clean_text(cv.summary)
    cv.skills = [clean_text(s) for s in cv.skills if s.strip()]
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


def revise_for_style(letter: str, model: str) -> str:
    """One targeted pass when detection finds machine tells.

    A single system prompt does not reliably suppress this vocabulary, but the
    detection is deterministic, so we can name the exact problems and fix them.
    Costs one extra call, and only when something was actually found.
    """
    tells = find_tells(letter)
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
    if len(find_tells(revised)) > len(tells):
        return letter
    return revised


def generate_cover_letter(
    profile: Profile, job: dict, cv: GeneratedCV, augmentation: Augmentation, model: str
) -> str:
    rules = AUGMENTATION_RULES[augmentation]
    cv_summary = (
        f"Summary: {cv.summary}\nSkills: {', '.join(cv.skills[:15])}\n"
        + "\n".join(
            f"{e.role} at {e.company}: " + "; ".join(b.text for b in e.bullets[:3])
            for e in cv.experience[:3]
        )
    )
    letter = complete_text(
        model=model,
        system=f"{COVER_LETTER_SYSTEM}\n\n{HUMAN_STYLE}\n\nAUGMENTATION POLICY\n{rules}",
        user=(
            f"CANDIDATE PROFILE\n{_profile_text(profile)}\n\n"
            f"TAILORED CV JUST WRITTEN FOR THIS ROLE\n{cv_summary}\n\n"
            f"TARGET VACANCY\n{_job_text(job)}\n\n"
            "Write the cover letter."
        ),
        max_tokens=1500,
    )
    # Clean per paragraph so blank-line structure survives, then fix any tells
    # the style rules failed to prevent.
    return revise_for_style(_clean_blocks(letter), model)
