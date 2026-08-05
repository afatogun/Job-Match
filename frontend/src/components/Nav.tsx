import { NavLink } from 'react-router-dom'

const AREAS = [
  { to: '/jobs', label: 'Jobs' },
  { to: '/profile', label: 'Profile' },
  { to: '/applications', label: 'Applications' },
  { to: '/settings', label: 'Settings' },
]

export function Nav() {
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/85 backdrop-blur">
      <div className="mx-auto flex max-w-screen-2xl items-center gap-8 px-6 py-3">
        <div className="flex items-center gap-2">
          <div className="grid h-7 w-7 place-items-center rounded-lg bg-slate-900 text-xs font-bold text-white">
            JM
          </div>
          <span className="text-sm font-semibold tracking-tight text-slate-900">JobMatch Local</span>
        </div>
        <nav className="flex items-center gap-1">
          {AREAS.map((area) => (
            <NavLink
              key={area.to}
              to={area.to}
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
                }`
              }
            >
              {area.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
