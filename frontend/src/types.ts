export type WorkMode = 'any' | 'remote' | 'hybrid' | 'onsite'
export type Augmentation = 'accurate' | 'enhanced' | 'aggressive'

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
    blurb: 'Strengthens your real experience and makes implied skills explicit.',
  },
  {
    value: 'aggressive',
    label: 'Aggressive',
    blurb: 'Reasonable inference to present you as strongly as the evidence allows.',
  },
]

export interface SearchSettings {
  target_titles: string[]
  keywords: string[]
  excluded_keywords: string[]
  excluded_title_words: string[]
  location: string
  max_job_age_days: number
  work_mode: WorkMode
  results_per_title: number
  sources: string[]
  openai_model: string
  default_augmentation: Augmentation
  ai_rank_top_n: number
  min_score_to_rank: number
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
  posted_within_days: string
  min_score: string
  sort: 'newest' | 'best'
}

// ------------------------------------------------------------- profile

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
  created_at: string
  updated_at: string
  job: Job | null
}

export interface GenerationStatus {
  running: boolean
  current: string | null
  completed: number
  total: number
  generated: number
  errors: string[]
}
