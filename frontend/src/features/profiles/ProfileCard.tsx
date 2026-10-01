import type { Profile, ProfileStatus } from './types'

interface ProfileCardProps {
  profile: Profile
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

export function ProfileCard({ profile }: ProfileCardProps) {
  return (
    <article className="profile-card">
      <div className="profile-card-heading">
        <h2>{profile.name}</h2>
        {profile.status !== 'ready' ? (
          <span className={`profile-status profile-status-${profile.status}`}>
            {statusLabels[profile.status]}
          </span>
        ) : null}
      </div>

      <div className="profile-directions" aria-label="Directions">
        {profile.directions.length > 0 ? (
          profile.directions.map((direction) => (
            <span className="category-tag" key={direction}>
              {direction}
            </span>
          ))
        ) : (
          <span className="profile-directions-empty">Directions pending</span>
        )}
      </div>

      <time className="profile-card-meta" dateTime={profile.createdAt}>
        {formatCreatedAt(profile.createdAt)}
      </time>
    </article>
  )
}
