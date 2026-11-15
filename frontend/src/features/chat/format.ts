import { formatDateTime } from '../../shared/format'

const relativeFormatter = new Intl.RelativeTimeFormat('en', { numeric: 'always' })

const RELATIVE_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
]

export function formatRelativeTime(unixSeconds: number, nowMs: number): string {
  const elapsed = nowMs / 1000 - unixSeconds
  for (const [unit, size] of RELATIVE_UNITS) {
    if (elapsed >= size) {
      return relativeFormatter.format(-Math.floor(elapsed / size), unit)
    }
  }
  return 'just now'
}

export function formatAbsoluteTime(unixSeconds: number): string {
  return formatDateTime(toIsoString(unixSeconds))
}

export function toIsoString(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toISOString()
}
