import type { ScoredVacancies, VacanciesPage, VacancyParams } from './types'

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

export async function fetchScoredVacancies(): Promise<ScoredVacancies> {
  const response = await fetch('/api/vacancies/score', {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(
      (await readErrorDetail(response)) ??
        `Could not load scored vacancies (${response.status})`,
    )
  }

  return (await response.json()) as ScoredVacancies
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    return typeof body.detail === 'string' ? body.detail : null
  } catch {
    return null
  }
}
