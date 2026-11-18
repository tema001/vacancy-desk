export type ChatRole = 'human' | 'ai'

export interface ChatMessage {
  id: string
  role: ChatRole
  text: string
  created_at: number | null
}

export interface ActiveChat {
  id: string
  date_created: string
  date_updated: string
}

export interface ActiveChatResponse {
  chat: ActiveChat | null
  messages: ChatMessage[]
}

export interface ActiveChatWithChat {
  chat: ActiveChat
  messages: ChatMessage[]
}

export type ChatStreamEvent =
  | { event: 'token'; text: string }
  | { event: 'interrupt'; text: string }
  | { event: 'done'; awaiting_input: boolean; created_at: number }
  | { event: 'error'; text: string }
