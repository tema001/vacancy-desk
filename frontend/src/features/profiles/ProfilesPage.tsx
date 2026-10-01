import { useState } from 'react'
import { mockProfiles } from './mockProfiles'
import { ProfileCard } from './ProfileCard'
import { ProfileFormModal } from './ProfileFormModal'
import './profiles.css'

export function ProfilesPage() {
  const [isModalOpen, setIsModalOpen] = useState(false)

  return (
    <div className="app-shell">
      <main>
        <section className="page-heading">
          <h1>Profiles</h1>
          <button
            type="button"
            className="primary-button"
            onClick={() => setIsModalOpen(true)}
          >
            Add new
          </button>
        </section>

        <section className="profiles-grid" aria-label="Resume profiles">
          {mockProfiles.map((profile) => (
            <ProfileCard profile={profile} key={profile.id} />
          ))}
        </section>

        {isModalOpen ? (
          <ProfileFormModal onClose={() => setIsModalOpen(false)} />
        ) : null}
      </main>
    </div>
  )
}
