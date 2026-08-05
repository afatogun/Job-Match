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
  ProfileMeta,
  RefreshStatus,
  SearchSettings,
  SourceInfo,
  Stats,
} from './types'

function resolveUrl(path: string): string {
  const base = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
  if (!base) return path.startsWith('/') ? path : `/${path}`
  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData
  const res = await fetch(resolveUrl(path), {
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
  getSettings: (profileId?: string) =>
    request<SearchSettings>(`/api/settings${profileId ? `?profile_id=${profileId}` : ''}`),

  saveSettings: (settings: SearchSettings, profileId?: string) =>
    request<SearchSettings>(`/api/settings${profileId ? `?profile_id=${profileId}` : ''}`, { method: 'PUT', body: JSON.stringify(settings) }),

  getSources: () => request<SourceInfo[]>('/api/settings/sources'),

  getStats: () => request<Stats>('/api/stats'),

  clearJobs: () => request<void>('/api/jobs', { method: 'DELETE' }),

  getJobs: (filters: Partial<JobFilterState>, limit = 50, offset = 0) => {
    const params = new URLSearchParams()
    if (filters.q) params.set('q', filters.q)
    if (filters.source) params.set('source', filters.source)
    if (filters.status) params.set('status', filters.status)
    if (filters.posted_within_days) params.set('posted_within_days', filters.posted_within_days)
    if (filters.min_score) params.set('min_score', filters.min_score)
    if (filters.sort) params.set('sort', filters.sort)
    if (filters.profile_id) params.set('profile_id', filters.profile_id)
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

  // --------------------------------------------------- multi-profile management

  listProfiles: () => request<ProfileMeta[]>('/api/profiles'),

  createProfile: (name: string) =>
    request<ProfileMeta>('/api/profiles', { method: 'POST', body: JSON.stringify({ name }) }),

  deleteProfile: (id: string) =>
    request<void>(`/api/profiles/${id}`, { method: 'DELETE' }),

  activateProfile: (id: string) =>
    request<ProfileMeta[]>(`/api/profiles/${id}/activate`, { method: 'PUT' }),

  renameProfile: (id: string, name: string) =>
    request<ProfileMeta>(`/api/profiles/${id}/rename`, { method: 'PUT', body: JSON.stringify({ name }) }),

  getProfileById: (id: string) =>
    request<{ exists: boolean; profile: Profile | null }>(`/api/profiles/${id}`),

  saveProfileById: (id: string, profile: Profile) =>
    request<Profile>(`/api/profiles/${id}`, { method: 'PUT', body: JSON.stringify(profile) }),

  uploadCVById: (id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Profile>(`/api/profiles/${id}/upload`, { method: 'POST', body: form })
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

  downloadUrl: (jobId: number, filename: string) => resolveUrl(`/api/jobs/${jobId}/download/${filename}`),

  bulkGenerate: (jobIds: number[], augmentation?: Augmentation) =>
    request<GenerationStatus>('/api/generate/bulk', {
      method: 'POST',
      body: JSON.stringify({ job_ids: jobIds, augmentation: augmentation ?? null }),
    }),

  getGenerationStatus: () => request<GenerationStatus>('/api/generate/status'),
}
