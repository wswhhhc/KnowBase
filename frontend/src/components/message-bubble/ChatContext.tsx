import type { PropsWithChildren } from 'react'
import { createContext, useContext } from 'react'
import type { Source } from '@/lib/api'
import type { PinnedSource } from '@/hooks/useChat'

interface ChatContextValue {
  onCitationClick?: (source: Source) => void
  onSendQuestion?: (question: string) => void
  onNavigateBrowser?: () => void
  pinnedSources?: PinnedSource[]
  onPinToggle?: (chunkId: string, action: 'pin' | 'unpin' | 'exclude' | 'unexclude') => void
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function ChatContextProvider({
  value,
  children,
}: PropsWithChildren<{ value: ChatContextValue }>) {
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

export function useChatContext() {
  return useContext(ChatContext) ?? {}
}
