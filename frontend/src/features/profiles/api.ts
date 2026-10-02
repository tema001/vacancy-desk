import type {
  ExtractedProfile,
  PendingProfile,
  ProfileCreateResult,
  ProfileListResponse,
  ProfileResponse,
} from './types'

const POLL_INTERVAL_MS = 1000
const POLL_TIMEOUT_MS = 30_000

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason ?? new DOMException('Aborted', 'AbortError'))
      return
    }

    const timeoutId = window.setTimeout(resolve, ms)
    signal?.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timeoutId)
        reject(signal.reason ?? new DOMException('Aborted', 'AbortError'))
      },
      { once: true },
    )
  })
}

export async function fetchProfiles(): Promise<ProfileListResponse> {
  const response = await fetch('/api/profiles')

  if (!response.ok) {
    throw new Error(`Could not load profiles (${response.status})`)
  }

  return (await response.json()) as ProfileListResponse
}

export async function createProfile(
  input: { text: string; name: string | null },
  signal?: AbortSignal,
): Promise<ProfileCreateResult> {
  const response = await fetch('/api/profiles', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      text: input.text,
      ...(input.name ? { name: input.name } : {}),
    }),
    signal,
  })

  if (response.status === 409) {
    const body = (await response.json()) as {
      detail?: { profile_id?: string }
    }
    if (body.detail?.profile_id) {
      return { id: body.detail.profile_id }
    }
  }

  if (!response.ok) {
    throw new Error(`Could not create profile (${response.status})`)
  }

  return (await response.json()) as ProfileCreateResult
}

export async function deleteProfile(profileId: string): Promise<void> {
  const response = await fetch(`/api/profiles/${profileId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error(`Could not delete profile (${response.status})`)
  }
}

export async function fetchProfile(
  profileId: string,
  signal?: AbortSignal,
): Promise<ProfileResponse> {
  const response = await fetch(`/api/profiles/${profileId}`, { signal })

  if (!response.ok) {
    throw new Error(`Could not load profile (${response.status})`)
  }

  return (await response.json()) as ProfileResponse
}

export async function waitForProfileExtract(
  profileId: string,
  signal?: AbortSignal,
): Promise<ExtractedProfile | PendingProfile> {
  const deadline = Date.now() + POLL_TIMEOUT_MS

  while (true) {
    const profile = await fetchProfile(profileId, signal)
    if (profile.status !== 'pending') {
      return profile
    }

    const remaining = deadline - Date.now()
    if (remaining <= 0) {
      throw new Error('Profile extract timed out')
    }

    await sleep(Math.min(POLL_INTERVAL_MS, remaining), signal)
  }
}

export function isExtractedProfile(
  profile: ProfileResponse,
): profile is ExtractedProfile {
  return profile.status === 'ready'
}
