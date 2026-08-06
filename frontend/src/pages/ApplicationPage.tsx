import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api'
import { AugmentationPicker } from '../components/AugmentationPicker'
import { Markdown } from '../components/Markdown'
import { Card, Spinner } from '../components/ui'
import { applyUrl } from '../format'
import { APPLICATION_STAGES } from '../types'
import type { Application, ApplicationStage, Augmentation, GeneratedCV, Job } from '../types'

type Tab = 'cv' | 'cover' | 'prep'

function CVPreview({ cv }: { cv: GeneratedCV }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-8 text-slate-800 shadow-sm">
      <div className="text-center">
        <h2 className="text-xl font-bold tracking-tight text-slate-900">{cv.full_name}</h2>
        {cv.headline && <p className="mt-0.5 text-sm text-slate-600">{cv.headline}</p>}
        {cv.contact.length > 0 && (
          <p className="mt-1 text-xs text-slate-500">{cv.contact.join('  |  ')}</p>
        )}
      </div>

      {cv.summary && (
        <section className="mt-5">
          <h3 className="border-b border-slate-200 pb-1 text-[11px] font-bold uppercase tracking-wider text-slate-700">
            Professional Summary
          </h3>
          <p className="mt-2 text-sm leading-relaxed">{cv.summary}</p>
        </section>
      )}

      {cv.skills.length > 0 && (
        <section className="mt-4">
          <h3 className="border-b border-slate-200 pb-1 text-[11px] font-bold uppercase tracking-wider text-slate-700">
            Skills
          </h3>
          <p className="mt-2 text-sm">{cv.skills.join(', ')}</p>
        </section>
      )}

      {cv.experience.length > 0 && (
        <section className="mt-4">
          <h3 className="border-b border-slate-200 pb-1 text-[11px] font-bold uppercase tracking-wider text-slate-700">
            Experience
          </h3>
          {cv.experience.map((exp, i) => (
            <div key={i} className="mt-3">
              <p className="text-sm font-semibold">
                {exp.role}
                {exp.company && <span className="font-normal text-slate-600">, {exp.company}</span>}
              </p>
              {(exp.dates || exp.location) && (
                <p className="text-xs italic text-slate-500">
                  {[exp.dates, exp.location].filter(Boolean).join('  |  ')}
                </p>
              )}
              <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm marker:text-slate-400">
                {exp.bullets.map((b, j) => (
                  <li key={j} className={b.inferred ? 'bg-amber-50/70' : ''}>
                    {b.text}
                    {b.inferred && (
                      <span className="ml-1.5 rounded bg-amber-100 px-1 text-[10px] font-medium text-amber-800">
                        inferred
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}

      {cv.projects.length > 0 && (
        <section className="mt-4">
          <h3 className="border-b border-slate-200 pb-1 text-[11px] font-bold uppercase tracking-wider text-slate-700">
            Projects
          </h3>
          {cv.projects.map((p, i) => (
            <div key={i} className="mt-2">
              <p className="text-sm font-semibold">
                {p.name}
                {p.technologies.length > 0 && (
                  <span className="ml-1.5 text-xs font-normal text-slate-500">
                    ({p.technologies.join(', ')})
                  </span>
                )}
              </p>
              <p className="text-sm">{p.description}</p>
            </div>
          ))}
        </section>
      )}

      {cv.education.length > 0 && (
        <section className="mt-4">
          <h3 className="border-b border-slate-200 pb-1 text-[11px] font-bold uppercase tracking-wider text-slate-700">
            Education
          </h3>
          {cv.education.map((e, i) => (
            <p key={i} className="mt-1.5 text-sm">
              <span className="font-semibold">{e.qualification}</span>
              {[e.institution, e.year].filter(Boolean).length > 0 &&
                `, ${[e.institution, e.year].filter(Boolean).join(', ')}`}
            </p>
          ))}
        </section>
      )}
    </div>
  )
}

export function ApplicationPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const id = Number(jobId)

  const [app, setApp] = useState<Application | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [tab, setTab] = useState<Tab>('cv')
  const [editing, setEditing] = useState(false)
  const [cvDraft, setCvDraft] = useState('')
  const [coverDraft, setCoverDraft] = useState('')
  const [augmentation, setAugmentation] = useState<Augmentation | undefined>()
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = async () => {
    const [a, j] = await Promise.all([api.getApplication(id), api.getJob(id)])
    setApp(a)
    setJob(j)
    if (a) {
      setAugmentation(a.augmentation)
      setCoverDraft(a.cover_letter_text ?? '')
      setCvDraft(JSON.stringify(a.cv, null, 2))
    }
  }

  useEffect(() => {
    if (!id) return
    load().catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const regenerate = async () => {
    setBusy('regenerate')
    setError(null)
    setNotice(null)
    try {
      await api.generate(id, augmentation)
      await load()
      setEditing(false)
      setNotice('Regenerated.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Regeneration failed')
    } finally {
      setBusy(null)
    }
  }

  const saveCV = async () => {
    setBusy('save-cv')
    setError(null)
    try {
      const parsed = JSON.parse(cvDraft) as GeneratedCV
      setApp(await api.saveCV(id, parsed))
      setEditing(false)
      setNotice('CV saved and documents re-rendered.')
    } catch (e) {
      setError(
        e instanceof SyntaxError
          ? 'That is not valid JSON - check for a missing comma or quote.'
          : e instanceof Error
            ? e.message
            : 'Could not save',
      )
    } finally {
      setBusy(null)
    }
  }

  const saveCover = async () => {
    setBusy('save-cover')
    setError(null)
    try {
      setApp(await api.saveCoverLetter(id, coverDraft))
      setNotice('Cover letter saved and DOCX re-rendered.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setBusy(null)
    }
  }

  const generateInterviewPrep = async () => {
    setBusy('prep')
    setError(null)
    try {
      const updated = await api.generateInterviewPrep(id)
      setApp(updated)
      setTab('prep')
      setNotice('Interview prep generated.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not generate interview prep')
    } finally {
      setBusy(null)
    }
  }

  const updateStage = async (stage: ApplicationStage) => {
    setBusy('stage')
    setError(null)
    try {
      const updated = await api.setApplicationStage(id, stage)
      setApp((prev) => (prev ? { ...prev, stage: updated.stage, stage_updated_at: updated.stage_updated_at, updated_at: updated.updated_at } : prev))
      setNotice('Application stage updated.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update stage')
    } finally {
      setBusy(null)
    }
  }

  if (error && !app) {
    return (
      <div className="mx-auto max-w-screen-2xl px-6 py-10">
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
        <Link to="/applications" className="mt-4 inline-block text-sm text-slate-600">
          ← Back to applications
        </Link>
      </div>
    )
  }

  if (!app) {
    return (
      <div className="mx-auto max-w-screen-2xl px-6 py-10 text-center">
        <p className="text-sm text-slate-500">
          No application has been generated for this job yet.
        </p>
        <Link
          to={`/jobs/${id}`}
          className="mt-4 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white"
        >
          Go to the job and generate one
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-screen-2xl px-6 py-6">
      <Link to="/applications" className="text-sm text-slate-500 hover:text-slate-900">
        ← Back to applications
      </Link>

      <div className="mt-3">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          {job?.title ?? `Job ${id}`}
        </h1>
        <p className="mt-0.5 text-sm text-slate-600">
          {job?.company ?? 'Unknown company'}
          {job?.location && <span className="text-slate-400"> · {job.location}</span>}
        </p>
      </div>

      {error && (
        <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200">
          {error}
        </p>
      )}
      {notice && (
        <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700 ring-1 ring-inset ring-emerald-200">
          {notice}
        </p>
      )}

      <div className="mt-5 flex items-start gap-6">
        {/* Left: sticky job description panel */}
        {job?.description && (
          <div className="w-2/5 shrink-0">
            <div className="sticky top-[57px] max-h-[calc(100vh-80px)] overflow-y-auto rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Job Description
              </p>
              <Markdown text={job.description} />
            </div>
          </div>
        )}

        {/* Right: generated documents + controls */}
        <div className="min-w-0 flex-1">
          {app.flagged_additions.length > 0 && (
            <Card className="border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-semibold text-amber-900">
                Review before sending — {app.flagged_additions.length} inferred addition
                {app.flagged_additions.length > 1 ? 's' : ''}
              </p>
              <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-amber-900">
                {app.flagged_additions.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </Card>
          )}

          {(app.style_notes.length > 0 || app.monotonous) && (
            <Card className="mt-4 border-sky-200 bg-sky-50 p-4">
              <p className="text-sm font-semibold text-sky-900">Writing check</p>
              {app.style_notes.length > 0 && (
                <p className="mt-1 text-sm text-sky-900">
                  Phrases that read as AI-written slipped through:{' '}
                  <span className="font-medium">{app.style_notes.join(', ')}</span>. Worth rewording
                  before you send it.
                </p>
              )}
              {app.monotonous && (
                <p className="mt-1 text-sm text-sky-900">
                  Cover letter sentences are all a similar length, which reads as machine-written. Break
                  one up or merge two.
                </p>
              )}
            </Card>
          )}

          <Card className="mt-4 space-y-4 p-5">
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex-1">
                <p className="text-xs font-medium text-slate-500">Augmentation level</p>
                <div className="mt-1.5">
                  <AugmentationPicker value={augmentation} onChange={setAugmentation} compact />
                </div>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500">Application stage</p>
                <select
                  value={app.stage}
                  disabled={busy !== null}
                  onChange={(e) => updateStage(e.target.value as ApplicationStage)}
                  className="mt-1.5 rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm capitalize text-slate-700 focus:border-slate-500 focus:outline-none"
                >
                  {APPLICATION_STAGES.map((stage) => (
                    <option key={stage} value={stage} className="capitalize">
                      {stage.replaceAll('_', ' ')}
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={regenerate}
                disabled={busy !== null}
                className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:bg-slate-400"
              >
                {busy === 'regenerate' && <Spinner />}
                Regenerate
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
              {app.has_cv_docx && (
                <a
                  href={api.downloadUrl(id, 'cv.docx')}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Download CV (DOCX)
                </a>
              )}
              {app.has_cv_pdf ? (
                <a
                  href={api.downloadUrl(id, 'cv.pdf')}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Download CV (PDF)
                </a>
              ) : (
                <span
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-400"
                  title="PDF generation failed for this application. Regenerate to try again."
                >
                  PDF unavailable
                </span>
              )}
              {app.has_cover_letter_docx && (
                <a
                  href={api.downloadUrl(id, 'cover-letter.docx')}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Download Cover Letter (DOCX)
                </a>
              )}
              {job && (
                <a
                  href={applyUrl(job)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Open Original Job ↗
                </a>
              )}
            </div>
            {app.model && (
              <p className="text-[11px] text-slate-400">
                Generated with {app.model} · {new Date(app.updated_at).toLocaleString('en-IE')}
              </p>
            )}
            {app.stage_updated_at && (
              <p className="text-[11px] text-slate-400">
                Stage updated {new Date(app.stage_updated_at).toLocaleString('en-IE')}
              </p>
            )}
          </Card>

          <div className="mt-5 flex gap-1 border-b border-slate-200">
            {(['cv', 'cover', 'prep'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${
                  tab === t
                    ? 'border-slate-900 text-slate-900'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                {t === 'cv' ? 'CV' : t === 'cover' ? 'Cover Letter' : 'Interview Prep'}
              </button>
            ))}
          </div>

          {tab === 'cv' ? (
            <div className="mt-4">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm text-slate-500">
                  {editing ? 'Editing structured CV content as JSON.' : 'Preview of the rendered CV.'}
                </p>
                <div className="flex gap-2">
                  {editing && (
                    <button
                      onClick={saveCV}
                      disabled={busy !== null}
                      className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:bg-slate-400"
                    >
                      {busy === 'save-cv' && <Spinner />}
                      Save &amp; re-render
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setEditing((e) => !e)
                      setCvDraft(JSON.stringify(app.cv, null, 2))
                    }}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    {editing ? 'Cancel' : 'Edit'}
                  </button>
                </div>
              </div>

              {editing ? (
                <textarea
                  value={cvDraft}
                  onChange={(e) => setCvDraft(e.target.value)}
                  spellCheck={false}
                  className="h-[32rem] w-full rounded-lg border border-slate-300 p-3 font-mono text-xs focus:border-slate-500 focus:outline-none"
                />
              ) : app.cv ? (
                <CVPreview cv={app.cv} />
              ) : (
                <p className="text-sm text-slate-500">No CV content.</p>
              )}
            </div>
          ) : tab === 'cover' ? (
            <div className="mt-4">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm text-slate-500">Edit freely — saving re-renders the DOCX.</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(coverDraft)
                      setNotice('Cover letter copied to clipboard.')
                    }}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Copy text
                  </button>
                  <button
                    onClick={saveCover}
                    disabled={busy !== null}
                    className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:bg-slate-400"
                  >
                    {busy === 'save-cover' && <Spinner />}
                    Save &amp; re-render
                  </button>
                </div>
              </div>
              <textarea
                value={coverDraft}
                onChange={(e) => setCoverDraft(e.target.value)}
                className="h-[32rem] w-full rounded-lg border border-slate-300 bg-white p-5 text-[15px] leading-relaxed focus:border-slate-500 focus:outline-none"
              />
            </div>
          ) : (
            <div className="mt-4 space-y-4">
              <Card className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Interview preparation</p>
                    <p className="mt-0.5 text-sm text-slate-500">
                      Targeted interview questions generated from this job description and your profile.
                    </p>
                  </div>
                  <button
                    onClick={generateInterviewPrep}
                    disabled={busy !== null}
                    className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:bg-slate-400"
                  >
                    {busy === 'prep' && <Spinner />}
                    {app.interview_prep ? 'Regenerate prep' : 'Generate prep'}
                  </button>
                </div>
              </Card>

              {app.interview_prep ? (
                <Card className="space-y-4 p-5">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 uppercase text-slate-600">
                      {app.interview_prep.source}
                    </span>
                    <span>
                      Generated {new Date(app.interview_prep.generated_at).toLocaleString('en-IE')}
                    </span>
                  </div>

                  {app.interview_prep.source_note && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                      {app.interview_prep.source_note}
                    </div>
                  )}

                  {app.interview_prep.focus_areas.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-slate-500">Focus areas</p>
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {app.interview_prep.focus_areas.map((area) => (
                          <span key={area} className="rounded-md bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-700">
                            {area}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {app.interview_prep.tips && (
                    <div>
                      <p className="text-xs font-medium text-slate-500">Preparation tip</p>
                      <p className="mt-1 text-sm text-slate-700">{app.interview_prep.tips}</p>
                    </div>
                  )}

                  <div className="space-y-3">
                    {app.interview_prep.questions.map((q, idx) => (
                      <div key={`${q.question}-${idx}`} className="rounded-lg border border-slate-200 bg-white p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-medium text-slate-900">Q{idx + 1}. {q.question}</p>
                          <span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-medium capitalize text-amber-700">
                            {q.difficulty}
                          </span>
                        </div>
                        {q.why_relevant && (
                          <p className="mt-1 text-sm text-slate-600">Why it matters: {q.why_relevant}</p>
                        )}
                      </div>
                    ))}
                  </div>

                  {app.interview_prep.references.length > 0 && (
                    <div className="space-y-2 border-t border-slate-100 pt-3">
                      <p className="text-xs font-medium text-slate-500">External references</p>
                      {app.interview_prep.references.map((ref, idx) => (
                        <div key={`${ref.url}-${idx}`} className="rounded-lg border border-slate-200 p-3">
                          <a
                            href={ref.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-medium text-slate-800 underline decoration-slate-300 underline-offset-2 hover:text-slate-900"
                          >
                            {ref.title}
                          </a>
                          {ref.snippet && <p className="mt-1 text-xs text-slate-600">{ref.snippet}</p>}
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              ) : (
                <p className="text-sm text-slate-500">Generate interview prep to get role-specific questions and focus areas.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
