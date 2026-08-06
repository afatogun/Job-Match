export type WorkMode = 'any' | 'remote' | 'hybrid' | 'onsite'
export type Augmentation = 'accurate' | 'enhanced' | 'aggressive'
export type OpenAIModel = 'gpt-4.1-nano' | 'gpt-4.1-mini' | 'gpt-4.1' | 'gpt-5'

export const JOB_STATUSES = [
  'new',
  'saved',
  'generated',
  'applied',
  'interview',
  'rejected',
] as const

export type JobStatus = (typeof JOB_STATUSES)[number]

export const AUGMENTATION_LEVELS: { value: Augmentation; label: string; blurb: string }[] = [
  {
    value: 'accurate',
    label: 'Accurate',
    blurb: 'Only what your profile already says. Rewording and restructuring only.',
  },
  {
    value: 'enhanced',
    label: 'Enhanced',
    blurb: 'Rebuilds your CV around the vacancy and makes explicit the skills your real work implies. No invented systems, no new numbers, titles untouched.',
  },
  {
    value: 'aggressive',
    label: 'Aggressive',
    blurb: 'Closes every gap in the job ad. Names projects, systems and metrics under your real employers and reworks your job titles toward the role. It will state things you have not done. Check every amber bullet before you send it.',
  },
]

export interface SearchSettings {
  target_titles: string[]
  target_levels: string[]
  min_years_experience: number | null
  max_years_experience: number | null
  keywords: string[]
  excluded_keywords: string[]
  excluded_title_words: string[]
  location: string
  max_job_age_days: number
  work_mode: WorkMode
  results_per_title: number
  sources: string[]
  openai_model: OpenAIModel
  default_augmentation: Augmentation
  ai_rank_top_n: number
  min_score_to_rank: number
  enable_external_interview_data: boolean
}

export interface Job {
  id: number
  source: string
  source_job_id: string | null
  title: string
  company: string | null
  location: string | null
  is_remote: boolean | null
  job_url: string
  job_url_direct: string | null
  date_posted: string | null
  job_type: string | null
  salary_min: number | null
  salary_max: number | null
  salary_currency: string | null
  salary_interval: string | null
  description: string | null
  status: JobStatus
  relevance_score: number | null
  local_score: number | null
  ai_score: number | null
  ai_reason: string | null
  ai_matching_skills: string[]
  ai_missing_skills: string[]
  ai_seniority_fit: string | null
  ai_ranked_at: string | null
  matching_terms: string[]
  has_application: boolean
  first_seen_at: string
  last_seen_at: string
  profile_id: string | null
}

export interface JobListResponse {
  items: Job[]
  total: number
  limit: number
  offset: number
}

export interface Stats {
  total_jobs: number
  new_jobs: number
  good_matches: number
  generated_applications: number
  last_refresh_at: string | null
}

export interface RefreshError {
  source: string
  search_term: string
  error: string
}

export interface RefreshStatus {
  running: boolean
  run_id: string | null
  started_at: string | null
  finished_at: string | null
  current: string | null
  completed: number
  total: number
  found: number
  inserted: number
  updated: number
  filtered: number
  ranked: number
  errors: RefreshError[]
}

export interface SourceInfo {
  name: string
  label: string
  unreliable?: boolean
}

export interface JobFilterState {
  q: string
  source: string
  status: string
  profile_id: string
  posted_within_days: string
  min_score: string
  salary_min: string
  salary_max: string
  sort: 'newest' | 'best' | 'salary_high'
}

export const APPLICATION_STAGES = [
  'generated',
  'applied',
  'interview_stage_1',
  'offer',
  'rejected',
] as const

export type ApplicationStage = (typeof APPLICATION_STAGES)[number]

// ------------------------------------------------------------- profile

export interface ProfileMeta {
  id: string
  name: string
  is_active: boolean
  created_at: string
  source_filename: string | null
}

export interface PersonalInfo {
  full_name: string
  email: string
  phone: string
  location: string
  linkedin: string
  github: string
  website: string
}

export interface ExperienceItem {
  role: string
  company: string
  location: string
  start_date: string
  end_date: string
  summary: string
  achievements: string[]
  technologies: string[]
}

export interface ProjectItem {
  name: string
  description: string
  technologies: string[]
  link: string
}

export interface EducationItem {
  qualification: string
  institution: string
  year: string
  details: string
}

export interface Profile {
  personal: PersonalInfo
  professional_summary: string
  experience: ExperienceItem[]
  achievements: string[]
  projects: ProjectItem[]
  education: EducationItem[]
  skills: string[]
  additional_experience: string
  additional_projects: string
  additional_skills: string
  notes_for_ai: string
  source_filename: string
  updated_at: string
}

// -------------------------------------------------------- applications

export interface CVBullet {
  text: string
  inferred: boolean
}

export interface CVExperience {
  role: string
  company: string
  location: string
  dates: string
  bullets: CVBullet[]
}

export interface CVProject {
  name: string
  description: string
  technologies: string[]
}

export interface CVEducation {
  qualification: string
  institution: string
  year: string
}

export interface GeneratedCV {
  full_name: string
  headline: string
  contact: string[]
  summary: string
  skills: string[]
  experience: CVExperience[]
  projects: CVProject[]
  education: CVEducation[]
}

export interface Application {
  id: number
  job_id: number
  augmentation: Augmentation
  cv: GeneratedCV | null
  cover_letter_text: string | null
  flagged_additions: string[]
  style_notes: string[]
  monotonous: boolean
  folder: string | null
  has_cv_docx: boolean
  has_cv_pdf: boolean
  has_cover_letter_docx: boolean
  model: string | null
  profile_id: string | null
  stage: ApplicationStage
  stage_updated_at: string | null
  interview_prep: InterviewPrepData | null
  created_at: string
  updated_at: string
  job: Job | null
}

export interface InterviewQuestion {
  question: string
  why_relevant: string
  difficulty: 'easy' | 'medium' | 'hard'
}

export interface InterviewPrepReference {
  title: string
  url: string
  snippet: string
}

export interface InterviewPrepData {
  questions: InterviewQuestion[]
  tips: string
  focus_areas: string[]
  references: InterviewPrepReference[]
  source_note: string
  generated_at: string
  source: 'ai' | 'external' | 'hybrid'
}

export interface GenerationStatus {
  running: boolean
  current: string | null
  completed: number
  total: number
  generated: number
  errors: string[]
}
