import { ProfileExtractDetails } from './ProfileExtractDetails'
import type { ExtractedProfile } from './types'

interface ProfileDetailsModalProps {
  name: string
  isSelected: boolean
  profile: ExtractedProfile | null
  errorMessage: string | null
  onClose: () => void
}

function showDialog(dialog: HTMLDialogElement | null): void {
  if (dialog && !dialog.open) {
    dialog.showModal()
  }
}

export function ProfileDetailsModal({
  name,
  isSelected,
  profile,
  errorMessage,
  onClose,
}: ProfileDetailsModalProps) {
  return (
    <dialog
      ref={showDialog}
      className="profile-modal"
      aria-labelledby="profile-modal-title"
      onCancel={onClose}
    >
      <div className="profile-modal-heading">
        <div className="profile-modal-title">
          <h2 id="profile-modal-title">{profile?.name ?? name}</h2>
          {isSelected ? (
            <span className="profile-modal-selected" aria-label="Selected">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 2.8 14.07 9.16 20.75 9.16 15.34 13.06 17.41 19.43 12 15.51 6.59 19.43 8.66 13.06 3.25 9.16 9.93 9.16Z" />
              </svg>
            </span>
          ) : null}
        </div>
        <button
          type="button"
          className="profile-modal-close"
          onClick={onClose}
          aria-label="Close profile dialog"
        >
          ×
        </button>
      </div>

      {errorMessage ? (
        <div className="profile-extract-status error-state" role="alert">
          <strong>Could not load profile</strong>
          <span>{errorMessage}</span>
          <button type="button" className="primary-button" onClick={onClose}>
            Close
          </button>
        </div>
      ) : null}

      {!errorMessage && !profile ? (
        <div className="profile-extract-status" role="status">
          <span className="spinner large-spinner" aria-hidden="true" />
          <strong>Loading profile</strong>
        </div>
      ) : null}

      {profile ? (
        <div className="profile-extract">
          <ProfileExtractDetails profile={profile} />
          <div className="profile-form-actions">
            <button type="button" className="primary-button" onClick={onClose}>
              Done
            </button>
          </div>
        </div>
      ) : null}
    </dialog>
  )
}
