import type { KeyboardEvent } from 'react'
import { formatDateTime } from '../../shared/format'
import { formatJobFamily } from './format'
import { ProfileCardMenu } from './ProfileCardMenu'
import { STAR_PATH } from './icons'
import type { Profile, ProfileStatus } from './types'

interface ProfileCardProps {
  profile: Profile
  isBusy: boolean
  onOpen: () => void
  onDelete: () => void
  onSetSelected: (isSelected: boolean) => void
}

const statusLabels: Record<Exclude<ProfileStatus, 'ready'>, string> = {
  pending: 'Pending',
  failed: 'Failed',
}


export function ProfileCard({
  profile,
  isBusy,
  onOpen,
  onDelete,
  onSetSelected,
}: ProfileCardProps) {
  const jobFamilies = profile.job_families ?? []
  const canOpen = profile.status === 'ready'

  function handleCardKeyDown(event: KeyboardEvent<HTMLElement>): void {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onOpen()
    }
  }

  return (
    <ProfileCardMenu
      profile={profile}
      isBusy={isBusy}
      onDelete={onDelete}
      onSetSelected={onSetSelected}
    >
      <article
        className={canOpen ? 'profile-card profile-card-clickable' : 'profile-card'}
        onClick={canOpen ? onOpen : undefined}
        onKeyDown={canOpen ? handleCardKeyDown : undefined}
        role={canOpen ? 'button' : undefined}
        tabIndex={canOpen ? 0 : undefined}
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
            {formatDateTime(profile.date_created)}
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
    </ProfileCardMenu>
  )
}
