import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import { EmptyState } from '../components/ui'
import { APPLICATION_STAGES } from '../types'
import type { Application, ApplicationStage, ProfileMeta } from '../types'

export function ApplicationsPage() {
  const [apps, setApps] = useState<Application[] | null>(null)
  const [profiles, setProfiles] = useState<ProfileMeta[]>([])
  const [savingJobId, setSavingJobId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .getApplications()
      .then(setApps)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load applications'))
    api.listProfiles().then(setProfiles).catch(() => undefined)
  }, [])

  const updateStage = async (jobId: number, stage: ApplicationStage) => {
    setSavingJobId(jobId)
    try {
      const updated = await api.setApplicationStage(jobId, stage)
      setApps((prev) =>
        prev
          ? prev.map((app) => (app.job_id === jobId ? { ...app, stage: updated.stage, stage_updated_at: updated.stage_updated_at, updated_at: updated.updated_at } : app))
          : prev,
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update application stage')
    } finally {
      setSavingJobId(null)
    }
  }

  return (
    <div className="mx-auto max-w-screen-2xl px-6 py-6">
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
                  <span className="rounded-md bg-sky-50 px-2 py-0.5 capitalize text-sky-700">
                    {app.stage.replaceAll('_', ' ')}
                  </span>
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
                  {app.profile_id && (() => {
                    const pName = profiles.find((p) => p.id === app.profile_id)?.name
                    return pName ? (
                      <span className="rounded-md bg-violet-50 px-2 py-0.5 text-violet-700">
                        {pName}
                      </span>
                    ) : null
                  })()}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={app.stage}
                  disabled={savingJobId === app.job_id}
                  onChange={(e) => updateStage(app.job_id, e.target.value as ApplicationStage)}
                  className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs capitalize text-slate-700 focus:border-slate-500 focus:outline-none"
                >
                  {APPLICATION_STAGES.map((stage) => (
                    <option key={stage} value={stage} className="capitalize">
                      {stage.replaceAll('_', ' ')}
                    </option>
                  ))}
                </select>
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
