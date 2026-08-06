import type { RefreshStatus } from '../types'
import { Spinner } from './ui'

interface Props {
  status: RefreshStatus | null
  onRefresh: () => void
  error: string | null
}

export function RefreshPanel({ status, onRefresh, error }: Props) {
  const running = status?.running ?? false
  const pct = status && status.total > 0 ? Math.round((status.completed / status.total) * 100) : 0
  const finished = !running && status?.finished_at

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Job discovery</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Searches your configured sources for live vacancies matching your search settings.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={running}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {running && <Spinner />}
          {running ? 'Searching…' : 'Find New Jobs'}
        </button>
      </div>

      {running && (
        <div className="mt-3">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-slate-900 transition-all duration-500"
              style={{ width: `${Math.max(pct, 4)}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {status?.current ?? 'Starting…'} · {status?.completed ?? 0}/{status?.total ?? 0} searches ·{' '}
            {status?.inserted ?? 0} new
          </p>
        </div>
      )}

      {finished && (
        <p className="mt-3 text-xs text-slate-500">
          Last run found {status.found} listings — {status.inserted} new, {status.updated} already known,{' '}
          {status.filtered} filtered out.
        </p>
      )}

      {error && (
        <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 ring-1 ring-inset ring-red-200">
          {error}
        </p>
      )}

      {status && status.errors.length > 0 && (
        <div className="mt-3 rounded-lg bg-amber-50 p-3 ring-1 ring-inset ring-amber-200">
          <p className="text-xs font-medium text-amber-900">
            {status.errors.length} search{status.errors.length > 1 ? 'es' : ''} failed — other sources still
            returned results.
          </p>
          <ul className="mt-1.5 space-y-1">
            {status.errors.map((e, i) => (
              <li key={i} className="text-[11px] text-amber-800">
                <span className="font-medium">
                  {e.source} · {e.search_term}
                </span>
                : {e.error.split('\n')[0]}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
