import type { Profile } from './types'

export const mockProfiles: Profile[] = [
  {
    id: 'profile-ready',
    name: 'Senior Python Engineer',
    directions: ['Python', 'Backend', 'Cloud'],
    createdAt: '2026-09-24T09:30:00.000Z',
    status: 'ready',
  },
  {
    id: 'profile-pending',
    name: 'ML Platform Engineer',
    directions: ['ML/AI', 'MLOps'],
    createdAt: '2026-09-28T14:15:00.000Z',
    status: 'pending',
  },
  {
    id: 'profile-failed',
    name: 'Data Engineer',
    directions: ['Data Engineering', 'Python'],
    createdAt: '2026-09-19T11:45:00.000Z',
    status: 'failed',
  },
]
