"""Pydantic models for the API surface."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

WorkMode = Literal["any", "remote", "hybrid", "onsite"]
JobStatus = Literal["new", "saved", "generated", "applied", "interview", "rejected"]
Augmentation = Literal["accurate", "enhanced", "aggressive"]
ApplicationStage = Literal[
    "generated",
    "applied",
    "interview_stage_1",
    "offer",
    "rejected",
]

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

# Curated model options for non-technical users.
OPENAI_MODELS: tuple[str, ...] = ("gpt-4.1-nano", "gpt-4.1-mini", "gpt-4.1", "gpt-5")
# Balanced default for cost and output quality.
DEFAULT_MODEL = "gpt-4.1-mini"


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
    target_levels: list[str] = Field(default_factory=list)
    min_years_experience: int | None = Field(default=None, ge=0, le=30)
    max_years_experience: int | None = Field(default=None, ge=0, le=40)
    keywords: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    excluded_title_words: list[str] = Field(default_factory=list)
    location: str = "Ireland"
    country: str = "auto"
    max_job_age_days: int = Field(default=7, ge=1, le=90)
    work_mode: WorkMode = "any"
    results_per_title: int = Field(default=40, ge=5, le=200)
    # Indeed is the only jobspy source reliably serving Ireland right now;
    # Glassdoor currently answers 400 and LinkedIn rate-limits without proxies.
    sources: list[str] = Field(default_factory=lambda: ["indeed"])

    # AI
    openai_model: str = DEFAULT_MODEL
    default_augmentation: Augmentation = "enhanced"
    ai_rank_top_n: int = Field(default=25, ge=0, le=200)
    min_score_to_rank: float = Field(default=40.0, ge=0, le=100)
    enable_external_interview_data: bool = False

    @field_validator(
        "target_titles",
        "target_levels",
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

    @field_validator("country")
    @classmethod
    def _strip_country(cls, v: str) -> str:
        return (v or "").strip().lower() or "auto"

    @field_validator("openai_model")
    @classmethod
    def _strip_model(cls, v: str) -> str:
        model = (v or "").strip()
        if model in OPENAI_MODELS:
            return model
        return DEFAULT_MODEL

    @model_validator(mode="after")
    def _validate_years_range(self):
        if (
            self.min_years_experience is not None
            and self.max_years_experience is not None
            and self.min_years_experience > self.max_years_experience
        ):
            raise ValueError("min_years_experience cannot be greater than max_years_experience")
        return self


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
    local_score: float | None = None
    ai_score: float | None = None
    ai_reason: str | None = None
    ai_matching_skills: list[str] = Field(default_factory=list)
    ai_missing_skills: list[str] = Field(default_factory=list)
    ai_seniority_fit: str | None = None
    ai_ranked_at: str | None = None
    matching_terms: list[str] = Field(default_factory=list)
    has_application: bool = False
    first_seen_at: str
    last_seen_at: str
    profile_id: str | None = None


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
    ranked: int = 0
    errors: list[RefreshError] = Field(default_factory=list)


# ---------------------------------------------------------------- profile


class ExperienceItem(BaseModel):
    role: str = ""
    company: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    summary: str = ""
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    link: str = ""


class EducationItem(BaseModel):
    qualification: str = ""
    institution: str = ""
    year: str = ""
    details: str = ""


class PersonalInfo(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""


class Profile(BaseModel):
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    professional_summary: str = ""
    experience: list[ExperienceItem] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)

    # Free-text extras the user maintains by hand.
    additional_experience: str = ""
    additional_projects: str = ""
    additional_skills: str = ""
    notes_for_ai: str = ""

    source_filename: str = ""
    updated_at: str = ""


class ProfileMeta(BaseModel):
    id: str
    name: str
    is_active: bool
    created_at: str
    source_filename: str | None = None


class CreateProfileRequest(BaseModel):
    name: str


class RenameProfileRequest(BaseModel):
    name: str


# ------------------------------------------------------- generated documents


class CVBullet(BaseModel):
    text: str
    inferred: bool = False


class CVExperience(BaseModel):
    role: str = ""
    company: str = ""
    location: str = ""
    dates: str = ""
    bullets: list[CVBullet] = Field(default_factory=list)


class CVProject(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class CVEducation(BaseModel):
    qualification: str = ""
    institution: str = ""
    year: str = ""


class GeneratedCV(BaseModel):
    """Structured CV content. The model never controls document formatting."""

    full_name: str = ""
    headline: str = ""
    contact: list[str] = Field(default_factory=list)
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[CVExperience] = Field(default_factory=list)
    projects: list[CVProject] = Field(default_factory=list)
    education: list[CVEducation] = Field(default_factory=list)


# ---------------------------------------------------------------- gap analysis
#
# Produced by a first pass over the vacancy, before any CV is written. The point is to
# turn decisions into lookups: a writing call that has to work out what the role wants,
# diff it against the profile, choose what to bridge and then write it will fall back to
# restating the profile. Given this, it only has to write.

Importance = Literal["must_have", "strong_plus", "nice_to_have"]


class RequirementEvidence(BaseModel):
    """A vacancy requirement the profile already answers."""

    requirement: str = ""
    jd_phrase: str = ""  # the vacancy's own wording, verbatim, for ATS purposes
    importance: Importance = "strong_plus"
    profile_evidence: str = ""  # the specific profile line that proves it
    evidence_role: str = ""  # "Role at Company"
    strength: Literal["direct", "adjacent"] = "direct"


class RequirementGap(BaseModel):
    """A vacancy requirement the profile does not answer, and how to close it."""

    requirement: str = ""
    jd_phrase: str = ""
    importance: Importance = "strong_plus"
    nearest_real_experience: str = ""  # closest true thing, for interview survival
    bridge_role: str = ""  # "Role at Company" - must be a real role from the profile
    bridge_claim: str = ""  # one bullet-shaped assertion, written as settled fact
    bridge_credibility: Literal["natural", "stretch", "implausible"] = "stretch"
    metric_hint: str = ""  # what kind of number is credible, with a magnitude band
    skill_tokens: list[str] = Field(default_factory=list)


class TitleReframe(BaseModel):
    company: str = ""
    original_role: str = ""
    suggested_role: str = ""
    justification: str = ""


class JobGapAnalysis(BaseModel):
    """Field order matters. Structured output is generated in declaration order, so if a
    response is cut short the later fields are the ones lost. `gaps` is the whole point
    of this pass, so it is emitted before the evidence summary, not after it."""

    role_archetype: str = ""
    seniority: Literal["junior", "mid", "senior", "staff", "lead", "unknown"] = "unknown"
    positioning_statement: str = ""
    headline_suggestion: str = ""
    ats_keywords: list[str] = Field(default_factory=list)
    gaps: list[RequirementGap] = Field(default_factory=list)
    covered: list[RequirementEvidence] = Field(default_factory=list)
    title_reframes: list[TitleReframe] = Field(default_factory=list)
    do_not_claim: list[str] = Field(default_factory=list)
    generated_at: str = ""


class InterviewQuestion(BaseModel):
    question: str
    why_relevant: str = ""
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class InterviewPrepReference(BaseModel):
    title: str
    url: str
    snippet: str = ""


class InterviewPrepData(BaseModel):
    questions: list[InterviewQuestion] = Field(default_factory=list)
    tips: str = ""
    focus_areas: list[str] = Field(default_factory=list)
    references: list[InterviewPrepReference] = Field(default_factory=list)
    source_note: str = ""
    generated_at: str = ""
    source: Literal["ai", "external", "hybrid"] = "ai"


class Application(BaseModel):
    id: int
    job_id: int
    augmentation: str
    cv: GeneratedCV | None = None
    cover_letter_text: str | None = None
    flagged_additions: list[str] = Field(default_factory=list)
    # Machine-writing tells that survived generation, computed on read.
    style_notes: list[str] = Field(default_factory=list)
    monotonous: bool = False
    folder: str | None = None
    has_cv_docx: bool = False
    has_cv_pdf: bool = False
    has_cover_letter_docx: bool = False
    model: str | None = None
    profile_id: str | None = None
    stage: ApplicationStage = "generated"
    stage_updated_at: str | None = None
    interview_prep: InterviewPrepData | None = None
    created_at: str
    updated_at: str
    job: Job | None = None


APPLICATION_STAGES: tuple[ApplicationStage, ...] = (
    "generated",
    "applied",
    "interview_stage_1",
    "offer",
    "rejected",
)


class ApplicationStageUpdate(BaseModel):
    stage: ApplicationStage


class GenerateRequest(BaseModel):
    augmentation: Augmentation | None = None


class BulkGenerateRequest(BaseModel):
    job_ids: list[int]
    augmentation: Augmentation | None = None


class GenerationStatus(BaseModel):
    running: bool = False
    current: str | None = None
    completed: int = 0
    total: int = 0
    generated: int = 0
    errors: list[str] = Field(default_factory=list)


class CVUpdate(BaseModel):
    cv: GeneratedCV


class CoverLetterUpdate(BaseModel):
    cover_letter_text: str
