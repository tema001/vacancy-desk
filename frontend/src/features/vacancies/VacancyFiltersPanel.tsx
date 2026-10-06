import { useState, type FormEvent } from 'react'
import {
  categoryOptions,
  englishLevelOptions,
  haveSameCategories,
  parseEngLvl,
  parseOptionalInt,
  stripNonDigits,
  type VacancyFilters,
} from './filters'

interface VacancyFiltersPanelProps {
  applied: VacancyFilters
  disabled: boolean
  isOpen: boolean
  onApply: (filters: VacancyFilters) => void
}

export function VacancyFiltersPanel({
  applied,
  disabled,
  isOpen,
  onApply,
}: VacancyFiltersPanelProps) {
  const [categories, setCategories] = useState<string[]>([
    ...applied.categories,
  ])
  const [expDraft, setExpDraft] = useState(
    applied.exp === null ? '' : String(applied.exp),
  )
  const [salaryDraft, setSalaryDraft] = useState(
    applied.salaryMin === null ? '' : String(applied.salaryMin),
  )
  const [engLvlDraft, setEngLvlDraft] = useState(
    applied.engLvl === null ? '' : String(applied.engLvl),
  )
  const [activeOnlyDraft, setActiveOnlyDraft] = useState(applied.activeOnly)
  const [expInvalid, setExpInvalid] = useState(false)
  const [salaryInvalid, setSalaryInvalid] = useState(false)

  const parsedExpDraft = parseOptionalInt(expDraft, 1, 19)
  const parsedSalaryDraft = parseOptionalInt(salaryDraft, 1, 99999)
  const filtersChanged =
    !haveSameCategories(categories, applied.categories) ||
    parsedExpDraft === 'invalid' ||
    parsedExpDraft !== applied.exp ||
    parsedSalaryDraft === 'invalid' ||
    parsedSalaryDraft !== applied.salaryMin ||
    parseEngLvl(engLvlDraft) !== applied.engLvl ||
    activeOnlyDraft !== applied.activeOnly

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

    if (disabled) {
      return
    }

    const expResult = parseOptionalInt(expDraft, 1, 19)
    const salaryResult = parseOptionalInt(salaryDraft, 1, 99999)
    const nextExpInvalid = expResult === 'invalid'
    const nextSalaryInvalid = salaryResult === 'invalid'

    setExpInvalid(nextExpInvalid)
    setSalaryInvalid(nextSalaryInvalid)

    if (nextExpInvalid || nextSalaryInvalid) {
      return
    }

    onApply({
      categories,
      exp: expResult,
      salaryMin: salaryResult,
      engLvl: parseEngLvl(engLvlDraft),
      activeOnly: activeOnlyDraft,
    })
  }

  function handleReset(): void {
    if (disabled) {
      return
    }

    setCategories([])
    setExpDraft('')
    setSalaryDraft('')
    setEngLvlDraft('')
    setActiveOnlyDraft(false)
    setExpInvalid(false)
    setSalaryInvalid(false)
    onApply({
      categories: [],
      exp: null,
      salaryMin: null,
      engLvl: null,
      activeOnly: false,
    })
  }

  if (!isOpen) {
    return null
  }

  return (
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
              className={expInvalid ? 'filter-input is-invalid' : 'filter-input'}
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
                salaryInvalid ? 'filter-input is-invalid' : 'filter-input'
              }
              type="text"
              inputMode="numeric"
              autoComplete="off"
              value={salaryDraft}
              aria-invalid={salaryInvalid}
              onChange={(event) => handleSalaryChange(event.target.value)}
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
              onChange={(event) => setActiveOnlyDraft(event.target.checked)}
            />
            Active only
          </label>
          <div className="filter-actions">
            <button
              type="button"
              className="text-button"
              onClick={handleReset}
              disabled={disabled}
            >
              Reset
            </button>
            <button
              type="submit"
              className="primary-button"
              disabled={disabled || !filtersChanged}
            >
              Apply filters
            </button>
          </div>
        </div>
      </form>
    </section>
  )
}
