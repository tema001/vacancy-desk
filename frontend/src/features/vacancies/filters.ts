import type { EnglishLevel } from './types'

export const categoryOptions = ['Python', 'ML/AI']
export const englishLevelOptions: { value: EnglishLevel; label: string }[] = [
  { value: 1, label: 'A1' },
  { value: 2, label: 'A2' },
  { value: 3, label: 'B1' },
  { value: 4, label: 'B2' },
  { value: 5, label: 'C1' },
  { value: 6, label: 'C2' },
]

const filtersPanelStorageKey = 'vacancy-desk:filters-panel-open'

export interface VacancyFilters {
  categories: string[]
  exp: number | null
  salaryMin: number | null
  engLvl: EnglishLevel | null
  activeOnly: boolean
}

export function parseOptionalInt(
  value: string,
  min: number,
  max: number,
): number | null | 'invalid' {
  if (value === '') {
    return null
  }

  if (!/^\d+$/.test(value)) {
    return 'invalid'
  }

  const parsed = Number(value)

  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    return 'invalid'
  }

  return parsed
}

export function parseEngLvl(value: string): EnglishLevel | null {
  if (value === '') {
    return null
  }

  const parsed = Number(value)

  if (
    parsed === 1 ||
    parsed === 2 ||
    parsed === 3 ||
    parsed === 4 ||
    parsed === 5 ||
    parsed === 6
  ) {
    return parsed
  }

  return null
}

export function stripNonDigits(value: string): string {
  return value.replace(/\D/g, '')
}

export function haveSameCategories(left: string[], right: string[]): boolean {
  return (
    left.length === right.length &&
    left.every((category) => right.includes(category))
  )
}

export function sameFilters(left: VacancyFilters, right: VacancyFilters): boolean {
  return (
    haveSameCategories(left.categories, right.categories) &&
    left.exp === right.exp &&
    left.salaryMin === right.salaryMin &&
    left.engLvl === right.engLvl &&
    left.activeOnly === right.activeOnly
  )
}

export function countActiveFilters(filters: VacancyFilters): number {
  return (
    Number(filters.categories.length > 0) +
    Number(filters.exp !== null) +
    Number(filters.salaryMin !== null) +
    Number(filters.engLvl !== null) +
    Number(filters.activeOnly)
  )
}

export function getInitialFilters(): VacancyFilters {
  const searchParams = new URLSearchParams(window.location.search)
  const categories = [
    ...new Set(
      searchParams
        .getAll('category')
        .filter((category) => categoryOptions.includes(category)),
    ),
  ]
  const exp = parseOptionalInt(searchParams.get('exp') ?? '', 1, 19)
  const salaryMin = parseOptionalInt(
    searchParams.get('salary_min') ?? '',
    1,
    99999,
  )

  return {
    categories,
    exp: exp === 'invalid' ? null : exp,
    salaryMin: salaryMin === 'invalid' ? null : salaryMin,
    engLvl: parseEngLvl(searchParams.get('eng_lvl') ?? ''),
    activeOnly: searchParams.get('active_only') === '1',
  }
}

export function saveFiltersToSearch(filters: VacancyFilters): void {
  const url = new URL(window.location.href)

  url.searchParams.delete('category')
  filters.categories.forEach((category) => {
    url.searchParams.append('category', category)
  })

  if (filters.exp === null) {
    url.searchParams.delete('exp')
  } else {
    url.searchParams.set('exp', String(filters.exp))
  }

  if (filters.salaryMin === null) {
    url.searchParams.delete('salary_min')
  } else {
    url.searchParams.set('salary_min', String(filters.salaryMin))
  }

  if (filters.engLvl === null) {
    url.searchParams.delete('eng_lvl')
  } else {
    url.searchParams.set('eng_lvl', String(filters.engLvl))
  }

  if (filters.activeOnly) {
    url.searchParams.set('active_only', '1')
  } else {
    url.searchParams.delete('active_only')
  }

  window.history.replaceState(window.history.state, '', url)
}

export function getInitialFiltersPanelState(): boolean {
  try {
    return localStorage.getItem(filtersPanelStorageKey) === 'true'
  } catch {
    return false
  }
}

export function saveFiltersPanelState(isOpen: boolean): void {
  try {
    localStorage.setItem(filtersPanelStorageKey, String(isOpen))
  } catch {
    // The interface still works when browser storage is unavailable.
  }
}
