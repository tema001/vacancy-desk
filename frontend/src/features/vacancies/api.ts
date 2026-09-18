import type { VacanciesPage, VacancyParams } from './types'

export async function fetchVacancies(params: VacancyParams): Promise<VacanciesPage> {
  const response = await fetch('/api/vacancies', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
  })

  if (!response.ok) {
    throw new Error(`Could not load vacancies (${response.status})`)
  }

  return (await response.json()) as VacanciesPage
}
