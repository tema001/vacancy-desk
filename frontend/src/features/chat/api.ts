import { fetchJson, jsonInit, toResponseError } from '../../shared/api'
import type { ActiveChatResponse, ActiveChatWithChat, ChatStreamEvent } from './types'

export const activeChatKey = ['chat', 'active'] as const

// Soft-deletes the current chat on the backend and returns the new empty one.
export function createChat(): Promise<ActiveChatResponse> {
  return fetchJson<ActiveChatResponse>(
    '/api/chats/new',
    jsonInit('POST'),
    'Could not start a new chat',
  )
}

// Always resolves with a chat: creates one when the user has none yet.
export async function fetchActiveChat(): Promise<ActiveChatWithChat> {
  const active = await fetchJson<ActiveChatResponse>(
    '/api/chats/active',
    undefined,
    'Could not load chat',
  )
  const { chat, messages } = active.chat ? active : await createChat()
  if (!chat) {
    throw new Error('Could not load chat')
  }
  return { chat, messages }
}

function parseStreamEvent(block: string): ChatStreamEvent | null {
  let name = ''
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) {
      name = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      data = line.slice('data:'.length).trim()
    }
  }
  if (name !== 'token' && name !== 'interrupt' && name !== 'done' && name !== 'error') {
    return null
  }
  return { event: name, ...JSON.parse(data) } as ChatStreamEvent
}

export async function* streamChatMessage(
  chatId: string,
  text: string,
  signal: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  // Aborting the signal closes the connection; the backend then cancels the graph run.
  const response = await fetch(`/api/chats/${chatId}/messages/stream`, {
    ...jsonInit('POST', { text }),
    signal,
  })
  if (!response.ok) {
    throw await toResponseError(response, 'Could not send message')
  }
  if (!response.body) {
    throw new Error('Could not send message')
  }

  // getReader() instead of `for await` over the stream: Safari can't iterate streams.
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) {
      return
    }
    buffer += value
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const event = parseStreamEvent(block)
      if (event) {
        yield event
      }
    }
  }
}
