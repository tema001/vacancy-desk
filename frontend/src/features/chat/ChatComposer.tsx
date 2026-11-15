import { useState, type FormEvent, type KeyboardEvent } from 'react'

interface ChatComposerProps {
  isStreaming: boolean
  onSend: (text: string) => void
}

export function ChatComposer({ isStreaming, onSend }: ChatComposerProps) {
  const [text, setText] = useState('')
  const canSend = !isStreaming && text.trim() !== ''

  function send(): void {
    if (!canSend) return
    onSend(text.trim())
    setText('')
  }

  function handleSubmit(event: FormEvent): void {
    event.preventDefault()
    send()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    // Enter sends, Shift+Enter adds a new line; skip while an IME is composing.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      send()
    }
  }

  return (
    <form className="chat-composer" onSubmit={handleSubmit}>
      <textarea
        className="chat-input"
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Message the assistant"
        aria-label="Message"
        rows={1}
        autoFocus
      />
      <button
        type="submit"
        className="chat-send-button"
        disabled={!canSend}
        aria-label={isStreaming ? 'Waiting for the reply' : 'Send message'}
      >
        {isStreaming ? (
          <span className="spinner" aria-hidden="true" />
        ) : (
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 19V5m-6 6 6-6 6 6" />
          </svg>
        )}
      </button>
    </form>
  )
}
