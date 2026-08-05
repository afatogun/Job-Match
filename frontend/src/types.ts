export type WorkMode = 'any' | 'remote' | 'hybrid' | 'onsite'

export const JOB_STATUSES = [
  'new',
  'saved',
  'generated',
  'applied',
  'interview',
  'rejected',
] as const

export type JobStatus = (typeof JOB_STATUSES)[number]

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
  errors: RefreshError[]
}

export interface SourceInfo {
  name: string
  label: string
}

export interface JobFilterState {
  q: string
  source: string
  status: string
  posted_within_days: string
  sort: 'newest' | 'best'
}
