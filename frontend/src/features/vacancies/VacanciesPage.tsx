import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchVacancies } from './api'
import type {
  EnglishLevel,
  VacancyOrder,
  VacancySource,
} from './types'

const categoryOptions = ['Python', 'ML/AI']
const pageSizes = [10, 25, 50]
const englishLevelOptions: { value: EnglishLevel; label: string }[] = [
  { value: 1, label: 'A1' },
  { value: 2, label: 'A2' },
  { value: 3, label: 'B1' },
  { value: 4, label: 'B2' },
  { value: 5, label: 'C1' },
  { value: 6, label: 'C2' },
]
const filtersPanelStorageKey = 'vacancy-desk:filters-panel-open'
const sourceLabels: Record<VacancySource, string> = {
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

function getInitialFiltersPanelState(): boolean {
  try {
    return localStorage.getItem(filtersPanelStorageKey) === 'true'
  } catch {
    return false
  }
}

function saveFiltersPanelState(isOpen: boolean): void {
  try {
    localStorage.setItem(filtersPanelStorageKey, String(isOpen))
  } catch {
    // The interface still works when browser storage is unavailable.
  }
}

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

function formatDate(value: string): string {
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

function formatDateTitle(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value || '—'
  }

  const parts = getDateParts(dateTitleFormatter, date)
  return `${parts.hour}:${parts.minute}, ${parts.day}.${parts.month}.${parts.year}`
}

function formatSalary(
  salaryMin: number | null,
  salaryMax: number | null,
  salaryLevel: string | null,
): string {
  if (salaryMin !== null && salaryMax !== null) {
    return `$${numberFormatter.format(salaryMin)} - ${numberFormatter.format(salaryMax)}`
  }

  return salaryLevel || '—'
}

function formatExperience(experienceInMonths: number): string {
  const years = Math.floor(experienceInMonths / 12)

  if (years < 1) {
    return 'Less than 1 year experience'
  }

  return `${years} ${years === 1 ? 'year' : 'years'} experience`
}

function haveSameCategories(left: string[], right: string[]): boolean {
  return (
    left.length === right.length &&
    left.every((category) => right.includes(category))
  )
}

function stripNonDigits(value: string): string {
  return value.replace(/\D/g, '')
}

function parseOptionalInt(
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

function parseEngLvl(value: string): EnglishLevel | null {
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

interface VacancyFilters {
  categories: string[]
  exp: number | null
  salaryMin: number | null
  engLvl: EnglishLevel | null
  activeOnly: boolean
}

function getInitialFilters(): VacancyFilters {
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

function saveFiltersToSearch(filters: VacancyFilters): void {
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

export function VacanciesPage() {
  const [initialFilters] = useState(getInitialFilters)
  const [categories, setCategories] = useState<string[]>([
    ...initialFilters.categories,
  ])
  const [activeCategories, setActiveCategories] = useState<string[]>([
    ...initialFilters.categories,
  ])
  const [expDraft, setExpDraft] = useState(
    initialFilters.exp === null ? '' : String(initialFilters.exp),
  )
  const [salaryDraft, setSalaryDraft] = useState(
    initialFilters.salaryMin === null ? '' : String(initialFilters.salaryMin),
  )
  const [engLvlDraft, setEngLvlDraft] = useState(
    initialFilters.engLvl === null ? '' : String(initialFilters.engLvl),
  )
  const [activeOnlyDraft, setActiveOnlyDraft] = useState(
    initialFilters.activeOnly,
  )
  const [activeExp, setActiveExp] = useState<number | null>(initialFilters.exp)
  const [activeSalaryMin, setActiveSalaryMin] = useState<number | null>(
    initialFilters.salaryMin,
  )
  const [activeEngLvl, setActiveEngLvl] = useState<EnglishLevel | null>(
    initialFilters.engLvl,
  )
  const [activeActiveOnly, setActiveActiveOnly] = useState(
    initialFilters.activeOnly,
  )
  const [expInvalid, setExpInvalid] = useState(false)
  const [salaryInvalid, setSalaryInvalid] = useState(false)
  const [isFiltersPanelOpen, setIsFiltersPanelOpen] = useState(
    getInitialFiltersPanelState,
  )
  const [order, setOrder] = useState<VacancyOrder>(2)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const vacancyParams = {
    categories: activeCategories.length > 0 ? activeCategories : null,
    limit: pageSize,
    order,
    page,
    exp: activeExp,
    salary_min: activeSalaryMin,
    eng_lvl: activeEngLvl,
    active_only: activeActiveOnly,
  }
  const vacanciesQuery = useQuery({
    queryKey: ['vacancies', vacancyParams],
    queryFn: () => fetchVacancies(vacancyParams),
  })

  const vacancies = vacanciesQuery.data?.rows ?? []
  const totalCount = vacanciesQuery.data?.total_count ?? 0
  const pageStart = (page - 1) * pageSize
  const firstRow = totalCount === 0 ? 0 : pageStart + 1
  const hasNextPage = vacanciesQuery.data?.has_next ?? false
  const activeFilterCount =
    Number(activeCategories.length > 0) +
    Number(activeExp !== null) +
    Number(activeSalaryMin !== null) +
    Number(activeEngLvl !== null) +
    Number(activeActiveOnly)
  const parsedExpDraft = parseOptionalInt(expDraft, 1, 19)
  const parsedSalaryDraft = parseOptionalInt(salaryDraft, 1, 99999)
  const filtersChanged =
    !haveSameCategories(categories, activeCategories) ||
    parsedExpDraft === 'invalid' ||
    parsedExpDraft !== activeExp ||
    parsedSalaryDraft === 'invalid' ||
    parsedSalaryDraft !== activeSalaryMin ||
    parseEngLvl(engLvlDraft) !== activeEngLvl ||
    activeOnlyDraft !== activeActiveOnly

  function setFiltersPanelOpen(isOpen: boolean): void {
    setIsFiltersPanelOpen(isOpen)
    saveFiltersPanelState(isOpen)
  }

  function applyFilters(next: VacancyFilters): void {
    const filtersUnchanged =
      haveSameCategories(next.categories, activeCategories) &&
      next.exp === activeExp &&
      next.salaryMin === activeSalaryMin &&
      next.engLvl === activeEngLvl &&
      next.activeOnly === activeActiveOnly
    setPage(1)
    saveFiltersToSearch(next)

    if (filtersUnchanged && page === 1) {
      void vacanciesQuery.refetch()
      return
    }

    if (!filtersUnchanged) {
      setActiveCategories([...next.categories])
      setActiveExp(next.exp)
      setActiveSalaryMin(next.salaryMin)
      setActiveEngLvl(next.engLvl)
      setActiveActiveOnly(next.activeOnly)
    }
  }

  function toggleCategory(category: string): void {
    setCategories((currentCategories) =>
      currentCategories.includes(category)
        ? currentCategories.filter((item) => item !== category)
        : [...currentCategories, category],
    )
  }

  function handleExpChange(value: string): void {
    const digits = stripNonDigits(value)
    setExpDraft(digits)

    if (parseOptionalInt(digits, 1, 19) !== 'invalid') {
      setExpInvalid(false)
    }
  }

  function handleSalaryChange(value: string): void {
    const digits = stripNonDigits(value)
    setSalaryDraft(digits)

    if (parseOptionalInt(digits, 1, 99999) !== 'invalid') {
      setSalaryInvalid(false)
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()

    const expResult = parseOptionalInt(expDraft, 1, 19)
    const salaryResult = parseOptionalInt(salaryDraft, 1, 99999)
    const nextExpInvalid = expResult === 'invalid'
    const nextSalaryInvalid = salaryResult === 'invalid'

    setExpInvalid(nextExpInvalid)
    setSalaryInvalid(nextSalaryInvalid)

    if (nextExpInvalid || nextSalaryInvalid) {
      return
    }

    applyFilters({
      categories,
      exp: expResult,
      salaryMin: salaryResult,
      engLvl: parseEngLvl(engLvlDraft),
      activeOnly: activeOnlyDraft,
    })
  }

  function handleReset(): void {
    setCategories([])
    setExpDraft('')
    setSalaryDraft('')
    setEngLvlDraft('')
    setActiveOnlyDraft(false)
    setExpInvalid(false)
    setSalaryInvalid(false)
    applyFilters({
      categories: [],
      exp: null,
      salaryMin: null,
      engLvl: null,
      activeOnly: false,
    })
  }

  function handleSort(): void {
    setPage(1)
    setOrder((currentOrder) => (currentOrder === 1 ? 2 : 1))
  }

  function handlePageSize(nextPageSize: number): void {
    setPageSize(nextPageSize)
    setPage(1)
  }

  return (
    <div className="app-shell">
      <main>
        <section className="page-heading">
          <h1>Vacancies</h1>
          <div className="page-actions">
            <button
              type="button"
              className="secondary-button filter-button"
              onClick={() => setFiltersPanelOpen(!isFiltersPanelOpen)}
              aria-expanded={isFiltersPanelOpen}
              aria-controls="filters-panel"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 6h16M7 12h10m-7 6h4" />
              </svg>
              Filters
              {activeFilterCount > 0 ? (
                <span
                  className="filter-indicator"
                  aria-label={`${activeFilterCount} active ${
                    activeFilterCount === 1 ? 'filter' : 'filters'
                  }`}
                >
                  {activeFilterCount}
                </span>
              ) : null}
            </button>
            <button
              type="button"
              className="secondary-button refresh-button"
              onClick={() => void vacanciesQuery.refetch()}
              disabled={vacanciesQuery.isFetching}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20 11a8.1 8.1 0 0 0-14.9-4M4 4v4h4m-4 5a8.1 8.1 0 0 0 14.9 4M20 20v-4h-4" />
              </svg>
              Refresh
            </button>
          </div>
        </section>

        {isFiltersPanelOpen ? (
          <section className="filter-panel" id="filters-panel">
            <form className="filter-form" onSubmit={handleSubmit}>
              <div className="filter-fields">
                <div className="filter-field filter-field-category">
                  <span className="filter-label">Categories</span>
                  <details className="category-select">
                    <summary>
                      {categories.length > 0
                        ? categories.join(', ')
                        : 'All categories'}
                    </summary>
                    <div className="category-options">
                      {categoryOptions.map((category) => (
                        <label key={category}>
                          <input
                            type="checkbox"
                            checked={categories.includes(category)}
                            onChange={() => toggleCategory(category)}
                          />
                          {category}
                        </label>
                      ))}
                    </div>
                  </details>
                </div>

                <label className="filter-field">
                  <span className="filter-label">Experience</span>
                  <input
                    className={
                      expInvalid ? 'filter-input is-invalid' : 'filter-input'
                    }
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    value={expDraft}
                    aria-invalid={expInvalid}
                    onChange={(event) => handleExpChange(event.target.value)}
                  />
                </label>
                <label className="filter-field">
                  <span className="filter-label">Min salary</span>
                  <input
                    className={
                      salaryInvalid
                        ? 'filter-input is-invalid'
                        : 'filter-input'
                    }
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    value={salaryDraft}
                    aria-invalid={salaryInvalid}
                    onChange={(event) =>
                      handleSalaryChange(event.target.value)
                    }
                  />
                </label>
                <label className="filter-field">
                  <span className="filter-label">English</span>
                  <select
                    className="filter-select"
                    value={engLvlDraft}
                    onChange={(event) => setEngLvlDraft(event.target.value)}
                  >
                    <option value="">Any</option>
                    {englishLevelOptions.map((level) => (
                      <option key={level.value} value={String(level.value)}>
                        {level.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="filter-checkbox">
                  <input
                    type="checkbox"
                    checked={activeOnlyDraft}
                    onChange={(event) =>
                      setActiveOnlyDraft(event.target.checked)
                    }
                  />
                  Active only
                </label>
                <div className="filter-actions">
                  <button
                    type="button"
                    className="text-button"
                    onClick={handleReset}
                  >
                    Reset
                  </button>
                  <button
                    type="submit"
                    className="primary-button"
                    disabled={!filtersChanged}
                  >
                    Apply filters
                  </button>
                </div>
              </div>
            </form>
          </section>
        ) : null}

        <section className="results-panel" aria-labelledby="results-heading">
          <div className="results-toolbar">
            <div className="results-heading">
              <div className="results-title-row">
                <h2 id="results-heading">Results</h2>
                <span className="count-badge">{totalCount}</span>
              </div>
              <p>
                {activeCategories.length > 0
                  ? `Categories: ${activeCategories.join(', ')}`
                  : 'All categories'}
              </p>
            </div>
            <div className="results-actions">
              {vacanciesQuery.isFetching && !vacanciesQuery.isPending ? (
                <div className="query-status" aria-live="polite">
                  <span className="spinner" aria-hidden="true" />
                  Updating…
                </div>
              ) : vacanciesQuery.isError ? (
                <div className="query-status" aria-live="polite">
                  Update unavailable
                </div>
              ) : null}
              <div className="pagination" aria-label="Pagination">
                <label>
                  Rows per page
                  <select
                    value={pageSize}
                    onChange={(event) =>
                      handlePageSize(Number(event.target.value))
                    }
                  >
                    {pageSizes.map((size) => (
                      <option key={size} value={size}>
                        {size}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="pagination-navigation">
                  <span className="page-summary">
                    Rows {firstRow}–{pageStart + vacancies.length} of{' '}
                    {totalCount}
                  </span>
                  <div className="page-controls">
                    <button
                      type="button"
                      className="pagination-button"
                      onClick={() => setPage(page - 1)}
                      disabled={page === 1 || vacanciesQuery.isFetching}
                      aria-label="Previous page"
                    >
                      ‹
                    </button>
                    <span>Page {page}</span>
                    <button
                      type="button"
                      className="pagination-button"
                      onClick={() => setPage(page + 1)}
                      disabled={!hasNextPage || vacanciesQuery.isFetching}
                      aria-label="Next page"
                    >
                      ›
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {vacanciesQuery.isPending ? (
            <div className="state-message" role="status">
              <span className="spinner large-spinner" aria-hidden="true" />
              <strong>Loading vacancies</strong>
              <span>Fetching the latest results.</span>
            </div>
          ) : vacanciesQuery.isError && vacancies.length === 0 ? (
            <div className="state-message error-state" role="alert">
              <span className="state-icon" aria-hidden="true">
                !
              </span>
              <strong>Could not load vacancies</strong>
              <span>
                {vacanciesQuery.error instanceof Error
                  ? vacanciesQuery.error.message
                  : 'An unexpected error occurred.'}
              </span>
              <button
                type="button"
                className="secondary-button"
                onClick={() => void vacanciesQuery.refetch()}
              >
                Try again
              </button>
            </div>
          ) : vacancies.length === 0 ? (
            <div className="state-message">
              <span className="state-icon empty-icon" aria-hidden="true">
                0
              </span>
              <strong>
                {page > 1 ? 'No vacancies on this page' : 'No vacancies found'}
              </strong>
              <span>
                {page > 1
                  ? 'Return to the previous page.'
                  : 'Try another category or reset the filters.'}
              </span>
              {page > 1 ? (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setPage(page - 1)}
                >
                  Previous page
                </button>
              ) : null}
            </div>
          ) : (
            <>
              {vacanciesQuery.isError ? (
                <div className="inline-error" role="alert">
                  The update failed. Showing the most recently loaded results.
                  <button
                    type="button"
                    onClick={() => void vacanciesQuery.refetch()}
                  >
                    Retry
                  </button>
                </div>
              ) : null}

              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Vacancy</th>
                      <th>Source</th>
                      <th>Category</th>
                      <th>Salary</th>
                      <th aria-sort={order === 1 ? 'ascending' : 'descending'}>
                        <button
                          type="button"
                          className="sort-button"
                          onClick={handleSort}
                        >
                          Date started
                          <span className="sort-indicator" aria-hidden="true">
                            {order === 1 ? '↑' : '↓'}
                          </span>
                        </button>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {vacancies.map((vacancy) => {
                      const timestamp = Date.parse(vacancy.date_started)
                      const validDate = !Number.isNaN(timestamp)

                      return (
                        <tr key={vacancy.id}>
                          <td>
                            <div className="vacancy-title-row">
                              {vacancy.status === 3 ? (
                                <span
                                  className="inactive-dot"
                                  role="img"
                                  aria-label="Inactive vacancy"
                                  title="Inactive vacancy"
                                />
                              ) : null}
                              <div className="vacancy-title">
                                {vacancy.title}
                              </div>
                            </div>
                            <div className="vacancy-meta">
                              {vacancy.company ? (
                                <span>{vacancy.company}</span>
                              ) : null}
                              {vacancy.location_str ? (
                                <span>{vacancy.location_str}</span>
                              ) : null}
                              {vacancy.experience !== null ? (
                                <span>
                                  {formatExperience(vacancy.experience)}
                                </span>
                              ) : null}
                            </div>
                          </td>
                          <td>
                            <a
                              className="vacancy-link"
                              href={vacancy.url}
                              target="_blank"
                              rel="noreferrer"
                              title={vacancy.url}
                            >
                              <span>{sourceLabels[vacancy.source]}</span>
                              <svg viewBox="0 0 24 24" aria-hidden="true">
                                <path d="M14 5h5v5m0-5-8 8M19 13v6H5V5h6" />
                              </svg>
                            </a>
                          </td>
                          <td>
                            <span className="category-tag">
                              {vacancy.category}
                            </span>
                          </td>
                          <td className="salary">
                            {formatSalary(
                              vacancy.salary_min,
                              vacancy.salary_max,
                              vacancy.salary_level,
                            )}
                          </td>
                          <td>
                            {validDate ? (
                              <time
                                dateTime={vacancy.date_started}
                                title={formatDateTitle(vacancy.date_started)}
                              >
                                {formatDate(vacancy.date_started)}
                              </time>
                            ) : (
                              <span
                                title={formatDateTitle(vacancy.date_started)}
                              >
                                {formatDate(vacancy.date_started)}
                              </span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  )
}
