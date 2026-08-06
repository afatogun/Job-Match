import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import type { CountryOption } from '../types'
import { Card } from './ui'

interface Props {
  country: string
  location: string
  countries: CountryOption[]
  onSave: (next: { country: string; location: string }) => Promise<void>
}

const inputClass =
  'rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none'

export function LocationQuickEdit({ country, location, countries, onSave }: Props) {
  const [draftCountry, setDraftCountry] = useState(country)
  const [draftLocation, setDraftLocation] = useState(location)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Resync when the active profile changes underneath us.
  useEffect(() => {
    setDraftCountry(country)
    setDraftLocation(location)
  }, [country, location])

  const dirty = draftCountry !== country || draftLocation !== location

  const save = async () => {
    setSaving(true)
    setMessage(null)
    setError(null)
    try {
      await onSave({ country: draftCountry, location: draftLocation })
      setMessage('Saved.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="flex flex-wrap items-end gap-3 p-4">
      <div className="min-w-[220px] flex-1">
        <label className="text-xs font-medium text-slate-700">Location</label>
        <input
          value={draftLocation}
          onChange={(e) => setDraftLocation(e.target.value)}
          className={`mt-1 w-full ${inputClass}`}
          placeholder="e.g. Belfast, Northern Ireland"
        />
      </div>
      <div className="min-w-[180px]">
        <label className="text-xs font-medium text-slate-700">Country</label>
        <select
          value={draftCountry}
          onChange={(e) => setDraftCountry(e.target.value)}
          className={`mt-1 w-full ${inputClass}`}
        >
          <option value="auto">Auto-detect from location</option>
          {countries.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </div>
      <button
        onClick={save}
        disabled={saving || !dirty}
        className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {saving ? 'Saving…' : 'Save'}
      </button>
      <Link
        to="/settings"
        className="text-xs font-medium text-slate-500 underline underline-offset-2 hover:text-slate-700"
      >
        More search settings →
      </Link>
      {message && <span className="text-xs text-emerald-600">{message}</span>}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </Card>
  )
}
