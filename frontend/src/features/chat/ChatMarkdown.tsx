import { memo } from 'react'
import Markdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Module-level so every render passes the same references to Markdown.
const REMARK_PLUGINS = [remarkGfm]

const COMPONENTS: Components = {
  // Links lead to vacancy sites; open them in a new tab so the chat stays open.
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
}

interface ChatMarkdownProps {
  text: string
}

// Memoized: while a reply streams, only the last message gets new text,
// so the history is not re-parsed on every token.
export const ChatMarkdown = memo(function ChatMarkdown({ text }: ChatMarkdownProps) {
  return (
    <Markdown remarkPlugins={REMARK_PLUGINS} components={COMPONENTS}>
      {text}
    </Markdown>
  )
})
