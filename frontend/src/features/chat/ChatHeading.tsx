import type { ReactNode } from 'react'

interface ChatHeadingProps {
  children?: ReactNode
}

export function ChatHeading({ children }: ChatHeadingProps) {
  return (
    <section className="page-heading chat-heading">
      <div className="page-title">
        <h1>Chat</h1>
        <a className="page-title-link" href="/app">
          Vacancies
        </a>
        <a className="page-title-link" href="/app/profiles">
          Profiles
        </a>
      </div>
      <div className="page-actions">{children}</div>
    </section>
  )
}
