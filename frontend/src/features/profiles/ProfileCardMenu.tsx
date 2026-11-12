import { useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import type { Profile } from './types'
import { STAR_PATH } from './icons'

interface ProfileCardMenuProps {
  profile: Profile
  isBusy: boolean
  onDelete: () => void
  onSetSelected: (isSelected: boolean) => void
  children: ReactNode
}


// Module-level so the ref callback is stable and focuses only when the element mounts
function focusOnMount(element: HTMLElement | null): void {
  element?.focus()
}

export function ProfileCardMenu({
  profile,
  isBusy,
  onDelete,
  onSetSelected,
  children,
}: ProfileCardMenuProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const canSelect = profile.status === 'ready'
  const canDelete = profile.status !== 'pending'
  const hasMenu = canSelect || canDelete
  const overlayOpen = menuOpen || confirming

  function closeOverlays(): void {
    setMenuOpen(false)
    setConfirming(false)
  }

  function closeOverlaysAndFocusTrigger(): void {
    closeOverlays()
    triggerRef.current?.focus()
  }

  function handleWrapKeyDown(event: KeyboardEvent<HTMLElement>): void {
    if (event.key === 'Escape' && overlayOpen) {
      event.preventDefault()
      closeOverlaysAndFocusTrigger()
    }
  }

  function handleMenuKeyDown(event: KeyboardEvent<HTMLElement>): void {
    const items = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)'),
    )
    if (items.length === 0) {
      return
    }

    const current = items.indexOf(document.activeElement as HTMLElement)
    let next: number
    if (event.key === 'ArrowDown') {
      next = (current + 1) % items.length
    } else if (event.key === 'ArrowUp') {
      next = (current - 1 + items.length) % items.length
    } else if (event.key === 'Home') {
      next = 0
    } else if (event.key === 'End') {
      next = items.length - 1
    } else {
      return
    }

    event.preventDefault()
    items[next].focus()
  }

  function handleMenuToggle(): void {
    setConfirming(false)
    setMenuOpen((open) => !open)
  }

  function handleSelectClick(): void {
    closeOverlaysAndFocusTrigger()
    onSetSelected(!profile.is_selected)
  }

  function handleDeleteClick(): void {
    setMenuOpen(false)
    setConfirming(true)
  }

  function handleConfirmDelete(): void {
    setConfirming(false)
    onDelete()
  }

  const wrapClass = overlayOpen ? 'profile-card-wrap is-open' : 'profile-card-wrap'

  return (
    <div className={wrapClass} onKeyDown={handleWrapKeyDown}>
      {hasMenu ? (
        <div className="profile-card-menu">
          <button
            ref={triggerRef}
            type="button"
            className="profile-card-menu-trigger"
            onClick={handleMenuToggle}
            disabled={isBusy}
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
                onClick={closeOverlaysAndFocusTrigger}
                aria-label="Dismiss"
              />
              <div className="profile-card-menu-list" role="menu" onKeyDown={handleMenuKeyDown}>
                {canSelect ? (
                  <button
                    ref={focusOnMount}
                    type="button"
                    className="profile-card-menu-item"
                    role="menuitem"
                    onClick={handleSelectClick}
                    disabled={isBusy}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d={STAR_PATH} />
                    </svg>
                    {profile.is_selected ? 'Unselect' : 'Select'}
                  </button>
                ) : null}
                {canDelete ? (
                  <button
                    ref={canSelect ? undefined : focusOnMount}
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

      {canDelete && confirming ? (
        <>
          <button
            type="button"
            className="profile-card-overlay"
            onClick={closeOverlaysAndFocusTrigger}
            aria-label="Dismiss"
          />
          <div className="profile-card-confirm" role="dialog" aria-label="Are you sure?">
            <span>Are you sure?</span>
            <button
              type="button"
              className="profile-card-confirm-yes"
              onClick={handleConfirmDelete}
              disabled={isBusy}
            >
              Yes
            </button>
            <button
              ref={focusOnMount}
              type="button"
              className="profile-card-confirm-no"
              onClick={closeOverlaysAndFocusTrigger}
            >
              No
            </button>
          </div>
        </>
      ) : null}

      {children}
    </div>
  )
}
