import { useEffect, useState } from 'react'

import { api } from '../api'
import { Card } from '../components/ui'
import type { SearchSettings, SourceInfo, WorkMode } from '../types'

const WORK_MODES: { value: WorkMode; label: string }[] = [
  { value: 'any', label: 'Any' },
  { value: 'remote', label: 'Remote' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'onsite', label: 'On-site' },
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
  const [settings, setSettings] = useState<SearchSettings | null>(null)
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [openai, setOpenai] = useState<{ configured: boolean; masked: string }>({
    configured: false,
    masked: '',
  })
  const [keyInput, setKeyInput] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.getSettings().then(setSettings).catch((e) => setError(String(e)))
    api.getSources().then(setSources).catch(() => setSources([]))
    api.getOpenAIKey().then(setOpenai).catch(() => undefined)
  }, [])

  const update = <K extends keyof SearchSettings>(key: K, value: SearchSettings[K]) =>
    setSettings((prev) => (prev ? { ...prev, [key]: value } : prev))

  const save = async () => {
    if (!settings) return
    setSaving(true)
    setMessage(null)
    setError(null)
    try {
      setSettings(await api.saveSettings(settings))
      setMessage('Settings saved.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save settings')
    } finally {
      setSaving(false)
    }
  }

  const saveKey = async () => {
    try {
      setOpenai(await api.saveOpenAIKey(keyInput))
      setKeyInput('')
      setMessage('OpenAI key saved to .env')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save key')
    }
  }

  if (!settings) {
    return <p className="py-16 text-center text-sm text-slate-400">{error ?? 'Loading…'}</p>
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-6 py-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Settings</h1>
        <p className="mt-0.5 text-sm text-slate-500">Controls what every job search looks for.</p>
      </div>

      <Card className="space-y-5 p-6">
        <h2 className="text-sm font-semibold text-slate-900">Job search</h2>

        <ListField
          label="Target job titles"
          hint="Each title runs as its own search against every enabled source."
          value={settings.target_titles}
          onChange={(v) => update('target_titles', v)}
        />
        <ListField
          label="Desired keywords"
          hint="Used for ranking once local scoring lands in step 10."
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
            Glassdoor, JobsIreland and LinkedIn are added in later steps.
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

      <Card className="space-y-3 p-6">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">OpenAI</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Stored in <code className="rounded bg-slate-100 px-1">.env</code>. Not used yet — AI ranking and
            document generation start at step 13.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder={openai.configured ? `Configured (${openai.masked})` : 'sk-…'}
            className={`flex-1 ${inputClass}`}
          />
          <button
            onClick={saveKey}
            disabled={!keyInput.trim()}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Save key
          </button>
        </div>
      </Card>
    </div>
  )
}
