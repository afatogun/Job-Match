import { useEffect, useState } from 'react'

import { api } from '../api'
import { AugmentationPicker } from '../components/AugmentationPicker'
import { Card } from '../components/ui'
import type { OpenAIModel, ProfileMeta, SearchSettings, SourceInfo, WorkMode } from '../types'

const WORK_MODES: { value: WorkMode; label: string }[] = [
  { value: 'any', label: 'Any' },
  { value: 'remote', label: 'Remote' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'onsite', label: 'On-site' },
]

const AI_MODELS: { value: string; label: string; blurb: string }[] = [
  {
    value: 'gpt-4.1-nano',
    label: 'Lower performance (fastest, lowest cost)',
    blurb: 'Best for quick iterations and minimal token spend.',
  },
  {
    value: 'gpt-4.1-mini',
    label: 'Base performance (recommended)',
    blurb: 'Balanced quality, speed and cost for most tasks.',
  },
  {
    value: 'gpt-4.1',
    label: 'Plus performance',
    blurb: 'High quality outputs for ranking and document generation.',
  },
  {
    value: 'gpt-5',
    label: 'Max performance (best quality)',
    blurb: 'Best output quality for the most demanding ranking and generation tasks.',
  },
]

const inputClass =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none'

/** Comma-separated editing keeps list fields simple and paste-friendly. */
function ListField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string
  hint?: string
  value: string[]
  onChange: (next: string[]) => void
}) {
  const [text, setText] = useState(value.join(', '))

  useEffect(() => {
    setText(value.join(', '))
  }, [value])

  return (
    <div>
      <label className="text-sm font-medium text-slate-700">{label}</label>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
      <textarea
        value={text}
        rows={2}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => onChange(text.split(',').map((s) => s.trim()).filter(Boolean))}
        className={`mt-1.5 ${inputClass} resize-y`}
        placeholder="Comma separated"
      />
    </div>
  )
}

