import type { VacancySource } from './types'

export const sourceLabels: Record<VacancySource, string> = {
  1: 'Djinni',
  2: 'DOU',
}

const numberFormatter = new Intl.NumberFormat('en-US')
const timeZone =
  Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Kyiv'

const dateFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone,
  year: 'numeric',
  month: 'short',
  day: 'numeric',
})
const timeFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone,
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})
const dayFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})
const dateTitleFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone,
  year: '2-digit',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

function getDateParts(
  formatter: Intl.DateTimeFormat,
  date: Date,
): Record<string, string> {
  return Object.fromEntries(
    formatter.formatToParts(date).map(({ type, value }) => [type, value]),
  )
}

function getCalendarDay(date: Date): number {
  const parts = getDateParts(dayFormatter, date)
  return Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
  )
}

export function formatDate(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value || '—'
  }

  const daysAgo = Math.round(
    (getCalendarDay(new Date()) - getCalendarDay(date)) / 86_400_000,
  )
  const time = timeFormatter.format(date)

  if (daysAgo === 0) {
    return `Today, ${time}`
  }

  if (daysAgo === 1) {
    return `Yesterday, ${time}`
  }

  return dateFormatter.format(date)
}

export function formatDateTitle(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value || '—'
  }

  const parts = getDateParts(dateTitleFormatter, date)
  return `${parts.hour}:${parts.minute}, ${parts.day}.${parts.month}.${parts.year}`
}

export function formatSalary(
  salaryMin: number | null,
  salaryMax: number | null,
  salaryLevel: string | null,
): string {
  if (salaryMin !== null && salaryMax !== null) {
    return `$${numberFormatter.format(salaryMin)} - ${numberFormatter.format(salaryMax)}`
  }

  return salaryLevel || '—'
}

export function formatScore(score: number): string {
  return score.toFixed(2)
}

export function formatExperience(experienceInMonths: number): string {
  const years = Math.floor(experienceInMonths / 12)

  if (years < 1) {
    return 'Less than 1 year experience'
  }

  return `${years} ${years === 1 ? 'year' : 'years'} experience`
}
