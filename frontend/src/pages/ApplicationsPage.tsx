import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import { EmptyState } from '../components/ui'
import type { Application } from '../types'

export function ApplicationsPage() {
  const [apps, setApps] = useState<Application[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .getApplications()
      .then(setApps)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load applications'))
  }, [])

  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Applications</h1>
      <p className="mt-0.5 text-sm text-slate-500">
        Every generated CV and cover letter, newest first.
      </p>

      {error && (
        <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      <div className="mt-5 space-y-2.5">
        {apps === null ? (
          <p className="py-10 text-center text-sm text-slate-400">Loading…</p>
        ) : apps.length === 0 ? (
          <EmptyState title="No applications generated yet">
            Open a job and press <span className="font-medium text-slate-700">Generate CV &amp; Cover
            Letter</span>, or select several jobs on the Jobs page and use Generate Selected.
          </EmptyState>
        ) : (
          apps.map((app) => (
            <div
              key={app.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div className="min-w-0">
                <Link
                  to={`/applications/${app.job_id}`}
                  className="text-[15px] font-semibold text-slate-900 hover:text-slate-600"
                >
                  {app.job?.title ?? `Job ${app.job_id}`}
                </Link>
                <p className="mt-0.5 text-sm text-slate-600">
                  {app.job?.company ?? 'Unknown company'}
                  {app.job?.location && <span className="text-slate-400"> · {app.job.location}</span>}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 capitalize text-slate-600">
                    {app.augmentation}
                  </span>
                  {app.has_cv_docx && (
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-slate-600">DOCX</span>
                  )}
                  {app.has_cv_pdf && (
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-slate-600">PDF</span>
                  )}
                  {app.flagged_additions.length > 0 && (
                    <span className="rounded-md bg-amber-50 px-2 py-0.5 text-amber-700">
                      {app.flagged_additions.length} inferred to review
                    </span>
                  )}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={`/applications/${app.job_id}`}
                  className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700"
                >
                  Open
                </Link>
                {app.has_cv_docx && (
                  <a
                    href={api.downloadUrl(app.job_id, 'cv.docx')}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    CV DOCX
                  </a>
                )}
                {app.has_cv_pdf && (
                  <a
                    href={api.downloadUrl(app.job_id, 'cv.pdf')}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    CV PDF
                  </a>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
