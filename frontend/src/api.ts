import type {
  Application,
  Augmentation,
  GeneratedCV,
  GenerationStatus,
  Job,
  JobFilterState,
  JobListResponse,
  JobStatus,
  Profile,
  RefreshStatus,
  SearchSettings,
  SourceInfo,
  Stats,
} from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData
  const res = await fetch(path, {
    ...init,
    headers: {
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* response had no JSON body */
    }
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  getSettings: () => request<SearchSettings>('/api/settings'),

  saveSettings: (settings: SearchSettings) =>
    request<SearchSettings>('/api/settings', { method: 'PUT', body: JSON.stringify(settings) }),

  getSources: () => request<SourceInfo[]>('/api/settings/sources'),

  getOpenAIKey: () => request<{ configured: boolean; masked: string }>('/api/settings/openai'),

  saveOpenAIKey: (apiKey: string) =>
    request<{ configured: boolean; masked: string }>('/api/settings/openai', {
      method: 'PUT',
      body: JSON.stringify({ api_key: apiKey }),
    }),

  getStats: () => request<Stats>('/api/stats'),

  getJobs: (filters: Partial<JobFilterState>, limit = 50, offset = 0) => {
    const params = new URLSearchParams()
    if (filters.q) params.set('q', filters.q)
    if (filters.source) params.set('source', filters.source)
    if (filters.status) params.set('status', filters.status)
    if (filters.posted_within_days) params.set('posted_within_days', filters.posted_within_days)
    if (filters.min_score) params.set('min_score', filters.min_score)
    if (filters.sort) params.set('sort', filters.sort)
    params.set('limit', String(limit))
    params.set('offset', String(offset))
    return request<JobListResponse>(`/api/jobs?${params.toString()}`)
  },

  getJob: (id: number) => request<Job>(`/api/jobs/${id}`),

  setJobStatus: (id: number, status: JobStatus) =>
    request<Job>(`/api/jobs/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }),

  startRefresh: () => request<RefreshStatus>('/api/jobs/refresh', { method: 'POST' }),

  getRefreshStatus: () => request<RefreshStatus>('/api/jobs/refresh/status'),

  rerank: (jobId: number) => request<{ ranked: number }>(`/api/jobs/${jobId}/rerank`, { method: 'POST' }),

  // ------------------------------------------------------------ profile

  getProfile: () => request<{ exists: boolean; profile: Profile | null }>('/api/profile'),

  saveProfile: (profile: Profile) =>
    request<Profile>('/api/profile', { method: 'PUT', body: JSON.stringify(profile) }),

  uploadCV: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Profile>('/api/profile/upload', { method: 'POST', body: form })
  },

  // ------------------------------------------------------- applications

  getApplications: () => request<Application[]>('/api/applications'),

  getApplication: (jobId: number) => request<Application | null>(`/api/jobs/${jobId}/application`),

  generate: (jobId: number, augmentation?: Augmentation) =>
    request<Application>(`/api/jobs/${jobId}/generate`, {
      method: 'POST',
      body: JSON.stringify({ augmentation: augmentation ?? null }),
    }),

  saveCV: (jobId: number, cv: GeneratedCV) =>
    request<Application>(`/api/jobs/${jobId}/application/cv`, {
      method: 'PUT',
      body: JSON.stringify({ cv }),
    }),

  saveCoverLetter: (jobId: number, text: string) =>
    request<Application>(`/api/jobs/${jobId}/application/cover-letter`, {
      method: 'PUT',
      body: JSON.stringify({ cover_letter_text: text }),
    }),

  downloadUrl: (jobId: number, filename: string) => `/api/jobs/${jobId}/download/${filename}`,

  bulkGenerate: (jobIds: number[], augmentation?: Augmentation) =>
    request<GenerationStatus>('/api/generate/bulk', {
      method: 'POST',
      body: JSON.stringify({ job_ids: jobIds, augmentation: augmentation ?? null }),
    }),

  getGenerationStatus: () => request<GenerationStatus>('/api/generate/status'),
}
