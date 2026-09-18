export type VacancySource = 1 | 2
export type VacancyStatus = 1 | 2 | 3 | 4

export interface Vacancy {
  id: string
  source: VacancySource
  title: string
  company: string | null
  url: string
  category: string
  location_str: string | null
  salary_min: number | null
  salary_max: number | null
  salary_level: string | null
  experience: number | null
  status: VacancyStatus
  date_started: string
}

export type VacancyOrder = 1 | 2

export interface VacancyParams {
  categories: string[] | null
  limit: number
  order: VacancyOrder
  page: number
}

export interface VacanciesPage {
  total_count: number
  has_next: boolean
  rows: Vacancy[]
}
