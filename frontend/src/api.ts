import type {
  Job,
  JobFilterState,
  JobListResponse,
  JobStatus,
  RefreshStatus,
  SearchSettings,
  SourceInfo,
  Stats,
} from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
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
  return res.json() as Promise<T>
}

export const api = {
  getSettings: () => request<SearchSettings>('/api/settings'),

  saveSettings: (settings: SearchSettings) =>
    request<SearchSettings>('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),

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
}
