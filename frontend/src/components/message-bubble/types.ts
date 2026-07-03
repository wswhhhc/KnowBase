import type { Source } from '@/lib/api'
import type { ChatMessage, PinnedSource } from '@/hooks/useChat'
import type { WorkspaceSummary } from '@/types/workspace-summary'

export interface MessageBubbleProps {
  message: ChatMessage
  prevMessage?: ChatMessage
  threadId?: string | null
  onCitationClick?: (source: Source) => void
  onSendQuestion?: (q: string) => void
  onNavigateBrowser?: () => void
  pinnedSources?: PinnedSource[]
  onPinToggle?: (chunkId: string, action: 'pin' | 'unpin' | 'exclude' | 'unexclude') => void
  workspaceId?: string
  workspaceSummary?: WorkspaceSummary
}

export interface OutcomeGuidance {
  badge: string
  badgeClass: string
  title: string
  description: string
  primaryLabel?: string
  secondaryLabel?: string
  followUpPrompt?: string
}
