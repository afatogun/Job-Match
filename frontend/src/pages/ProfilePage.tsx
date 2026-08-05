import { useEffect, useRef, useState } from 'react'

import { api } from '../api'
import { Card, Spinner } from '../components/ui'
import type { EducationItem, ExperienceItem, Profile, ProfileMeta, ProjectItem } from '../types'

const input =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none'

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <div>
      <label className="text-xs font-medium text-slate-600">{label}</label>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={`mt-1 ${input}`}
      />
    </div>
  )
}

function Area({
  label,
  hint,
  value,
  onChange,
  rows = 3,
}: {
  label: string
  hint?: string
  value: string
  onChange: (v: string) => void
  rows?: number
}) {
  return (
    <div>
      <label className="text-sm font-medium text-slate-700">{label}</label>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
      <textarea
        value={value}
        rows={rows}
        onChange={(e) => onChange(e.target.value)}
        className={`mt-1.5 ${input} resize-y`}
      />
    </div>
  )
}

function ListArea({
  label,
  value,
  onChange,
  hint,
}: {
  label: string
  value: string[]
  onChange: (v: string[]) => void
  hint?: string
}) {
  const [text, setText] = useState(value.join('\n'))
  useEffect(() => setText(value.join('\n')), [value])
  return (
    <div>
      <label className="text-sm font-medium text-slate-700">{label}</label>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
      <textarea
        value={text}
        rows={4}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => onChange(text.split('\n').map((s) => s.trim()).filter(Boolean))}
        className={`mt-1.5 ${input} resize-y`}
      />
    </div>
  )
}

