import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchProfile, fetchProfiles, deleteProfile, isAbortError, isExtractedProfile } from './api'
import { ProfileCard } from './ProfileCard'
import { ProfileDetailsModal } from './ProfileDetailsModal'
import { ProfileFormModal } from './ProfileFormModal'
import type { ExtractedProfile, Profile } from './types'
import './profiles.css'

interface ProfileDetailsView {
  id: string
  name: string
  profile: ExtractedProfile | null
  errorMessage: string | null
}

export function ProfilesPage() {
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [details, setDetails] = useState<ProfileDetailsView | null>(null)
  const detailsAbortRef = useRef<AbortController | null>(null)
  const profilesQuery = useQuery({
    queryKey: ['profiles'],
    queryFn: fetchProfiles,
  })
  const profiles = profilesQuery.data?.rows ?? []

  function closeDetails(): void {
    detailsAbortRef.current?.abort()
    setDetails(null)
  }

  async function openProfile(profile: Profile): Promise<void> {
    if (profile.status !== 'ready') {
      return
    }

    detailsAbortRef.current?.abort()
    const controller = new AbortController()
    detailsAbortRef.current = controller
    setDetails({ id: profile.id, name: profile.name, profile: null, errorMessage: null })

    try {
      const data = await fetchProfile(profile.id, controller.signal)
      if (!isExtractedProfile(data)) {
        setDetails({
          id: profile.id,
          name: profile.name,
          profile: null,
          errorMessage: 'Profile is not ready',
        })
        return
      }

      setDetails({ id: data.id, name: data.name, profile: data, errorMessage: null })
    } catch (error) {
      if (isAbortError(error) || controller.signal.aborted) {
        return
      }

      setDetails({
        id: profile.id,
        name: profile.name,
        profile: null,
        errorMessage:
          error instanceof Error ? error.message : 'Could not load profile',
      })
    }
  }

  async function handleDelete(profile: Profile): Promise<void> {
    if (profile.status === 'pending') {
      return
    }

    await deleteProfile(profile.id)

    if (details?.id === profile.id) {
      closeDetails()
    }

    await profilesQuery.refetch()
  }

  return (
    <div className="app-shell">
      <main>
        <section className="page-heading profiles-heading">
          <h1>Profiles</h1>
          <div className="page-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => setIsCreateOpen(true)}
            >
              Add new
            </button>
            <button
              type="button"
              className="secondary-button refresh-button"
              onClick={() => void profilesQuery.refetch()}
              disabled={profilesQuery.isFetching}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20 11a8.1 8.1 0 0 0-14.9-4M4 4v4h4m-4 5a8.1 8.1 0 0 0 14.9 4M20 20v-4h-4" />
              </svg>
              Refresh
            </button>
          </div>
        </section>

        {profilesQuery.isPending ? (
          <div className="state-message" role="status">
            <span className="spinner large-spinner" aria-hidden="true" />
            <strong>Loading profiles</strong>
            <span>Fetching the latest results.</span>
          </div>
        ) : profilesQuery.isError && profiles.length === 0 ? (
          <div className="state-message error-state" role="alert">
            <span className="state-icon" aria-hidden="true">
              !
            </span>
            <strong>Could not load profiles</strong>
            <span>
              {profilesQuery.error instanceof Error
                ? profilesQuery.error.message
                : 'An unexpected error occurred.'}
            </span>
            <button
              type="button"
              className="secondary-button"
              onClick={() => void profilesQuery.refetch()}
            >
              Try again
            </button>
          </div>
        ) : profiles.length === 0 ? (
          <div className="state-message">
            <span className="state-icon empty-icon" aria-hidden="true">
              0
            </span>
            <strong>No profiles yet</strong>
            <span>Add a resume to create the first profile.</span>
          </div>
        ) : (
          <section className="profiles-grid" aria-label="Resume profiles">
            {profiles.map((profile) => (
              <ProfileCard
                profile={profile}
                key={profile.id}
                onSelect={
                  profile.status === 'ready'
                    ? () => void openProfile(profile)
                    : undefined
                }
                onDelete={
                  profile.status !== 'pending'
                    ? () => void handleDelete(profile)
                    : undefined
                }
              />
            ))}
          </section>
        )}

        {isCreateOpen ? (
          <ProfileFormModal
            onClose={() => setIsCreateOpen(false)}
            onCreated={() => void profilesQuery.refetch()}
          />
        ) : null}

        {details ? (
          <ProfileDetailsModal
            name={details.name}
            profile={details.profile}
            errorMessage={details.errorMessage}
            onClose={closeDetails}
          />
        ) : null}
      </main>
    </div>
  )
}
