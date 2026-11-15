import { useState } from 'react'
import { ChatMarkdown } from './ChatMarkdown'
import { formatAbsoluteTime, formatRelativeTime, toIsoString } from './format'
import type { ChatMessage } from './types'

interface ChatEntryProps {
  message: ChatMessage
  isStreaming: boolean
}

export function ChatEntry({ message, isStreaming }: ChatEntryProps) {
  // The time is visible only on hover/focus, so it is recalculated right then.
  const [now, setNow] = useState(Date.now)

  function refreshTime(): void {
    setNow(Date.now())
  }

  const isHuman = message.role === 'human'

  return (
    <div
      className={isHuman ? 'chat-entry is-human' : 'chat-entry is-ai'}
      onMouseEnter={refreshTime}
      onFocus={refreshTime}
    >
      {isHuman ? (
        <div className="chat-message is-human">{message.text}</div>
      ) : (
        <div className={isStreaming ? 'chat-message is-ai is-streaming' : 'chat-message is-ai'}>
          <ChatMarkdown text={message.text} />
        </div>
      )}
      {message.created_at !== null ? (
        <time
          className="chat-time"
          dateTime={toIsoString(message.created_at)}
          aria-label={formatAbsoluteTime(message.created_at)}
          data-full={formatAbsoluteTime(message.created_at)}
          tabIndex={0}
        >
          {formatRelativeTime(message.created_at, now)}
        </time>
      ) : null}
    </div>
  )
}
