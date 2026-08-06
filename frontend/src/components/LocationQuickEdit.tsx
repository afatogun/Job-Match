import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Card } from './ui'

interface Props {
  location: string
  onSave: (next: { location: string }) => Promise<void>
}

const inputClass =
  'rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none'

export function LocationQuickEdit({ location, onSave }: Props) {
  const [draftLocation, setDraftLocation] = useState(location)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Resync when the active profile changes underneath us.
  useEffect(() => {
    setDraftLocation(location)
  }, [location])

  const dirty = draftLocation !== location

  const save = async () => {
    setSaving(true)
    setMessage(null)
    setError(null)
    try {
      await onSave({ location: draftLocation })
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
