import { AUGMENTATION_LEVELS } from '../types'
import type { Augmentation } from '../types'

interface Props {
  value: Augmentation | undefined
  onChange: (next: Augmentation) => void
  compact?: boolean
}

/** Step 14 - how far generation may go beyond the profile. */
export function AugmentationPicker({ value, onChange, compact }: Props) {
  if (compact) {
    return (
      <select
        value={value ?? 'enhanced'}
        onChange={(e) => onChange(e.target.value as Augmentation)}
        className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-700 focus:border-slate-500 focus:outline-none"
      >
        {AUGMENTATION_LEVELS.map((l) => (
          <option key={l.value} value={l.value}>
            {l.label}
          </option>
        ))}
      </select>
    )
  }

  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {AUGMENTATION_LEVELS.map((level) => {
        const active = value === level.value
        return (
          <button
            key={level.value}
            type="button"
            onClick={() => onChange(level.value)}
            className={`rounded-lg border p-3 text-left transition ${
              active
                ? 'border-slate-900 bg-slate-900 text-white'
                : 'border-slate-200 bg-white hover:border-slate-400'
            }`}
          >
            <span className="block text-sm font-semibold">{level.label}</span>
            <span className={`mt-1 block text-xs ${active ? 'text-slate-300' : 'text-slate-500'}`}>
              {level.blurb}
            </span>
          </button>
        )
      })}
    </div>
  )
}
