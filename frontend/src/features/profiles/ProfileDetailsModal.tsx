import { ProfileExtractDetails } from './ProfileExtractDetails'
import type { ExtractedProfile } from './types'

interface ProfileDetailsModalProps {
  name: string
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
        <h2 id="profile-modal-title">{profile?.name ?? name}</h2>
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
