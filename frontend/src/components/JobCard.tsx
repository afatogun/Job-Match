import { Link } from 'react-router-dom'

import { applyUrl, formatSalary, relativeDate } from '../format'
import type { Job } from '../types'
import { Chip, ScoreBadge, StatusBadge } from './ui'

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
        <ScoreBadge score={job.relevance_score} isAi={job.ai_score !== null} />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <Link
              to={`/jobs/${job.id}`}
              className="text-[15px] font-semibold text-slate-900 hover:text-slate-600"
            >
              {job.title}
            </Link>
            <div className="flex items-center gap-1.5">
              {job.has_application && (
                <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 ring-1 ring-inset ring-indigo-200">
                  Pack ready
                </span>
              )}
              <StatusBadge status={job.status} />
            </div>
          </div>

          <p className="mt-0.5 text-sm text-slate-600">
            {job.company ?? 'Unknown company'}
            {job.location && <span className="text-slate-400"> · {job.location}</span>}
          </p>

          {job.ai_reason && (
            <p className="mt-2 border-l-2 border-slate-200 pl-2.5 text-sm italic text-slate-600">
              {job.ai_reason}
            </p>
          )}

          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            <Chip>{job.source}</Chip>
            <Chip>{relativeDate(job.date_posted)}</Chip>
            {job.is_remote && <Chip>Remote</Chip>}
            {job.job_type && <Chip>{job.job_type.replace(/_/g, ' ')}</Chip>}
            {salary && <Chip>{salary}</Chip>}
          </div>

          {(job.ai_matching_skills.length > 0 || job.matching_terms.length > 0) && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {(job.ai_matching_skills.length ? job.ai_matching_skills : job.matching_terms)
                .slice(0, 6)
                .map((term) => (
                  <span
                    key={term}
                    className="rounded-md bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700"
                  >
                    {term}
                  </span>
                ))}
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Link
              to={`/jobs/${job.id}`}
              className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700"
            >
              View Job
            </Link>
            <Link
              to={job.has_application ? `/applications/${job.id}` : `/jobs/${job.id}`}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
            >
              {job.has_application ? 'Open Application' : 'Generate Application'}
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
