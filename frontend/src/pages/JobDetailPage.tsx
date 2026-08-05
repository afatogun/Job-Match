import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api'
import { AugmentationPicker } from '../components/AugmentationPicker'
import { Markdown } from '../components/Markdown'
import { Card, ScoreBadge, Spinner, StatusBadge } from '../components/ui'
import { applyUrl, formatSalary, hostOf, relativeDate } from '../format'
import { JOB_STATUSES } from '../types'
import type { Augmentation, Job, JobStatus } from '../types'

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{value}</dd>
    </div>
  )
}

function SkillList({ title, skills, tone }: { title: string; skills: string[]; tone: 'good' | 'gap' }) {
  if (!skills.length) return null
  const cls = tone === 'good' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'
  return (
    <div>
      <p className="text-xs font-medium text-slate-500">{title}</p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {skills.map((s) => (
          <span key={s} className={`rounded-md px-2 py-0.5 text-xs font-medium ${cls}`}>
            {s}
          </span>
        ))}
      </div>
    </div>
  )
}

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [ranking, setRanking] = useState(false)
  const [augmentation, setAugmentation] = useState<Augmentation | undefined>()

  useEffect(() => {
    if (!id) return
    api
      .getJob(Number(id))
      .then((j) => {
        setJob(j)
        setError(null)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load job'))
  }, [id])

  useEffect(() => {
    api
      .getSettings()
      .then((s) => setAugmentation((prev) => prev ?? s.default_augmentation))
      .catch(() => undefined)
  }, [])

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

  const generate = async () => {
    if (!job) return
    setGenerating(true)
    setError(null)
    try {
      await api.generate(job.id, augmentation)
      navigate(`/applications/${job.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generation failed')
    } finally {
      setGenerating(false)
    }
  }

  const rerank = async () => {
    if (!job) return
    setRanking(true)
    setError(null)
    try {
      await api.rerank(job.id)
      setJob(await api.getJob(job.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ranking failed')
    } finally {
      setRanking(false)
    }
  }

  if (error && !job) {
    return (
      <div className="mx-auto max-w-screen-2xl px-6 py-10">
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
    <div className="mx-auto max-w-screen-2xl px-6 py-6">
      <Link to="/jobs" className="text-sm text-slate-500 hover:text-slate-900">
        ← Back to jobs
      </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 gap-4">
          <ScoreBadge score={job.relevance_score} isAi={job.ai_score !== null} />
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{job.title}</h1>
            <p className="mt-1 text-sm text-slate-600">
              {job.company ?? 'Unknown company'}
              {job.location && <span className="text-slate-400"> · {job.location}</span>}
            </p>
          </div>
        </div>
        <StatusBadge status={job.status} />
      </div>

      {error && (
        <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200">
          {error}
        </p>
      )}

      <Card className="mt-5 space-y-4 p-5">
        <div>
          <p className="text-sm font-semibold text-slate-900">Generate application pack</p>
          <p className="mt-0.5 text-xs text-slate-500">
            Writes a tailored CV and cover letter for this vacancy only.
          </p>
        </div>

        <AugmentationPicker value={augmentation} onChange={setAugmentation} />

        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
          {job.has_application ? (
            <Link
              to={`/applications/${job.id}`}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
            >
              Open Application
            </Link>
          ) : null}
          <button
            onClick={generate}
            disabled={generating}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:bg-slate-400"
          >
            {generating && <Spinner />}
            {generating
              ? 'Writing…'
              : job.has_application
                ? 'Regenerate CV & Cover Letter'
                : 'Generate CV & Cover Letter'}
          </button>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
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
      </Card>

      <Card className="mt-4 p-5">
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

      <Card className="mt-4 space-y-4 p-5">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-slate-900">Match analysis</p>
          <button
            onClick={rerank}
            disabled={ranking}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {ranking && <Spinner className="h-3 w-3" />}
            {job.ai_score === null ? 'Rank with AI' : 'Re-rank'}
          </button>
        </div>

        {job.ai_score === null ? (
          <p className="text-sm text-slate-500">
            Local relevance score is {job.local_score ?? '—'}. Rank with AI for matching skills,
            gaps and seniority fit. Needs a profile and an OpenAI key.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <p className="text-xs font-medium text-slate-500">Overall match</p>
                <p className="text-2xl font-semibold tabular-nums text-slate-900">
                  {Math.round(job.ai_score)}
                  <span className="text-sm font-normal text-slate-400">/100</span>
                </p>
              </div>
              {job.ai_seniority_fit && (
                <div>
                  <p className="text-xs font-medium text-slate-500">Seniority fit</p>
                  <p className="mt-1 text-sm capitalize text-slate-800">{job.ai_seniority_fit}</p>
                </div>
              )}
            </div>
            {job.ai_reason && <p className="text-sm text-slate-700">{job.ai_reason}</p>}
            <SkillList title="Matching skills" skills={job.ai_matching_skills} tone="good" />
            <SkillList title="Missing skills" skills={job.ai_missing_skills} tone="gap" />
          </>
        )}
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
