import { useEffect, useRef } from 'react'
import { ChatEntry } from './ChatEntry'
import type { ChatMessage } from './types'

const BOTTOM_THRESHOLD_PX = 40

interface ChatMessageListProps {
  messages: ChatMessage[]
  isStreaming: boolean
}

export function ChatMessageList({ messages, isStreaming }: ChatMessageListProps) {
  const listRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)

  function handleScroll(): void {
    const list = listRef.current
    if (!list) return
    isAtBottomRef.current =
      list.scrollHeight - list.scrollTop - list.clientHeight < BOTTOM_THRESHOLD_PX
  }

  // Effect is needed: the new height is known only after React commits the new
  // tokens to the DOM. Scroll only if the user has not scrolled up to read history.
  useEffect(() => {
    const list = listRef.current
    if (list && isAtBottomRef.current) {
      list.scrollTop = list.scrollHeight
    }
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="chat-empty">
        <strong>Ask about vacancies or profiles</strong>
        <span>For example: “Show remote Python vacancies for my selected profile”.</span>
      </div>
    )
  }

  const lastIndex = messages.length - 1

  return (
    <div className="chat-messages" ref={listRef} onScroll={handleScroll}>
      <div className="chat-messages-inner">
        {messages.map((message, index) => (
          <ChatEntry
            key={message.id}
            message={message}
            isStreaming={isStreaming && index === lastIndex}
          />
        ))}
      </div>
    </div>
  )
}
