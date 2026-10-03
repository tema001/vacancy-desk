import { useState, type KeyboardEvent } from 'react'
import { formatJobFamily } from './format'
import type { Profile, ProfileStatus } from './types'

interface ProfileCardProps {
  profile: Profile
  onOpen?: () => void
  onDelete?: () => void
  onSetSelected?: (isSelected: boolean) => void
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

const STAR_PATH =
  'M12 2.8 14.07 9.16 20.75 9.16 15.34 13.06 17.41 19.43 12 15.51 6.59 19.43 8.66 13.06 3.25 9.16 9.93 9.16Z'

export function ProfileCard({
  profile,
  onOpen,
  onDelete,
  onSetSelected,
}: ProfileCardProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const jobFamilies = profile.job_families ?? []
  const canSelect = profile.status === 'ready' && onSetSelected
  const canDelete = Boolean(onDelete)
  const hasMenu = Boolean(canSelect || canDelete)
  const overlayOpen = menuOpen || confirming

  function closeOverlays(): void {
    setMenuOpen(false)
    setConfirming(false)
  }

  function handleOverlayKeyDown(event: KeyboardEvent<HTMLElement>): void {
    if (event.key === 'Escape' && overlayOpen) {
      event.preventDefault()
      closeOverlays()
    }
  }

  function handleCardKeyDown(event: KeyboardEvent<HTMLElement>): void {
    if (!onOpen) {
      return
    }

    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onOpen()
    }
  }

  function handleMenuToggle(): void {
    setConfirming(false)
    setMenuOpen((open) => !open)
  }

  function handleSelectClick(): void {
    closeOverlays()
    onSetSelected?.(!profile.is_selected)
  }

  function handleDeleteClick(): void {
    setMenuOpen(false)
    setConfirming(true)
  }

  function handleCancelDelete(): void {
    setConfirming(false)
  }

  function handleConfirmDelete(): void {
    setConfirming(false)
    onDelete?.()
  }

  const wrapClass = overlayOpen ? 'profile-card-wrap is-open' : 'profile-card-wrap'

  return (
    <div className={wrapClass} onKeyDown={handleOverlayKeyDown}>
      {hasMenu ? (
        <div className="profile-card-menu">
          <button
            type="button"
            className="profile-card-menu-trigger"
            onClick={handleMenuToggle}
            aria-label={`Actions for ${profile.name}`}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="6" cy="12" r="1.7" />
              <circle cx="12" cy="12" r="1.7" />
              <circle cx="18" cy="12" r="1.7" />
            </svg>
          </button>

          {menuOpen ? (
            <>
              <button
                type="button"
                className="profile-card-overlay"
                onClick={closeOverlays}
                aria-label="Dismiss"
              />
              <div className="profile-card-menu-list" role="menu">
                {canSelect ? (
                  <button
                    type="button"
                    className="profile-card-menu-item"
                    role="menuitem"
                    onClick={handleSelectClick}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d={STAR_PATH} />
                    </svg>
                    {profile.is_selected ? 'Unselect' : 'Select'}
                  </button>
                ) : null}
                {canDelete ? (
                  <button
                    type="button"
                    className="profile-card-menu-item is-danger"
                    role="menuitem"
                    onClick={handleDeleteClick}
                  >
                    Delete
                  </button>
                ) : null}
              </div>
            </>
          ) : null}
        </div>
      ) : null}

      {onDelete && confirming ? (
        <>
          <button
            type="button"
            className="profile-card-overlay"
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
        className={onOpen ? 'profile-card profile-card-clickable' : 'profile-card'}
        onClick={onOpen}
        onKeyDown={onOpen ? handleCardKeyDown : undefined}
        role={onOpen ? 'button' : undefined}
        tabIndex={onOpen ? 0 : undefined}
      >
        <div className="profile-card-heading">
          <h2>{profile.name}</h2>
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

        <div className="profile-card-footer">
          <time className="profile-card-meta" dateTime={profile.date_created}>
            {formatCreatedAt(profile.date_created)}
          </time>

          {profile.is_selected ? (
            <span className="profile-selected" aria-label="Selected">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d={STAR_PATH} />
              </svg>
            </span>
          ) : profile.status !== 'ready' ? (
            <span className={`profile-status profile-status-${profile.status}`}>
              {statusLabels[profile.status]}
            </span>
          ) : null}
        </div>
      </article>
    </div>
  )
}
