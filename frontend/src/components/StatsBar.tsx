import type { Stats } from '../types'

function Tile({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums tracking-tight text-slate-900">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-slate-400">{hint}</p>}
    </div>
  )
}

export function StatsBar({ stats }: { stats: Stats | null }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Tile label="Total discovered" value={stats?.total_jobs ?? 0} />
      <Tile label="New" value={stats?.new_jobs ?? 0} />
      <Tile label="Good matches" value={stats?.good_matches ?? 0} hint="Needs AI ranking" />
      <Tile label="Applications" value={stats?.generated_applications ?? 0} hint="Needs generation" />
    </div>
  )
}
