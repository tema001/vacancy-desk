import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createProfile, fetchProfile, profileKey, profilesKey } from './api'
import { Modal } from '../../shared/Modal'
import { ProfileExtractDetails } from './ProfileExtractDetails'

interface ProfileFormModalProps {
  onClose: () => void
}

type FieldState = 'empty' | 'invalid' | 'valid'

// Backend limits after trimming: name 5+ (optional), resume text 10+ (required)
const NAME_MIN_LENGTH = 5
const RESUME_MIN_LENGTH = 10

function getFieldState(value: string, minLength: number): FieldState {
  if (value === '') {
    return 'empty'
  }

  return value.trim().length < minLength ? 'invalid' : 'valid'
}

interface FieldStatusProps {
  state: FieldState
  emptyLabel: string
  minLength: number
}

function FieldStatus({ state, emptyLabel, minLength }: FieldStatusProps) {
  if (state === 'empty') {
    return <small>{emptyLabel}</small>
  }

  if (state === 'invalid') {
    return <small className="profile-field-invalid">At least {minLength} characters</small>
  }

  return (
    <svg className="profile-field-valid" viewBox="0 0 24 24" aria-label="Valid">
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  )
}

export function ProfileFormModal({ onClose }: ProfileFormModalProps) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [resumeText, setResumeText] = useState('')
  const [createdId, setCreatedId] = useState<string | null>(null)
  const nameState = getFieldState(name, NAME_MIN_LENGTH)
  const resumeState = getFieldState(resumeText, RESUME_MIN_LENGTH)
  const canSubmit = resumeState === 'valid' && nameState !== 'invalid'

  const createMutation = useMutation({
    mutationFn: createProfile,
    onSuccess: async (created) => {
      setCreatedId(created.id)
      await queryClient.invalidateQueries({ queryKey: profilesKey })
    },
  })

  const profileQuery = useQuery({
    queryKey: profileKey(createdId),
    queryFn: async ({ signal }) => {
      const profile = await fetchProfile(createdId!, signal)
      if (profile.status !== 'pending') {
        // Extraction finished: polling stops, refresh the list to show the new status
        void queryClient.invalidateQueries({ queryKey: profilesKey })
      }
      return profile
    },
    enabled: createdId !== null,
    refetchInterval: (query) => (query.state.data?.status === 'pending' ? 1000 : false),
  })

  const extracted = profileQuery.data?.status === 'ready' ? profileQuery.data : null
  const failure = createMutation.isError
    ? { title: 'Could not extract profile', text: createMutation.error.message }
    : profileQuery.isError
      ? { title: 'Could not extract profile', text: profileQuery.error.message }
      : profileQuery.data?.status === 'failed'
        ? {
            title: 'Extract failed',
            text: 'The resume could not be processed. Try again with a different text.',
          }
        : null
  const isForm = !failure && !extracted && !createMutation.isPending && createdId === null

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()

    if (!canSubmit) {
      return
    }

    createMutation.mutate({ text: resumeText.trim(), name: nameState === 'valid' ? name.trim() : null })
  }

  return (
    <Modal
      title={extracted ? extracted.name : 'Add a new profile'}
      closeLabel="Close add profile dialog"
      onClose={onClose}
    >
      {!isForm && !failure && !extracted ? (
        <div className="profile-extract-status" role="status">
          <span className="spinner large-spinner" aria-hidden="true" />
          <strong>Extracting profile</strong>
          <span>This usually takes a few seconds.</span>
        </div>
      ) : null}

      {failure ? (
        <div className="profile-extract-status error-state" role="alert">
          <strong>{failure.title}</strong>
          <span>{failure.text}</span>
          <button type="button" className="primary-button" onClick={onClose}>
            Close
          </button>
        </div>
      ) : null}

      {extracted ? (
        <div className="profile-extract">
          <ProfileExtractDetails profile={extracted} />
          <div className="profile-form-actions">
            <button type="button" className="primary-button" onClick={onClose}>
              Done
            </button>
          </div>
        </div>
      ) : null}

      {isForm ? (
        <form className="profile-form" onSubmit={handleSubmit}>
          <label>
            <span>
              Profile name{' '}
              <FieldStatus state={nameState} emptyLabel="Optional" minLength={NAME_MIN_LENGTH} />
            </span>
            <input
              type="text"
              value={name}
              autoFocus
              aria-invalid={nameState === 'invalid'}
              maxLength={100}
              placeholder="e.g. Senior Python Engineer"
              onChange={(event) => setName(event.target.value)}
            />
          </label>

          <label className="profile-resume-field">
            <span>
              Resume text{' '}
              <FieldStatus state={resumeState} emptyLabel="Required" minLength={RESUME_MIN_LENGTH} />
            </span>
            <textarea
              value={resumeText}
              required
              aria-invalid={resumeState === 'invalid'}
              maxLength={5000}
              placeholder="Paste the full resume text here…"
              onChange={(event) => setResumeText(event.target.value)}
            />
          </label>

          <div className="profile-form-actions">
            <button type="button" className="secondary-button" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="primary-button" disabled={!canSubmit}>
              Upload
            </button>
          </div>
        </form>
      ) : null}
    </Modal>
  )
}
