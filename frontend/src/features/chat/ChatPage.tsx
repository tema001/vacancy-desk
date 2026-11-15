import { useQuery } from '@tanstack/react-query'
import { StateMessage } from '../../shared/StateMessage'
import { activeChatKey, fetchActiveChat } from './api'
import { ChatConversation } from './ChatConversation'
import { ChatHeading } from './ChatHeading'
import './chat.css'

export function ChatPage() {
  const chatQuery = useQuery({
    queryKey: activeChatKey,
    queryFn: fetchActiveChat,
  })

  return (
    <div className="app-shell chat-shell">
      <main className="chat-main">
        {chatQuery.data ? (
          <ChatConversation
            key={chatQuery.data.chat.id}
            chatId={chatQuery.data.chat.id}
            initialMessages={chatQuery.data.messages}
          />
        ) : chatQuery.isError ? (
          <>
            <ChatHeading />
            <StateMessage
              kind="error"
              title="Could not load chat"
              text={chatQuery.error.message}
              action={{
                label: 'Try again',
                onClick: () => void chatQuery.refetch(),
              }}
            />
          </>
        ) : (
          <>
            <ChatHeading />
            <StateMessage
              kind="loading"
              title="Loading chat"
              text="Fetching the conversation history."
            />
          </>
        )}
      </main>
    </div>
  )
}
