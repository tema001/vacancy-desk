import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchScoredVacancies, fetchVacancies } from './api'
import {
  countActiveFilters,
  getInitialFilters,
  getInitialFiltersPanelState,
  sameFilters,
  saveFiltersPanelState,
  saveFiltersToSearch,
  type VacancyFilters,
} from './filters'
import { VacancyFiltersPanel } from './VacancyFiltersPanel'
import { VacancyTable } from './VacancyTable'
import type { ScoredVacancy, Vacancy, VacancyOrder } from './types'

const pageSizes = [10, 25, 50]
const vacanciesPath = '/app'
const scorePath = '/app/score'

function isScorePath(): boolean {
  return window.location.pathname === scorePath
}

function saveScorePath(isScore: boolean): void {
  const url = new URL(window.location.href)
  url.pathname = isScore ? scorePath : vacanciesPath
  window.history.replaceState(window.history.state, '', url)
}

export function VacanciesPage() {
  const [applied, setApplied] = useState(getInitialFilters)
  const [isFiltersPanelOpen, setIsFiltersPanelOpen] = useState(
    getInitialFiltersPanelState,
  )
  const [order, setOrder] = useState<VacancyOrder>(2)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [isScoreMode, setIsScoreMode] = useState(isScorePath)

  const vacancyParams = {
    categories: applied.categories.length > 0 ? applied.categories : null,
    limit: pageSize,
    order,
    page,
    exp: applied.exp,
    salary_min: applied.salaryMin,
    eng_lvl: applied.engLvl,
    active_only: applied.activeOnly,
  }
  const vacanciesQuery = useQuery({
    queryKey: ['vacancies', vacancyParams],
    queryFn: () => fetchVacancies(vacancyParams),
    enabled: !isScoreMode,
  })
  const scoredQuery = useQuery({
    queryKey: ['vacancies', 'score'],
    queryFn: fetchScoredVacancies,
    enabled: isScoreMode,
  })
  const listQuery = isScoreMode ? scoredQuery : vacanciesQuery
  const rows: Array<Vacancy | ScoredVacancy> = isScoreMode
    ? (scoredQuery.data?.rows ?? [])
    : (vacanciesQuery.data?.rows ?? [])
  const totalCount = isScoreMode
    ? (scoredQuery.data?.total_count ?? 0)
    : (vacanciesQuery.data?.total_count ?? 0)
  const pageStart = (page - 1) * pageSize
  const firstRow = totalCount === 0 ? 0 : pageStart + 1
  const hasNextPage = vacanciesQuery.data?.has_next ?? false
  const scoredProfileName = scoredQuery.data?.profile.name ?? null
  const activeFilterCount = countActiveFilters(applied)

  function setFiltersPanelOpen(isOpen: boolean): void {
    setIsFiltersPanelOpen(isOpen)
    saveFiltersPanelState(isOpen)
  }

  function applyFilters(next: VacancyFilters): void {
    const filtersUnchanged = sameFilters(next, applied)
    setPage(1)
    saveFiltersToSearch(next)

    if (filtersUnchanged && page === 1) {
      void vacanciesQuery.refetch()
      return
    }

    if (!filtersUnchanged) {
      setApplied({
        ...next,
        categories: [...next.categories],
      })
    }
  }

  function handleScore(): void {
    const next = !isScoreMode
    saveScorePath(next)
    setIsScoreMode(next)
  }

  function handleRefresh(): void {
    void listQuery.refetch()
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
          <div className="page-title">
            <h1>Vacancies</h1>
            <a className="page-title-link" href="/app/profiles">
              Profiles
            </a>
          </div>
          <div className="page-actions">
            <button
              type="button"
              className={
                isScoreMode ? 'secondary-button is-active' : 'secondary-button'
              }
              onClick={handleScore}
              aria-pressed={isScoreMode}
            >
              Score vacancies
            </button>
            <button
              type="button"
              className="secondary-button filter-button"
              onClick={() => setFiltersPanelOpen(!isFiltersPanelOpen)}
              disabled={isScoreMode}
              aria-expanded={isFiltersPanelOpen && !isScoreMode}
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
              onClick={handleRefresh}
              disabled={listQuery.isFetching}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20 11a8.1 8.1 0 0 0-14.9-4M4 4v4h4m-4 5a8.1 8.1 0 0 0 14.9 4M20 20v-4h-4" />
              </svg>
              Refresh
            </button>
          </div>
        </section>

        <VacancyFiltersPanel
          applied={applied}
          disabled={isScoreMode}
          isOpen={isFiltersPanelOpen && !isScoreMode}
          onApply={applyFilters}
        />

        <section className="results-panel" aria-labelledby="results-heading">
          <div className="results-toolbar">
            <div className="results-heading">
              <div className="results-title-row">
                <h2 id="results-heading">Results</h2>
                <span className="count-badge">{totalCount}</span>
              </div>
              <p>
                {isScoreMode
                  ? scoredProfileName
                    ? `Profile: ${scoredProfileName}`
                    : 'Scored vacancies'
                  : applied.categories.length > 0
                    ? `Categories: ${applied.categories.join(', ')}`
                    : 'All categories'}
              </p>
            </div>
            <div className="results-actions">
              {listQuery.isFetching && !listQuery.isPending ? (
                <div className="query-status" aria-live="polite">
                  <span className="spinner" aria-hidden="true" />
                  Updating…
                </div>
              ) : listQuery.isError ? (
                <div className="query-status" aria-live="polite">
                  Update unavailable
                </div>
              ) : null}
              {isScoreMode ? null : (
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
                      Rows {firstRow}–{pageStart + rows.length} of {totalCount}
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
              )}
            </div>
          </div>

          {listQuery.isPending ? (
            <div className="state-message" role="status">
              <span className="spinner large-spinner" aria-hidden="true" />
              <strong>
                {isScoreMode ? 'Scoring vacancies' : 'Loading vacancies'}
              </strong>
              <span>Fetching the latest results.</span>
            </div>
          ) : listQuery.isError && rows.length === 0 ? (
            <div className="state-message error-state" role="alert">
              <span className="state-icon" aria-hidden="true">
                !
              </span>
              <strong>Could not load vacancies</strong>
              <span>
                {listQuery.error instanceof Error
                  ? listQuery.error.message
                  : 'An unexpected error occurred.'}
              </span>
              <button
                type="button"
                className="secondary-button"
                onClick={handleRefresh}
              >
                Try again
              </button>
            </div>
          ) : rows.length === 0 ? (
            <div className="state-message">
              <span className="state-icon empty-icon" aria-hidden="true">
                0
              </span>
              <strong>
                {!isScoreMode && page > 1
                  ? 'No vacancies on this page'
                  : 'No vacancies found'}
              </strong>
              <span>
                {isScoreMode
                  ? 'The selected profile has no scored vacancies.'
                  : page > 1
                    ? 'Return to the previous page.'
                    : 'Try another category or reset the filters.'}
              </span>
              {!isScoreMode && page > 1 ? (
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
              {listQuery.isError ? (
                <div className="inline-error" role="alert">
                  The update failed. Showing the most recently loaded results.
                  <button type="button" onClick={handleRefresh}>
                    Retry
                  </button>
                </div>
              ) : null}
              <VacancyTable
                rows={rows}
                isScoreMode={isScoreMode}
                order={order}
                onSort={handleSort}
              />
            </>
          )}
        </section>
      </main>
    </div>
  )
}
