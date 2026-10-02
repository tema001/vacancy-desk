import { useState, type KeyboardEvent } from 'react'
import { formatJobFamily } from './format'
import type { Profile, ProfileStatus } from './types'

interface ProfileCardProps {
  profile: Profile
  onSelect?: () => void
  onDelete?: () => void
}

const statusLabels: Record<Exclude<ProfileStatus, 'ready'>, string> = {
  pending: 'Pending',
  failed: 'Failed',
}

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'Europe/Kyiv',
})

function formatCreatedAt(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date)
}

export function ProfileCard({ profile, onSelect, onDelete }: ProfileCardProps) {
  const [confirming, setConfirming] = useState(false)
  const jobFamilies = profile.job_families ?? []

  function handleKeyDown(event: KeyboardEvent<HTMLElement>): void {
    if (!onSelect) {
      return
    }

    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect()
    }
  }

  function handleDeleteClick(): void {
    setConfirming(true)
  }

  function handleCancelDelete(): void {
    setConfirming(false)
  }

  function handleConfirmDelete(): void {
    setConfirming(false)
    onDelete?.()
  }

  return (
    <div className={confirming ? 'profile-card-wrap is-confirming' : 'profile-card-wrap'}>
      {onDelete ? (
        <button
          type="button"
          className="profile-card-delete"
          onClick={handleDeleteClick}
          aria-label={`Delete ${profile.name}`}
          aria-expanded={confirming}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 7h16M9 7V5h6v2m-8 0v12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V7M10 11v6M14 11v6" />
          </svg>
        </button>
      ) : null}

      {onDelete && confirming ? (
        <>
          <button
            type="button"
            className="profile-card-confirm-backdrop"
            onClick={handleCancelDelete}
            aria-label="Dismiss"
          />
          <div className="profile-card-confirm" role="dialog" aria-label="Are you sure?">
            <span>Are you sure?</span>
            <button type="button" className="profile-card-confirm-yes" onClick={handleConfirmDelete}>
              Yes
            </button>
            <button type="button" className="profile-card-confirm-no" onClick={handleCancelDelete}>
              No
            </button>
          </div>
        </>
      ) : null}

      <article
        className={onSelect ? 'profile-card profile-card-clickable' : 'profile-card'}
        onClick={onSelect}
        onKeyDown={onSelect ? handleKeyDown : undefined}
        role={onSelect ? 'button' : undefined}
        tabIndex={onSelect ? 0 : undefined}
      >
        <div className="profile-card-heading">
          <h2>{profile.name}</h2>
          {profile.status !== 'ready' ? (
            <span className={`profile-status profile-status-${profile.status}`}>
              {statusLabels[profile.status]}
            </span>
          ) : null}
        </div>

        <div className="profile-directions" aria-label="Job families">
          {jobFamilies.length > 0 ? (
            jobFamilies.map((family) => (
              <span className="category-tag" key={family}>
                {formatJobFamily(family)}
              </span>
            ))
          ) : (
            <span className="profile-directions-empty">empty</span>
          )}
        </div>

        <time className="profile-card-meta" dateTime={profile.date_created}>
          {formatCreatedAt(profile.date_created)}
        </time>
      </article>
    </div>
  )
}
