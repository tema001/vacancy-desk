export type ProfileStatus = 'pending' | 'ready' | 'failed'

export interface Profile {
  id: string
  name: string
  job_families: string[] | null
  status: ProfileStatus
  is_selected: boolean
  date_created: string
}

export interface ProfileListResponse {
  rows: Profile[]
}

export type EnglishLevel = 1 | 2 | 3 | 4 | 5 | 6
export type SkillDepth = 1 | 2 | 3 | 4

export interface ProfileSkill {
  skill_name: string
  depth: SkillDepth
}

export interface ProfileCreateResult {
  id: string
}

export interface PendingProfile {
  id: string
  status: 'pending' | 'failed'
}

export interface ExtractedProfile {
  id: string
  name: string
  text: string
  job_families: string[] | null
  experience: number | null
  english_level: EnglishLevel | null
  seniority: string | null
  status: 'ready'
  is_selected: boolean
  skills: ProfileSkill[]
}

export type ProfileResponse = PendingProfile | ExtractedProfile
