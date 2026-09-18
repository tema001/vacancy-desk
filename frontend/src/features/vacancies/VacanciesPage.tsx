import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchVacancies } from './api'
import type {
  VacancyOrder,
  VacancySource,
} from './types'

const categoryOptions = ['Python', 'ML/AI']
const pageSizes = [10, 25, 50]
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

export function VacanciesPage() {
  const [categories, setCategories] = useState<string[]>([])
  const [activeCategories, setActiveCategories] = useState<string[]>([])
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

  function setFiltersPanelOpen(isOpen: boolean): void {
    setIsFiltersPanelOpen(isOpen)
    saveFiltersPanelState(isOpen)
  }

  function applyCategories(nextCategories: string[]): void {
    const categoriesUnchanged = haveSameCategories(
      nextCategories,
      activeCategories,
    )
    setPage(1)

    if (categoriesUnchanged && page === 1) {
      void vacanciesQuery.refetch()
      return
    }

    if (!categoriesUnchanged) {
      setActiveCategories([...nextCategories])
    }
  }

  function toggleCategory(category: string): void {
    setCategories((currentCategories) =>
      currentCategories.includes(category)
        ? currentCategories.filter((item) => item !== category)
        : [...currentCategories, category],
    )
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    applyCategories(categories)
  }

  function handleReset(): void {
    setCategories([])
    applyCategories([])
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
              {activeCategories.length > 0 ? (
                <span className="filter-indicator" aria-hidden="true" />
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
              <span className="filter-label">Categories</span>
              <div className="filter-controls">
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
                <button
                  type="button"
                  className="text-button"
                  onClick={handleReset}
                >
                  Reset
                </button>
                <button type="submit" className="primary-button">
                  Apply filters
                </button>
              </div>
            </form>
          </section>
        ) : null}

        <section className="results-panel" aria-labelledby="results-heading">
          <div className="results-toolbar">
            <div>
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
                <span className="page-summary">
                  Rows {firstRow}–{pageStart + vacancies.length} of {totalCount}
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
