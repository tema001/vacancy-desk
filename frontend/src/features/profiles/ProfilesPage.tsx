import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchProfiles,
  deleteProfile,
  setProfileSelected,
  profileKey,
  profilesKey,
} from './api'
import { RefreshButton } from '../../shared/RefreshButton'
import { StateMessage } from '../../shared/StateMessage'
import { ProfileCard } from './ProfileCard'
import { ProfileDetailsModal } from './ProfileDetailsModal'
import { ProfileFormModal } from './ProfileFormModal'
import './profiles.css'

export function ProfilesPage() {
  const queryClient = useQueryClient()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [openedId, setOpenedId] = useState<string | null>(null)
  const profilesQuery = useQuery({
    queryKey: profilesKey,
    queryFn: fetchProfiles,
  })
  const profiles = profilesQuery.data?.rows ?? []
  const openedProfile = profiles.find((profile) => profile.id === openedId)

  const deleteMutation = useMutation({
    mutationFn: deleteProfile,
    onSuccess: async (_data, profileId) => {
      if (openedId === profileId) {
        setOpenedId(null)
      }
      queryClient.removeQueries({ queryKey: profileKey(profileId) })
      await queryClient.invalidateQueries({ queryKey: profilesKey })
    },
  })

  const selectMutation = useMutation({
    mutationFn: (input: { profileId: string; isSelected: boolean }) =>
      setProfileSelected(input.profileId, input.isSelected),
    onSuccess: async (_data, input) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profilesKey }),
        queryClient.invalidateQueries({ queryKey: profileKey(input.profileId) }),
      ])
    },
  })

  const isBusy = deleteMutation.isPending || selectMutation.isPending
  const actionError = deleteMutation.error ?? selectMutation.error

  function handleDelete(profileId: string): void {
    selectMutation.reset()
    deleteMutation.mutate(profileId)
  }

  function handleSetSelected(profileId: string, isSelected: boolean): void {
    deleteMutation.reset()
    selectMutation.mutate({ profileId, isSelected })
  }

  return (
    <div className="app-shell">
      <main>
        <section className="page-heading profiles-heading">
          <div className="page-title">
            <h1>Profiles</h1>
            <a className="page-title-link" href="/app">
              Vacancies
            </a>
          </div>
          <div className="page-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => setIsCreateOpen(true)}
            >
              Add new
            </button>
            <RefreshButton
              onClick={() => void profilesQuery.refetch()}
              disabled={profilesQuery.isFetching}
            />
          </div>
        </section>

        {actionError ? (
          <div className="inline-error" role="alert">
            {actionError.message}
          </div>
        ) : null}

        {profilesQuery.isPending ? (
          <StateMessage
            kind="loading"
            title="Loading profiles"
            text="Fetching the latest results."
          />
        ) : profilesQuery.isError && profiles.length === 0 ? (
          <StateMessage
            kind="error"
            title="Could not load profiles"
            text={
              profilesQuery.error instanceof Error
                ? profilesQuery.error.message
                : 'An unexpected error occurred.'
            }
            action={{
              label: 'Try again',
              onClick: () => void profilesQuery.refetch(),
            }}
          />
        ) : profiles.length === 0 ? (
          <StateMessage
            kind="empty"
            title="No profiles yet"
            text="Add a resume to create the first profile."
          />
        ) : (
          <section className="profiles-grid" aria-label="Resume profiles">
            {profiles.map((profile) => (
              <ProfileCard
                profile={profile}
                key={profile.id}
                isBusy={isBusy}
                onOpen={() => setOpenedId(profile.id)}
                onDelete={() => handleDelete(profile.id)}
                onSetSelected={(isSelected) =>
                  handleSetSelected(profile.id, isSelected)
                }
              />
            ))}
          </section>
        )}

        {isCreateOpen ? (
          <ProfileFormModal onClose={() => setIsCreateOpen(false)} />
        ) : null}

        {openedProfile ? (
          <ProfileDetailsModal
            profile={openedProfile}
            onClose={() => setOpenedId(null)}
          />
        ) : null}
      </main>
    </div>
  )
}
