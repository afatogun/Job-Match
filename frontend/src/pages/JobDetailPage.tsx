import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api'
import { Markdown } from '../components/Markdown'
import { Card, StatusBadge } from '../components/ui'
import { applyUrl, formatSalary, hostOf, relativeDate } from '../format'
import { JOB_STATUSES } from '../types'
import type { Job, JobStatus } from '../types'

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{value}</dd>
    </div>
  )
}

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!id) return
    api
      .getJob(Number(id))
      .then(setJob)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load job'))
  }, [id])

  const changeStatus = async (status: JobStatus) => {
    if (!job) return
    setSaving(true)
    try {
      setJob(await api.setJobStatus(job.id, status))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update status')
    } finally {
      setSaving(false)
    }
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10">
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
        <Link to="/jobs" className="mt-4 inline-block text-sm text-slate-600 hover:text-slate-900">
          ← Back to jobs
        </Link>
      </div>
    )
  }

  if (!job) return <p className="py-16 text-center text-sm text-slate-400">Loading…</p>

  const salary = formatSalary(job)
  const url = applyUrl(job)

  return (
    <div className="mx-auto max-w-4xl px-6 py-6">
      <Link to="/jobs" className="text-sm text-slate-500 hover:text-slate-900">
        ← Back to jobs
      </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{job.title}</h1>
          <p className="mt-1 text-sm text-slate-600">
            {job.company ?? 'Unknown company'}
            {job.location && <span className="text-slate-400"> · {job.location}</span>}
          </p>
        </div>
        <StatusBadge status={job.status} />
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <button
          disabled
          title="Arrives in steps 14–16"
          className="cursor-not-allowed rounded-lg bg-slate-200 px-4 py-2 text-sm font-medium text-slate-500"
        >
          Generate CV &amp; Cover Letter
        </button>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          Open Original Job ↗
        </a>
        <select
          value={job.status}
          disabled={saving}
          onChange={(e) => changeStatus(e.target.value as JobStatus)}
          className="rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm capitalize text-slate-700 focus:border-slate-500 focus:outline-none"
        >
          {JOB_STATUSES.map((s) => (
            <option key={s} value={s} className="capitalize">
              {s}
            </option>
          ))}
        </select>
      </div>

      <Card className="mt-5 p-5">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Meta label="Source" value={<span className="capitalize">{job.source}</span>} />
          <Meta label="Posted" value={relativeDate(job.date_posted)} />
          <Meta label="Salary" value={salary ?? 'Not stated'} />
          <Meta label="Job type" value={job.job_type?.replace(/_/g, ' ') ?? 'Not stated'} />
        </dl>
        <div className="mt-4 border-t border-slate-100 pt-3">
          <dt className="text-xs font-medium text-slate-500">Original URL</dt>
          <dd className="mt-0.5 truncate text-sm">
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-700 underline decoration-slate-300 underline-offset-2 hover:text-slate-900"
            >
              {hostOf(url)}
              {job.job_url_direct && (
                <span className="ml-2 text-xs text-emerald-600">direct application link</span>
              )}
            </a>
          </dd>
        </div>
      </Card>

      <Card className="mt-4 border-dashed bg-slate-50/60 p-5">
        <p className="text-sm font-medium text-slate-700">Match analysis</p>
        <p className="mt-1 text-sm text-slate-500">
          Match score, matching skills, missing skills and the explanation arrive with AI ranking in step 13.
        </p>
      </Card>

      <Card className="mt-4 p-6">
        <h2 className="text-sm font-semibold text-slate-900">Job description</h2>
        <div className="mt-3">
          {job.description ? (
            <Markdown text={job.description} />
          ) : (
            <p className="text-sm text-slate-500">
              This source did not return a description. Open the original posting to read it.
            </p>
          )}
        </div>
      </Card>
    </div>
  )
}
