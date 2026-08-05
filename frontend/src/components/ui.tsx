import type { JobStatus } from '../types'

export const STATUS_STYLES: Record<JobStatus, string> = {
  new: 'bg-sky-50 text-sky-700 ring-sky-200',
  saved: 'bg-violet-50 text-violet-700 ring-violet-200',
  generated: 'bg-amber-50 text-amber-700 ring-amber-200',
  applied: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  interview: 'bg-teal-50 text-teal-700 ring-teal-200',
  rejected: 'bg-slate-100 text-slate-600 ring-slate-200',
}

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ring-1 ring-inset ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  )
}

export function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">
      {children}
    </span>
  )
}

export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>{children}</div>
  )
}

export function EmptyState({
  title,
  children,
}: {
  title: string
  children?: React.ReactNode
}) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
      <p className="text-base font-medium text-slate-800">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-sm text-slate-500">{children}</div>}
    </div>
  )
}

export function Placeholder({ title, step }: { title: string; step: string }) {
  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
      <div className="mt-6 rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
        <p className="text-sm text-slate-600">Not built yet.</p>
        <p className="mt-1 text-sm text-slate-500">{step}</p>
      </div>
    </div>
  )
}

export function Spinner({ className = '' }: { className?: string }) {
  return (
    <svg className={`h-4 w-4 animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}
