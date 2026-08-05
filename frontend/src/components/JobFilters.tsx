import { JOB_STATUSES } from '../types'
import type { JobFilterState, ProfileMeta, SourceInfo } from '../types'

interface Props {
  filters: JobFilterState
  sources: SourceInfo[]
  profiles: ProfileMeta[]
  onChange: (next: JobFilterState) => void
}

const selectClass =
  'rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-700 focus:border-slate-500 focus:outline-none'

export function JobFilters({ filters, sources, profiles, onChange }: Props) {
  const set = <K extends keyof JobFilterState>(key: K, value: JobFilterState[K]) =>
    onChange({ ...filters, [key]: value })

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="search"
        value={filters.q}
        onChange={(e) => set('q', e.target.value)}
        placeholder="Search title, company, description…"
        className="min-w-[240px] flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm placeholder:text-slate-400 focus:border-slate-500 focus:outline-none"
      />

      <select value={filters.source} onChange={(e) => set('source', e.target.value)} className={selectClass}>
        <option value="">All sources</option>
        {sources.map((s) => (
          <option key={s.name} value={s.name}>
            {s.label}
          </option>
        ))}
      </select>

      <select value={filters.status} onChange={(e) => set('status', e.target.value)} className={selectClass}>
        <option value="">Any status</option>
        {JOB_STATUSES.map((s) => (
          <option key={s} value={s} className="capitalize">
            {s}
          </option>
        ))}
      </select>

      <select
        value={filters.posted_within_days}
        onChange={(e) => set('posted_within_days', e.target.value)}
        className={selectClass}
      >
        <option value="">Any date</option>
        <option value="1">Today</option>
        <option value="3">Last 3 days</option>
        <option value="7">Last week</option>
        <option value="30">Last 30 days</option>
      </select>

      <select
        value={filters.min_score}
        onChange={(e) => set('min_score', e.target.value)}
        className={selectClass}
      >
        <option value="">Any score</option>
        <option value="70">70+ (good match)</option>
        <option value="50">50+</option>
        <option value="30">30+</option>
      </select>

      <select
        value={filters.salary_min}
        onChange={(e) => set('salary_min', e.target.value)}
        className={selectClass}
      >
        <option value="">Any min salary</option>
        <option value="30000">30k+</option>
        <option value="50000">50k+</option>
        <option value="70000">70k+</option>
        <option value="90000">90k+</option>
      </select>

      <select
        value={filters.salary_max}
        onChange={(e) => set('salary_max', e.target.value)}
        className={selectClass}
      >
        <option value="">Any max salary</option>
        <option value="50000">Up to 50k</option>
        <option value="70000">Up to 70k</option>
        <option value="90000">Up to 90k</option>
        <option value="120000">Up to 120k</option>
      </select>

      {profiles.length > 1 && (
        <select
          value={filters.profile_id}
          onChange={(e) => set('profile_id', e.target.value)}
          className={selectClass}
        >
          <option value="">All profiles</option>
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}{p.is_active ? ' ✓' : ''}
            </option>
          ))}
        </select>
      )}

      <select
        value={filters.sort}
        onChange={(e) => set('sort', e.target.value as JobFilterState['sort'])}
        className={selectClass}
      >
        <option value="newest">Newest first</option>
        <option value="best">Best match</option>
        <option value="salary_high">Highest salary</option>
      </select>
    </div>
  )
}
