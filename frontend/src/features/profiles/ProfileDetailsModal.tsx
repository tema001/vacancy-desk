import { useQuery } from '@tanstack/react-query'
import { fetchProfile, profileKey } from './api'
import { Modal } from '../../shared/Modal'
import { ProfileExtractDetails } from './ProfileExtractDetails'
import { STAR_PATH } from './icons'
import type { Profile } from './types'

interface ProfileDetailsModalProps {
  profile: Profile
  onClose: () => void
}

export function ProfileDetailsModal({ profile: listEntry, onClose }: ProfileDetailsModalProps) {
  const profileQuery = useQuery({
    queryKey: profileKey(listEntry.id),
    queryFn: ({ signal }) => fetchProfile(listEntry.id, signal),
  })
  const loaded = profileQuery.data?.status === 'ready' ? profileQuery.data : null
  const name = loaded?.name ?? listEntry.name
  const isSelected = loaded?.is_selected ?? listEntry.is_selected
  const errorMessage = profileQuery.isError
    ? profileQuery.error.message
    : profileQuery.data && !loaded
      ? 'Profile is not ready'
      : null

  return (
    <Modal
      title={name}
      titleExtra={
        isSelected ? (
          <span className="profile-modal-selected" aria-label="Selected">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d={STAR_PATH} />
            </svg>
          </span>
        ) : null
      }
      closeLabel="Close profile dialog"
      onClose={onClose}
    >
      {errorMessage ? (
        <div className="profile-extract-status error-state" role="alert">
          <strong>Could not load profile</strong>
          <span>{errorMessage}</span>
          <button type="button" className="primary-button" onClick={onClose}>
            Close
          </button>
        </div>
      ) : null}

      {!errorMessage && !loaded ? (
        <div className="profile-extract-status" role="status">
          <span className="spinner large-spinner" aria-hidden="true" />
          <strong>Loading profile</strong>
        </div>
      ) : null}

      {loaded ? (
        <div className="profile-extract">
          <ProfileExtractDetails profile={loaded} />
          <div className="profile-form-actions">
            <button type="button" className="primary-button" onClick={onClose}>
              Done
            </button>
          </div>
        </div>
      ) : null}
    </Modal>
  )
}
