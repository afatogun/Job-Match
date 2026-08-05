import type { Job } from './types'

export function relativeDate(iso: string | null): string {
  if (!iso) return 'Date unknown'
  const posted = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(posted.getTime())) return iso
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const days = Math.round((today.getTime() - posted.getTime()) / 86_400_000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days} days ago`
  if (days < 14) return 'Last week'
  return posted.toLocaleDateString('en-IE', { day: 'numeric', month: 'short' })
}

const CURRENCY_SYMBOLS: Record<string, string> = { EUR: '€', GBP: '£', USD: '$' }

export function formatSalary(job: Job): string | null {
  const { salary_min: min, salary_max: max } = job
  if (!min && !max) return null
  const symbol = CURRENCY_SYMBOLS[job.salary_currency ?? ''] ?? `${job.salary_currency ?? ''} `
  const fmt = (n: number) => (n >= 1000 ? `${Math.round(n / 1000)}k` : String(Math.round(n)))
  const range = min && max ? `${fmt(min)}–${fmt(max)}` : fmt((min ?? max) as number)
  const interval = job.salary_interval ? ` / ${job.salary_interval}` : ''
  return `${symbol}${range}${interval}`
}

/** The genuine application page - direct link when the source gave us one. */
export function applyUrl(job: Job): string {
  return job.job_url_direct || job.job_url
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}
