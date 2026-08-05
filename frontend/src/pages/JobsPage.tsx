import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '../api'
import { JobCard } from '../components/JobCard'
import { JobFilters } from '../components/JobFilters'
import { RefreshPanel } from '../components/RefreshPanel'
import { StatsBar } from '../components/StatsBar'
import { EmptyState } from '../components/ui'
import type { Job, JobFilterState, RefreshStatus, SourceInfo, Stats } from '../types'

const PAGE_SIZE = 50

const INITIAL_FILTERS: JobFilterState = {
  q: '',
  source: '',
  status: '',
  posted_within_days: '',
  sort: 'newest',
}

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<Stats | null>(null)
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [filters, setFilters] = useState<JobFilterState>(INITIAL_FILTERS)
  const [refresh, setRefresh] = useState<RefreshStatus | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const pollRef = useRef<number | null>(null)

  const loadJobs = useCallback(async (current: JobFilterState) => {
    try {
      const [list, s] = await Promise.all([api.getJobs(current, PAGE_SIZE), api.getStats()])
      setJobs(list.items)
      setTotal(list.total)
      setStats(s)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    api.getSources().then(setSources).catch(() => setSources([]))
  }, [])

  // Debounce so typing in the search box doesn't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => loadJobs(filters), 250)
    return () => clearTimeout(t)
  }, [filters, loadJobs])

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPolling = useCallback(() => {
    stopPolling()
    pollRef.current = window.setInterval(async () => {
      try {
        const status = await api.getRefreshStatus()
        setRefresh(status)
        if (!status.running) {
          stopPolling()
          loadJobs(filters)
        }
      } catch {
        stopPolling()
      }
    }, 1500)
  }, [filters, loadJobs, stopPolling])

  // Pick up a run already in flight (e.g. after a page reload mid-refresh).
  useEffect(() => {
    api
      .getRefreshStatus()
      .then((status) => {
        setRefresh(status)
        if (status.running) startPolling()
      })
      .catch(() => undefined)
    return stopPolling
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleRefresh = async () => {
    setError(null)
    try {
      setRefresh(await api.startRefresh())
      startPolling()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start refresh')
    }
  }

  const toggleSelect = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-6 py-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Jobs</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Live vacancies in Ireland, linked to their genuine application pages.
          </p>
        </div>
        {stats?.last_refresh_at && (
          <p className="text-xs text-slate-400">
            Last refreshed {new Date(stats.last_refresh_at).toLocaleString('en-IE')}
          </p>
        )}
      </div>

      <StatsBar stats={stats} />
      <RefreshPanel status={refresh} onRefresh={handleRefresh} error={error} />

      <div className="space-y-3 pt-1">
        <JobFilters filters={filters} sources={sources} onChange={setFilters} />

        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>
            {total} job{total === 1 ? '' : 's'}
            {jobs.length < total && ` · showing first ${jobs.length}`}
          </span>
          {selected.size > 0 && (
            <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-600">
              {selected.size} selected · bulk generation arrives in step 19
            </span>
          )}
        </div>

        {loading ? (
          <p className="py-10 text-center text-sm text-slate-400">Loading…</p>
        ) : jobs.length === 0 ? (
          <EmptyState title={total === 0 ? 'No jobs discovered yet' : 'No jobs match these filters'}>
            {total === 0 ? (
              <>
                Press <span className="font-medium text-slate-700">Find New Jobs</span> to search Indeed
                Ireland using your saved search settings.
              </>
            ) : (
              'Try widening the date range or clearing the search box.'
            )}
          </EmptyState>
        ) : (
          <div className="space-y-2.5">
            {jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                selected={selected.has(job.id)}
                onToggleSelect={toggleSelect}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
