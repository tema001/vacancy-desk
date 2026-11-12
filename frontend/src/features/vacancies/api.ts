import { fetchJson, jsonInit } from '../../shared/api'
import type { ScoredVacancies, VacanciesPage, VacancyParams } from './types'

export function fetchVacancies(params: VacancyParams): Promise<VacanciesPage> {
  return fetchJson<VacanciesPage>(
    '/api/vacancies',
    jsonInit('POST', params),
    'Could not load vacancies',
  )
}

export function fetchScoredVacancies(): Promise<ScoredVacancies> {
  return fetchJson<ScoredVacancies>(
    '/api/vacancies/score',
    { method: 'POST' },
    'Could not load scored vacancies',
  )
}
