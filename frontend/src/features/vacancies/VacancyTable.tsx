import {
  formatDate,
  formatDateTitle,
  formatExperience,
  formatSalary,
  formatScore,
  sourceLabels,
} from './format'
import type { ScoredVacancy, Vacancy, VacancyOrder } from './types'

interface VacancyTableProps {
  rows: Array<Vacancy | ScoredVacancy>
  isScoreMode: boolean
  order: VacancyOrder
  onSort: () => void
}

interface StartedAtProps {
  value: string
}

function StartedAt({ value }: StartedAtProps) {
  const timestamp = Date.parse(value)
  const validDate = !Number.isNaN(timestamp)

  if (!validDate) {
    return <span title={formatDateTitle(value)}>{formatDate(value)}</span>
  }

  return (
    <time dateTime={value} title={formatDateTitle(value)}>
      {formatDate(value)}
    </time>
  )
}

export function VacancyTable({
  rows,
  isScoreMode,
  order,
  onSort,
}: VacancyTableProps) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Vacancy</th>
            <th>Source</th>
            <th>Category</th>
            <th>Salary</th>
            {isScoreMode ? (
              <th>Score</th>
            ) : (
              <th aria-sort={order === 1 ? 'ascending' : 'descending'}>
                <button type="button" className="sort-button" onClick={onSort}>
                  Date started
                  <span className="sort-indicator" aria-hidden="true">
                    {order === 1 ? '↑' : '↓'}
                  </span>
                </button>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((vacancy) => (
            <tr key={vacancy.id}>
              <td>
                <div className="vacancy-title-row">
                  {'status' in vacancy && vacancy.status === 3 ? (
                    <span
                      className="inactive-dot"
                      role="img"
                      aria-label="Inactive vacancy"
                      title="Inactive vacancy"
                    />
                  ) : null}
                  <div className="vacancy-title">{vacancy.title}</div>
                </div>
                <div className="vacancy-meta">
                  {vacancy.company ? <span>{vacancy.company}</span> : null}
                  {vacancy.location_str ? (
                    <span>{vacancy.location_str}</span>
                  ) : null}
                  {vacancy.experience !== null ? (
                    <span>{formatExperience(vacancy.experience)}</span>
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
                <span className="category-tag">{vacancy.category}</span>
              </td>
              <td className="salary">
                {formatSalary(
                  vacancy.salary_min,
                  vacancy.salary_max,
                  vacancy.salary_level,
                )}
              </td>
              <td>
                {'score' in vacancy ? (
                  <span className="score">{formatScore(vacancy.score)}</span>
                ) : (
                  <StartedAt value={vacancy.date_started} />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
