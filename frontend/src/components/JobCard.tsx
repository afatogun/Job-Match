import { Link } from 'react-router-dom'

import { applyUrl, formatSalary, relativeDate } from '../format'
import type { Job } from '../types'
import { Chip, StatusBadge } from './ui'

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) {
    // Scores arrive with AI ranking (step 13); don't fake one in the meantime.
    return (
      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-slate-100 text-[11px] font-medium text-slate-400">
        —
      </div>
    )
  }
  const tone =
    score >= 70 ? 'bg-emerald-50 text-emerald-700' : score >= 45 ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'
  return (
    <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg text-sm font-semibold ${tone}`}>
      {Math.round(score)}
    </div>
  )
}

interface Props {
  job: Job
  selected: boolean
  onToggleSelect: (id: number) => void
}

export function JobCard({ job, selected, onToggleSelect }: Props) {
  const salary = formatSalary(job)

  return (
    <div className="group rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300 hover:shadow">
      <div className="flex gap-4">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelect(job.id)}
          className="mt-1.5 h-4 w-4 shrink-0 rounded border-slate-300 accent-slate-900"
          aria-label={`Select ${job.title}`}
        />
        <ScoreBadge score={job.relevance_score} />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <Link
              to={`/jobs/${job.id}`}
              className="text-[15px] font-semibold text-slate-900 hover:text-slate-600"
            >
              {job.title}
            </Link>
            <StatusBadge status={job.status} />
          </div>

          <p className="mt-0.5 text-sm text-slate-600">
            {job.company ?? 'Unknown company'}
            {job.location && <span className="text-slate-400"> · {job.location}</span>}
          </p>

          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            <Chip>{job.source}</Chip>
            <Chip>{relativeDate(job.date_posted)}</Chip>
            {job.is_remote && <Chip>Remote</Chip>}
            {job.job_type && <Chip>{job.job_type.replace(/_/g, ' ')}</Chip>}
            {salary && <Chip>{salary}</Chip>}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Link
              to={`/jobs/${job.id}`}
              className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700"
            >
              View Job
            </Link>
            <a
              href={applyUrl(job)}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
            >
              Open Original Job ↗
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
