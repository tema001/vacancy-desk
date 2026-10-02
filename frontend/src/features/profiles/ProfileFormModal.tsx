import { useRef, useState, type FormEvent } from 'react'
import {
  createProfile,
  isAbortError,
  isExtractedProfile,
  waitForProfileExtract,
} from './api'
import { ProfileExtractDetails } from './ProfileExtractDetails'
import type { ExtractedProfile } from './types'

interface ProfileFormModalProps {
  onClose: () => void
  onCreated: () => void
}

type ModalView = 'form' | 'loading' | 'result' | 'failed' | 'error'

export function ProfileFormModal({ onClose, onCreated }: ProfileFormModalProps) {
  const [name, setName] = useState('')
  const [resumeText, setResumeText] = useState('')
  const [view, setView] = useState<ModalView>('form')
  const [extracted, setExtracted] = useState<ExtractedProfile | null>(null)
  const [errorMessage, setErrorMessage] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const canSubmit = resumeText.trim().length >= 10

  function showDialog(dialog: HTMLDialogElement | null): void {
    if (dialog && !dialog.open) {
      dialog.showModal()
    }
  }

  function handleClose(): void {
    abortRef.current?.abort()
    onClose()
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()

    if (!canSubmit) {
      return
    }

    const trimmedName = name.trim()
    const controller = new AbortController()
    abortRef.current = controller
    setView('loading')
    setErrorMessage('')

    try {
      const created = await createProfile(
        {
          text: resumeText.trim(),
          name: trimmedName.length >= 5 ? trimmedName : null,
        },
        controller.signal,
      )
      onCreated()
      const profile = await waitForProfileExtract(created.id, controller.signal)

      if (isExtractedProfile(profile)) {
        setExtracted(profile)
        setView('result')
        onCreated()
        return
      }

      setView('failed')
      onCreated()
    } catch (error) {
      if (isAbortError(error) || controller.signal.aborted) {
        return
      }

      setErrorMessage(
        error instanceof Error ? error.message : 'Could not extract profile',
      )
      setView('error')
    }
  }

  return (
    <dialog
      ref={showDialog}
      className="profile-modal"
      aria-labelledby="profile-modal-title"
      onCancel={handleClose}
    >
      <div className="profile-modal-heading">
        <h2 id="profile-modal-title">
          {view === 'result' && extracted ? extracted.name : 'Add a new profile'}
        </h2>
        <button
          type="button"
          className="profile-modal-close"
          onClick={handleClose}
          aria-label="Close add profile dialog"
        >
          ×
        </button>
      </div>

      {view === 'loading' ? (
        <div className="profile-extract-status" role="status">
          <span className="spinner large-spinner" aria-hidden="true" />
          <strong>Extracting profile</strong>
          <span>This usually takes a few seconds.</span>
        </div>
      ) : null}

      {view === 'failed' ? (
        <div className="profile-extract-status error-state" role="alert">
          <strong>Extract failed</strong>
          <span>The resume could not be processed. Try again with a different text.</span>
          <button type="button" className="primary-button" onClick={handleClose}>
            Close
          </button>
        </div>
      ) : null}

      {view === 'error' ? (
        <div className="profile-extract-status error-state" role="alert">
          <strong>Could not extract profile</strong>
          <span>{errorMessage}</span>
          <button type="button" className="primary-button" onClick={handleClose}>
            Close
          </button>
        </div>
      ) : null}

      {view === 'result' && extracted ? (
        <div className="profile-extract">
          <ProfileExtractDetails profile={extracted} />
          <div className="profile-form-actions">
            <button type="button" className="primary-button" onClick={handleClose}>
              Done
            </button>
          </div>
        </div>
      ) : null}

      {view === 'form' ? (
        <form className="profile-form" onSubmit={(event) => void handleSubmit(event)}>
          <label>
            <span>
              Profile name <small>Optional</small>
            </span>
            <input
              type="text"
              value={name}
              autoFocus
              maxLength={100}
              placeholder="e.g. Senior Python Engineer"
              onChange={(event) => setName(event.target.value)}
            />
          </label>

          <label className="profile-resume-field">
            <span>Resume text</span>
            <textarea
              value={resumeText}
              required
              minLength={10}
              maxLength={5000}
              placeholder="Paste the full resume text here…"
              onChange={(event) => setResumeText(event.target.value)}
            />
          </label>

          <div className="profile-form-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={handleClose}
            >
              Cancel
            </button>
            <button type="submit" className="primary-button" disabled={!canSubmit}>
              Upload
            </button>
          </div>
        </form>
      ) : null}
    </dialog>
  )
}