export function SettingsPage() {
  const [profiles, setProfiles] = useState<ProfileMeta[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState<string | undefined>()
  const [settings, setSettings] = useState<SearchSettings | null>(null)
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.listProfiles().then((list) => {
      setProfiles(list)
      const active = list.find((p) => p.is_active) ?? list[0]
      if (active) setSelectedProfileId(active.id)
    }).catch(() => undefined)
    api.getSources().then(setSources).catch(() => setSources([]))
  }, [])

  useEffect(() => {
    if (selectedProfileId === undefined) return
    setSettings(null)
    api.getSettings(selectedProfileId).then(setSettings).catch((e) => setError(String(e)))
  }, [selectedProfileId])

  const update = <K extends keyof SearchSettings>(key: K, value: SearchSettings[K]) =>
    setSettings((prev) => (prev ? { ...prev, [key]: value } : prev))

  const save = async () => {
    if (!settings) return
    setSaving(true)
    setMessage(null)
    setError(null)
    try {
      setSettings(await api.saveSettings(settings, selectedProfileId))
      setMessage('Settings saved.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save settings')
    } finally {
      setSaving(false)
    }
  }

  if (!settings && !error) {
    return <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
  }

  return (
    <div className="mx-auto max-w-screen-2xl space-y-4 px-6 py-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Settings</h1>
          <p className="mt-0.5 text-sm text-slate-500">Controls what each profile's job search looks for.</p>
        </div>
        {profiles.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-500">Profile:</span>
            <select
              value={selectedProfileId ?? ''}
              onChange={(e) => setSelectedProfileId(e.target.value || undefined)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 focus:border-slate-500 focus:outline-none"
            >
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}{p.is_active ? ' (active)' : ''}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {!settings ? (
        <p className="py-8 text-center text-sm text-slate-400">Loading…</p>
      ) : (
        <>

      <Card className="space-y-5 p-6">
        <h2 className="text-sm font-semibold text-slate-900">Job search</h2>

        <ListField
          label="Target job titles"
          hint="Each title becomes its own search. Levels below are prepended to each title automatically."
          value={settings.target_titles}
          onChange={(v) => update('target_titles', v)}
        />

        <div>
          <label className="text-sm font-medium text-slate-700">Seniority levels</label>
          <p className="mt-0.5 text-xs text-slate-500">
            Selected levels are searched as prefixes ("Senior Software Engineer", "Junior Software Engineer", etc.) alongside the base title. Leave all unselected to search without a level prefix.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {['Junior', 'Mid', 'Senior', 'Lead', 'Principal', 'Staff', 'Director'].map((lv) => {
              const active = settings.target_levels.includes(lv)
              return (
                <button
                  key={lv}
                  type="button"
                  onClick={() =>
                    update(
                      'target_levels',
                      active
                        ? settings.target_levels.filter((l) => l !== lv)
                        : [...settings.target_levels, lv],
                    )
                  }
                  className={`rounded-full px-3 py-1 text-sm font-medium transition ${
                    active
                      ? 'bg-slate-900 text-white'
                      : 'border border-slate-300 text-slate-600 hover:border-slate-500'
                  }`}
                >
                  {lv}
                </button>
              )
            })}
          </div>
        </div>

        <ListField
          label="Desired keywords"
          hint="Boosts relevance score (up to 25%) for jobs that mention these — not a strict filter. Useful for specifying technologies or domains (e.g. React, Python, analytical chemistry). The AI ranking layer then checks full profile fit independently."
          value={settings.keywords}
          onChange={(v) => update('keywords', v)}
        />
        <ListField
          label="Excluded keywords"
          hint="A job is dropped if any of these appear in its title or description."
          value={settings.excluded_keywords}
          onChange={(v) => update('excluded_keywords', v)}
        />
        <ListField
          label="Excluded title words"
          hint="A job is dropped if its title contains any of these."
          value={settings.excluded_title_words}
          onChange={(v) => update('excluded_title_words', v)}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="text-sm font-medium text-slate-700">Location</label>
            <input
              value={settings.location}
              onChange={(e) => update('location', e.target.value)}
              className={`mt-1.5 ${inputClass}`}
            />
            <p className="mt-1 text-xs text-slate-500">Defaults to Ireland. Try "Dublin, Ireland" to narrow.</p>
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700">Maximum job age (days)</label>
            <input
              type="number"
              min={1}
              max={90}
              value={settings.max_job_age_days}
              onChange={(e) => update('max_job_age_days', Number(e.target.value))}
              className={`mt-1.5 ${inputClass}`}
            />
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700">Work arrangement</label>
            <select
              value={settings.work_mode}
              onChange={(e) => update('work_mode', e.target.value as WorkMode)}
              className={`mt-1.5 ${inputClass}`}
            >
              {WORK_MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
            {settings.work_mode === 'hybrid' || settings.work_mode === 'onsite' ? (
              <p className="mt-1 text-xs text-amber-700">
                Job boards only expose a remote flag, so hybrid and on-site are approximated from the listing
                text and may be imprecise.
              </p>
            ) : (
              <p className="mt-1 text-xs text-slate-500">Remote is filtered at the source.</p>
            )}
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700">Results per title</label>
            <input
              type="number"
              min={5}
              max={200}
              value={settings.results_per_title}
              onChange={(e) => update('results_per_title', Number(e.target.value))}
              className={`mt-1.5 ${inputClass}`}
            />
            <p className="mt-1 text-xs text-slate-500">Higher values make each refresh slower.</p>
          </div>
        </div>

        <div>
          <label className="text-sm font-medium text-slate-700">Sources</label>
          <div className="mt-2 flex flex-wrap gap-3">
            {sources.map((s) => (
              <label key={s.name} className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={settings.sources.includes(s.name)}
                  onChange={(e) =>
                    update(
                      'sources',
                      e.target.checked
                        ? [...settings.sources, s.name]
                        : settings.sources.filter((x) => x !== s.name),
                    )
                  }
                  className="h-4 w-4 rounded border-slate-300 accent-slate-900"
                />
                {s.label}
              </label>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-slate-500">
            LinkedIn rate-limits aggressively without proxies and will often return nothing; its
            failures never block the other sources. JobsIreland only exposes its most recent
            vacancies to non-browser clients, so it contributes little for technical roles.
          </p>
        </div>

        <div className="flex items-center gap-3 border-t border-slate-100 pt-4">
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:bg-slate-400"
          >
            {saving ? 'Saving…' : 'Save settings'}
          </button>
          {message && <span className="text-sm text-emerald-600">{message}</span>}
          {error && <span className="text-sm text-red-600">{error}</span>}
        </div>
      </Card>

      <Card className="space-y-5 p-6">
        <h2 className="text-sm font-semibold text-slate-900">AI</h2>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="text-sm font-medium text-slate-700">Model</label>
            <select
              value={settings.openai_model}
              onChange={(e) => update('openai_model', e.target.value as OpenAIModel)}
              className={`mt-1.5 ${inputClass}`}
            >
              {AI_MODELS.map((model) => (
                <option key={model.value} value={model.value}>
                  {model.label}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-slate-500">
              Used for CV parsing, ranking and generation. API key is always read from
              the root .env file.
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {AI_MODELS.find((m) => m.value === settings.openai_model)?.blurb}
            </p>
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700">Jobs to AI-rank per refresh</label>
            <input
              type="number"
              min={0}
              max={200}
              value={settings.ai_rank_top_n}
              onChange={(e) => update('ai_rank_top_n', Number(e.target.value))}
              className={`mt-1.5 ${inputClass}`}
            />
            <p className="mt-1 text-xs text-slate-500">
              Ranked in batches, best local scores first. 0 disables AI ranking.
            </p>
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700">Minimum local score to rank</label>
            <input
              type="number"
              min={0}
              max={100}
              value={settings.min_score_to_rank}
              onChange={(e) => update('min_score_to_rank', Number(e.target.value))}
              className={`mt-1.5 ${inputClass}`}
            />
            <p className="mt-1 text-xs text-slate-500">
              Stops tokens being spent on obviously irrelevant jobs.
            </p>
          </div>
        </div>

        <div>
          <label className="text-sm font-medium text-slate-700">Default augmentation level</label>
          <p className="mt-0.5 text-xs text-slate-500">
            How far generation may go beyond your profile. Overridable per job.
          </p>
          <div className="mt-2">
            <AugmentationPicker
              value={settings.default_augmentation}
              onChange={(v) => update('default_augmentation', v)}
            />
          </div>
        </div>
      </Card>
      </>
      )}
    </div>
  )
}