export function ProfilePage() {
  const [profiles, setProfiles] = useState<ProfileMeta[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [creatingNew, setCreatingNew] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const loadProfiles = async () => {
    const list = await api.listProfiles()
    setProfiles(list)
    return list
  }

  const selectProfile = async (id: string) => {
    setSelectedId(id)
    setProfile(null)
    setError(null)
    setNotice(null)
    try {
      const r = await api.getProfileById(id)
      setProfile(r.profile)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load profile')
    }
  }

  useEffect(() => {
    loadProfiles()
      .then((list) => {
        const active = list.find((p) => p.is_active) ?? list[0]
        if (active) return selectProfile(active.id)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load profiles'))
      .finally(() => setLoaded(true))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const upload = async (file: File) => {
    if (!selectedId) return
    setUploading(true)
    setError(null)
    setNotice(null)
    try {
      setProfile(await api.uploadCVById(selectedId, file))
      await loadProfiles()
      setNotice('CV parsed. Review everything below before generating applications.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const save = async () => {
    if (!profile || !selectedId) return
    setSaving(true)
    setError(null)
    try {
      setProfile(await api.saveProfileById(selectedId, profile))
      setNotice('Profile saved.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setSaving(false)
    }
  }

  const activate = async (id: string) => {
    try {
      const updated = await api.activateProfile(id)
      setProfiles(updated)
      setNotice('Active profile updated. New applications will use this profile.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not activate profile')
    }
  }

  const createNew = async () => {
    const name = newName.trim()
    if (!name) return
    try {
      const created = await api.createProfile(name)
      setNewName('')
      setCreatingNew(false)
      await loadProfiles()
      await selectProfile(created.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create profile')
    }
  }

  const doRename = async (id: string) => {
    const name = renameValue.trim()
    if (!name) return
    try {
      await api.renameProfile(id, name)
      setRenamingId(null)
      await loadProfiles()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not rename profile')
    }
  }

  const doDelete = async (id: string) => {
    if (!confirm('Delete this profile? This cannot be undone.')) return
    try {
      await api.deleteProfile(id)
      const list = await loadProfiles()
      const next = list.find((p) => p.is_active) ?? list[0]
      if (next) await selectProfile(next.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete profile')
    }
  }

  const patch = <K extends keyof Profile>(key: K, value: Profile[K]) =>
    setProfile((p) => (p ? { ...p, [key]: value } : p))

  const patchExp = (i: number, next: Partial<ExperienceItem>) =>
    setProfile((p) =>
      p ? { ...p, experience: p.experience.map((e, j) => (i === j ? { ...e, ...next } : e)) } : p,
    )

  const patchProj = (i: number, next: Partial<ProjectItem>) =>
    setProfile((p) =>
      p ? { ...p, projects: p.projects.map((e, j) => (i === j ? { ...e, ...next } : e)) } : p,
    )

  const patchEdu = (i: number, next: Partial<EducationItem>) =>
    setProfile((p) =>
      p ? { ...p, education: p.education.map((e, j) => (i === j ? { ...e, ...next } : e)) } : p,
    )

  if (!loaded) return <p className="py-16 text-center text-sm text-slate-400">Loading…</p>

  const selectedMeta = profiles.find((p) => p.id === selectedId)

  return (
    <div className="mx-auto max-w-screen-2xl px-6 py-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Profiles</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Each profile is a separate CV. The active one is used for all job generation.
        </p>
      </div>

      <div className="mt-5 flex items-start gap-6">
        {/* ---- Left sidebar: profile list ---- */}
        <div className="w-56 shrink-0 space-y-1">
          {profiles.map((meta) => (
            <div key={meta.id} className="group relative">
              {renamingId === meta.id ? (
                <div className="flex gap-1 rounded-lg border border-slate-300 bg-white p-2">
                  <input
                    autoFocus
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') doRename(meta.id)
                      if (e.key === 'Escape') setRenamingId(null)
                    }}
                    className="min-w-0 flex-1 rounded border-0 text-sm focus:outline-none"
                  />
                  <button
                    onClick={() => doRename(meta.id)}
                    className="text-xs font-medium text-slate-700"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setRenamingId(null)}
                    className="text-xs text-slate-400"
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => selectProfile(meta.id)}
                  className={`w-full rounded-lg px-3 py-2.5 text-left transition ${
                    selectedId === meta.id
                      ? 'bg-slate-900 text-white'
                      : 'hover:bg-slate-100 text-slate-700'
                  }`}
                >
                  <span className="block truncate text-sm font-medium">{meta.name}</span>
                  {meta.is_active && (
                    <span
                      className={`mt-0.5 block text-[10px] font-semibold uppercase tracking-wide ${
                        selectedId === meta.id ? 'text-slate-400' : 'text-emerald-600'
                      }`}
                    >
                      Active
                    </span>
                  )}
                </button>
              )}

              {renamingId !== meta.id && selectedId === meta.id && (
                <div className="mt-1 flex flex-wrap gap-1 px-1">
                  {!meta.is_active && (
                    <button
                      onClick={() => activate(meta.id)}
                      className="rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 hover:bg-emerald-100"
                    >
                      Make Active
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setRenamingId(meta.id)
                      setRenameValue(meta.name)
                    }}
                    className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-200"
                  >
                    Rename
                  </button>
                  {profiles.length > 1 && (
                    <button
                      onClick={() => doDelete(meta.id)}
                      className="rounded bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-600 hover:bg-red-100"
                    >
                      Delete
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}

          {creatingNew ? (
            <div className="flex gap-1 rounded-lg border border-slate-300 bg-white p-2">
              <input
                autoFocus
                value={newName}
                placeholder="Profile name"
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') createNew()
                  if (e.key === 'Escape') setCreatingNew(false)
                }}
                className="min-w-0 flex-1 rounded border-0 text-sm focus:outline-none"
              />
              <button onClick={createNew} className="text-xs font-medium text-slate-700">
                Create
              </button>
              <button onClick={() => setCreatingNew(false)} className="text-xs text-slate-400">
                ✕
              </button>
            </div>
          ) : (
            <button
              onClick={() => setCreatingNew(true)}
              className="mt-2 w-full rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm text-slate-500 hover:border-slate-400 hover:text-slate-700"
            >
              + New Profile
            </button>
          )}
        </div>

        {/* ---- Right panel: profile editor ---- */}
        <div className="min-w-0 flex-1 space-y-4">
          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200">
              {error}
            </p>
          )}
          {notice && (
            <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700 ring-1 ring-inset ring-emerald-200">
              {notice}
            </p>
          )}

          {selectedMeta && !selectedMeta.is_active && (
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Viewing <span className="font-semibold">{selectedMeta.name}</span> — this is not the active profile. Applications will still use the active one until you click <strong>Make Active</strong>.
            </p>
          )}

          <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-900">
              {selectedMeta ? selectedMeta.name : 'CV'}
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              PDF, DOCX or TXT. The text is extracted locally, then structured by OpenAI.
              {profile?.source_filename && (
                <>
                  {' '}
                  Current source: <span className="font-medium">{profile.source_filename}</span>
                </>
              )}
            </p>
            <div className="mt-3 flex items-center gap-3">
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx,.txt"
                disabled={uploading || !selectedId}
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) upload(f)
                }}
                className="text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-900 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700"
              />
              {uploading && (
                <span className="flex items-center gap-2 text-sm text-slate-500">
                  <Spinner /> Parsing…
                </span>
              )}
            </div>
          </Card>

          {!profile ? (
            <Card className="border-dashed p-10 text-center">
              <p className="text-sm text-slate-600">No profile content yet.</p>
              <p className="mt-1 text-sm text-slate-500">
                Upload a CV above, or{' '}
                <button
                  onClick={() =>
                    setProfile({
                      personal: {
                        full_name: '',
                        email: '',
                        phone: '',
                        location: '',
                        linkedin: '',
                        github: '',
                        website: '',
                      },
                      professional_summary: '',
                      experience: [],
                      achievements: [],
                      projects: [],
                      education: [],
                      skills: [],
                      additional_experience: '',
                      additional_projects: '',
                      additional_skills: '',
                      notes_for_ai: '',
                      source_filename: '',
                      updated_at: '',
                    })
                  }
                  className="font-medium text-slate-800 underline underline-offset-2"
                >
                  start one by hand
                </button>
                .
              </p>
            </Card>
          ) : (
            <>
              <Card className="space-y-4 p-5">
                <h2 className="text-sm font-semibold text-slate-900">Personal information</h2>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field
                    label="Full name"
                    value={profile.personal.full_name}
                    onChange={(v) => patch('personal', { ...profile.personal, full_name: v })}
                  />
                  <Field
                    label="Email"
                    value={profile.personal.email}
                    onChange={(v) => patch('personal', { ...profile.personal, email: v })}
                  />
                  <Field
                    label="Phone"
                    value={profile.personal.phone}
                    onChange={(v) => patch('personal', { ...profile.personal, phone: v })}
                  />
                  <Field
                    label="Location"
                    value={profile.personal.location}
                    onChange={(v) => patch('personal', { ...profile.personal, location: v })}
                  />
                  <Field
                    label="LinkedIn"
                    value={profile.personal.linkedin}
                    onChange={(v) => patch('personal', { ...profile.personal, linkedin: v })}
                  />
                  <Field
                    label="GitHub"
                    value={profile.personal.github}
                    onChange={(v) => patch('personal', { ...profile.personal, github: v })}
                  />
                </div>
                <Area
                  label="Professional summary"
                  value={profile.professional_summary}
                  onChange={(v) => patch('professional_summary', v)}
                  rows={4}
                />
                <ListArea
                  label="Skills"
                  hint="One per line."
                  value={profile.skills}
                  onChange={(v) => patch('skills', v)}
                />
              </Card>

              <Card className="space-y-4 p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-slate-900">
                    Experience ({profile.experience.length})
                  </h2>
                  <button
                    onClick={() =>
                      patch('experience', [
                        ...profile.experience,
                        {
                          role: '',
                          company: '',
                          location: '',
                          start_date: '',
                          end_date: '',
                          summary: '',
                          achievements: [],
                          technologies: [],
                        },
                      ])
                    }
                    className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Add role
                  </button>
                </div>
                {profile.experience.map((exp, i) => (
                  <div key={i} className="space-y-3 rounded-lg border border-slate-200 p-3">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <Field label="Role" value={exp.role} onChange={(v) => patchExp(i, { role: v })} />
                      <Field
                        label="Company"
                        value={exp.company}
                        onChange={(v) => patchExp(i, { company: v })}
                      />
                      <Field
                        label="Start"
                        value={exp.start_date}
                        onChange={(v) => patchExp(i, { start_date: v })}
                      />
                      <Field
                        label="End"
                        value={exp.end_date}
                        onChange={(v) => patchExp(i, { end_date: v })}
                      />
                    </div>
                    <Area
                      label="Summary"
                      value={exp.summary}
                      onChange={(v) => patchExp(i, { summary: v })}
                      rows={2}
                    />
                    <ListArea
                      label="Achievements"
                      hint="One per line. Real metrics here are what make strong CV bullets possible."
                      value={exp.achievements}
                      onChange={(v) => patchExp(i, { achievements: v })}
                    />
                    <ListArea
                      label="Technologies"
                      value={exp.technologies}
                      onChange={(v) => patchExp(i, { technologies: v })}
                    />
                    <button
                      onClick={() =>
                        patch(
                          'experience',
                          profile.experience.filter((_, j) => j !== i),
                        )
                      }
                      className="text-xs font-medium text-red-600 hover:text-red-700"
                    >
                      Remove role
                    </button>
                  </div>
                ))}
              </Card>

              <Card className="space-y-4 p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-slate-900">
                    Projects ({profile.projects.length})
                  </h2>
                  <button
                    onClick={() =>
                      patch('projects', [
                        ...profile.projects,
                        { name: '', description: '', technologies: [], link: '' },
                      ])
                    }
                    className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Add project
                  </button>
                </div>
                {profile.projects.map((p, i) => (
                  <div key={i} className="space-y-3 rounded-lg border border-slate-200 p-3">
                    <Field label="Name" value={p.name} onChange={(v) => patchProj(i, { name: v })} />
                    <Area
                      label="Description"
                      value={p.description}
                      onChange={(v) => patchProj(i, { description: v })}
                      rows={2}
                    />
                    <ListArea
                      label="Technologies"
                      value={p.technologies}
                      onChange={(v) => patchProj(i, { technologies: v })}
                    />
                    <button
                      onClick={() =>
                        patch(
                          'projects',
                          profile.projects.filter((_, j) => j !== i),
                        )
                      }
                      className="text-xs font-medium text-red-600 hover:text-red-700"
                    >
                      Remove project
                    </button>
                  </div>
                ))}
              </Card>

              <Card className="space-y-4 p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-slate-900">
                    Education ({profile.education.length})
                  </h2>
                  <button
                    onClick={() =>
                      patch('education', [
                        ...profile.education,
                        { qualification: '', institution: '', year: '', details: '' },
                      ])
                    }
                    className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Add education
                  </button>
                </div>
                {profile.education.map((e, i) => (
                  <div key={i} className="grid gap-3 rounded-lg border border-slate-200 p-3 sm:grid-cols-3">
                    <Field
                      label="Qualification"
                      value={e.qualification}
                      onChange={(v) => patchEdu(i, { qualification: v })}
                    />
                    <Field
                      label="Institution"
                      value={e.institution}
                      onChange={(v) => patchEdu(i, { institution: v })}
                    />
                    <Field label="Year" value={e.year} onChange={(v) => patchEdu(i, { year: v })} />
                  </div>
                ))}
              </Card>

              <Card className="space-y-4 p-5">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">Extras</h2>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Anything not in your CV that the AI should know.
                  </p>
                </div>
                <ListArea
                  label="Achievements"
                  hint="One per line."
                  value={profile.achievements}
                  onChange={(v) => patch('achievements', v)}
                />
                <Area
                  label="Additional experience"
                  value={profile.additional_experience}
                  onChange={(v) => patch('additional_experience', v)}
                />
                <Area
                  label="Additional projects"
                  value={profile.additional_projects}
                  onChange={(v) => patch('additional_projects', v)}
                />
                <Area
                  label="Additional skills"
                  value={profile.additional_skills}
                  onChange={(v) => patch('additional_skills', v)}
                />
                <Area
                  label="Notes for the AI"
                  hint="Context, preferences, things to emphasise or avoid."
                  value={profile.notes_for_ai}
                  onChange={(v) => patch('notes_for_ai', v)}
                  rows={4}
                />
              </Card>

              <div className="sticky bottom-4 flex items-center gap-3 rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
                <button
                  onClick={save}
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:bg-slate-400"
                >
                  {saving && <Spinner />}
                  Save profile
                </button>
                {profile.updated_at && (
                  <span className="text-xs text-slate-400">
                    Last saved {new Date(profile.updated_at).toLocaleString('en-IE')}
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
