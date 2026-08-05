import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'
import { AugmentationPicker } from '../components/AugmentationPicker'
import { JobCard } from '../components/JobCard'
import { JobFilters } from '../components/JobFilters'
import { RefreshPanel } from '../components/RefreshPanel'
import { StatsBar } from '../components/StatsBar'
import { EmptyState, Spinner } from '../components/ui'
import type {
  Augmentation,
  GenerationStatus,
  Job,
  JobFilterState,
  ProfileMeta,
  RefreshStatus,
  SourceInfo,
  Stats,
} from '../types'

const PAGE_SIZE = 50

const INITIAL_FILTERS: JobFilterState = {
  q: '',
  source: '',
  status: '',
  profile_id: '',
  posted_within_days: '',
  min_score: '',
  salary_min: '',
  salary_max: '',
  sort: 'best',
}

export function JobsPage() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<Stats | null>(null)
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [profiles, setProfiles] = useState<ProfileMeta[]>([])
  const [filters, setFilters] = useState<JobFilterState>(INITIAL_FILTERS)
  const [refresh, setRefresh] = useState<RefreshStatus | null>(null)
  const [generation, setGeneration] = useState<GenerationStatus | null>(null)
  const [augmentation, setAugmentation] = useState<Augmentation | undefined>()
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refreshPoll = useRef<number | null>(null)
  const genPoll = useRef<number | null>(null)

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
    api.listProfiles().then(setProfiles).catch(() => setProfiles([]))
    api
      .getSettings()
      .then((s) => setAugmentation((prev) => prev ?? s.default_augmentation))
      .catch(() => undefined)
  }, [])

  // Debounce so typing in the search box doesn't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => loadJobs(filters), 250)
    return () => clearTimeout(t)
  }, [filters, loadJobs])

  const stopRefreshPoll = useCallback(() => {
    if (refreshPoll.current !== null) {
      clearInterval(refreshPoll.current)
      refreshPoll.current = null
    }
  }, [])

  const startRefreshPoll = useCallback(() => {
    stopRefreshPoll()
    refreshPoll.current = window.setInterval(async () => {
      try {
        const status = await api.getRefreshStatus()
        setRefresh(status)
        if (!status.running) {
          stopRefreshPoll()
          loadJobs(filters)
        }
      } catch {
        stopRefreshPoll()
      }
    }, 1500)
  }, [filters, loadJobs, stopRefreshPoll])

  const startGenPoll = useCallback(() => {
    if (genPoll.current !== null) clearInterval(genPoll.current)
    genPoll.current = window.setInterval(async () => {
      try {
        const status = await api.getGenerationStatus()
        setGeneration(status)
        if (!status.running) {
          if (genPoll.current !== null) clearInterval(genPoll.current)
          genPoll.current = null
          setSelected(new Set())
          loadJobs(filters)
        }
      } catch {
        if (genPoll.current !== null) clearInterval(genPoll.current)
        genPoll.current = null
      }
    }, 2000)
  }, [filters, loadJobs])

  // Pick up runs already in flight (e.g. after a page reload).
  useEffect(() => {
    api
      .getRefreshStatus()
      .then((s) => {
        setRefresh(s)
        if (s.running) startRefreshPoll()
      })
      .catch(() => undefined)
    api
      .getGenerationStatus()
      .then((s) => {
        setGeneration(s)
        if (s.running) startGenPoll()
      })
      .catch(() => undefined)
    return () => {
      stopRefreshPoll()
      if (genPoll.current !== null) clearInterval(genPoll.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleRefresh = async () => {
    setError(null)
    try {
      setRefresh(await api.startRefresh())
      startRefreshPoll()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start refresh')
    }
  }

  const handleClearJobs = async () => {
    if (!confirm('Delete all jobs and applications? This cannot be undone.')) return
    setError(null)
    try {
      await api.clearJobs()
      setJobs([])
      setTotal(0)
      setSelected(new Set())
      setStats(null)
      await loadJobs(filters)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not clear jobs')
    }
  }

  const handleBulkGenerate = async () => {
    if (selected.size === 0) return
    setError(null)
    try {
      setGeneration(await api.bulkGenerate([...selected], augmentation))
      startGenPoll()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start generation')
    }
  }

  const toggleSelect = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const generating = generation?.running ?? false

  return (
    <div className="mx-auto max-w-screen-2xl space-y-4 px-6 py-6">
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
      <div className="flex flex-wrap items-start gap-3">
        <div className="flex-1">
          <RefreshPanel status={refresh} onRefresh={handleRefresh} error={error} />
        </div>
        {(stats?.total_jobs ?? 0) > 0 && (
          <button
            onClick={handleClearJobs}
            className="rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            Clear all jobs
          </button>
        )}
      </div>

      <div className="space-y-3 pt-1">
        <JobFilters filters={filters} sources={sources} profiles={profiles} onChange={setFilters} />

        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
          <span>
            {total} job{total === 1 ? '' : 's'}
            {jobs.length < total && ` · showing first ${jobs.length}`}
          </span>

          {selected.size > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-slate-600">{selected.size} selected</span>
              <AugmentationPicker value={augmentation} onChange={setAugmentation} compact />
              <button
                onClick={handleBulkGenerate}
                disabled={generating}
                className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 disabled:bg-slate-400"
              >
                {generating && <Spinner className="h-3 w-3" />}
                Generate Selected
              </button>
              <button
                onClick={() => setSelected(new Set())}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                Clear
              </button>
            </div>
          )}
        </div>

        {generation && (generation.running || generation.errors.length > 0) && (
          <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <p className="text-xs text-slate-600">
              {generation.running
                ? `Generating: ${generation.current ?? '…'} (${generation.completed}/${generation.total})`
                : `Generated ${generation.generated} of ${generation.total} application packs.`}
            </p>
            {generation.errors.length > 0 && (
              <ul className="mt-1.5 space-y-1">
                {generation.errors.map((e, i) => (
                  <li key={i} className="text-[11px] text-amber-800">
                    {e}
                  </li>
                ))}
              </ul>
            )}
            {!generation.running && generation.generated > 0 && (
              <button
                onClick={() => navigate('/applications')}
                className="mt-2 text-xs font-medium text-slate-800 underline underline-offset-2"
              >
                View applications
              </button>
            )}
          </div>
        )}

        {loading ? (
          <p className="py-10 text-center text-sm text-slate-400">Loading…</p>
        ) : jobs.length === 0 ? (
          <EmptyState title={total === 0 ? 'No jobs discovered yet' : 'No jobs match these filters'}>
            {total === 0 ? (
              <>
                Press <span className="font-medium text-slate-700">Find New Jobs</span> to search your
                configured sources using your saved search settings.
              </>
            ) : (
              'Try widening the date range, lowering the minimum score, or clearing the search box.'
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
                profiles={profiles}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
