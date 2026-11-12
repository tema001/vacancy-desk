import { fetchJson, fetchOk, jsonInit, toResponseError } from '../../shared/api'
import type {
  ProfileCreateResult,
  ProfileListResponse,
  ProfileResponse,
} from './types'

export const profilesKey = ['profiles'] as const

export function profileKey(profileId: string | null): readonly [string, string | null] {
  return ['profile', profileId]
}

export function fetchProfiles(): Promise<ProfileListResponse> {
  return fetchJson<ProfileListResponse>(
    '/api/profiles',
    undefined,
    'Could not load profiles',
  )
}

export async function createProfile(
  input: { text: string; name: string | null },
): Promise<ProfileCreateResult> {
  const response = await fetch(
    '/api/profiles',
    jsonInit('POST', {
      text: input.text,
      ...(input.name ? { name: input.name } : {}),
    }),
  )

  if (response.status === 409) {
    throw new Error(
      'Another profile is still being processed. Wait until it finishes and try again.',
    )
  }

  if (!response.ok) {
    throw await toResponseError(response, 'Could not create profile')
  }

  return (await response.json()) as ProfileCreateResult
}

export function deleteProfile(profileId: string): Promise<void> {
  return fetchOk(
    `/api/profiles/${profileId}`,
    { method: 'DELETE' },
    'Could not delete profile',
  )
}

export function setProfileSelected(
  profileId: string,
  isSelected: boolean,
): Promise<void> {
  return fetchOk(
    `/api/profiles/${profileId}`,
    jsonInit('PATCH', { is_selected: isSelected }),
    'Could not update profile',
  )
}

export function fetchProfile(
  profileId: string,
  signal?: AbortSignal,
): Promise<ProfileResponse> {
  return fetchJson<ProfileResponse>(
    `/api/profiles/${profileId}`,
    { signal },
    'Could not load profile',
  )
}
