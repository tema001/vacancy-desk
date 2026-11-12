import { englishLevelLabels, type EnglishLevel } from '../../shared/englishLevel'
import type { ProfileSkill, SkillDepth } from './types'

const jobFamilyLabels: Record<string, string> = {
  backend: 'Backend',
  frontend: 'Frontend',
  fullstack: 'Fullstack',
  data: 'Data',
  qa: 'QA',
  devops: 'DevOps',
  security: 'Security',
  embedded: 'Embedded',
  product: 'Product',
  delivery: 'Delivery',
  design: 'Design',
  support: 'Support',
  ai_ml: 'AI/ML',
  mobile: 'Mobile',
  other: 'Other',
}

const skillDepthOrder: SkillDepth[] = [4, 3, 2, 1]

export const skillDepthLabels: Record<SkillDepth, string> = {
  4: 'Expert',
  3: 'Advanced',
  2: 'Working',
  1: 'Familiarity',
}

export function formatJobFamily(value: string): string {
  return jobFamilyLabels[value] ?? value
}

export function formatSeniority(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function splitExperience(months: number): { years: string; months: string } {
  const years = Math.floor(months / 12)
  const yearLabel = years === 1 ? 'year' : 'years'
  const monthLabel = months === 1 ? 'month' : 'months'

  return {
    years: `${years} ${yearLabel}`,
    months: `(${months} ${monthLabel})`,
  }
}

export function formatEnglishLevel(level: EnglishLevel): string {
  return englishLevelLabels[level]
}

export function groupSkillsByDepth(skills: ProfileSkill[]): {
  depth: SkillDepth
  skills: ProfileSkill[]
}[] {
  return skillDepthOrder
    .map((depth) => ({
      depth,
      skills: skills.filter((skill) => skill.depth === depth),
    }))
    .filter((segment) => segment.skills.length > 0)
}
