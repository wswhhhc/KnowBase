import { useCallback, useEffect, useRef } from 'react'

import * as api from '@/shared/api'
import { type ViewType } from '@/app/navigation'
import { useConversations } from '@/hooks/useData'
import type { ChatMessage } from '@/hooks/useChat'
import type { Conversation, DebugInfo, PinStateResponse } from '@/shared/api'

type PersistedMessage = Awaited<ReturnType<typeof api.getMessages>>[number]

interface SidebarChatAdapter {
  loadMessages: (msgs: ChatMessage[], threadId?: string, pinState?: PinStateResponse) => void
  clearMessages: () => void
  threadId: string | null
  workspaceId: string
}

interface UseSidebarConversationsArgs {
  chat: SidebarChatAdapter
  convs: ReturnType<typeof useConversations>
  activeThreadId: string | null
  convRefreshKey: number
  activeWorkspaceId: string
  workspaceScopeKey: string
  onNavigate: (view: ViewType) => void
  onClose: () => void
  onLoadingMessages?: (loading: boolean) => void
  isMobile?: boolean
}

function mapPersistedMessage(message: PersistedMessage, conversationId: string): ChatMessage {
  const debugInfo = message.debug_info as DebugInfo | undefined
  const debugRecord = message.debug_info as Record<string, unknown> | undefined

  return {
    id: `${message.role}-${message.id}`,
    role: message.role,
    content: message.content,
    searchStrategy: typeof debugRecord?.search_strategy === 'string' ? debugRecord.search_strategy : undefined,
    webSearchEnabled: typeof debugRecord?.used_web_search === 'boolean' ? debugRecord.used_web_search : undefined,
    sources: message.sources,
    quality_reason: message.quality_reason,
    debugData: debugInfo,
    evidence_level: typeof debugRecord?.evidence_level === 'string' ? debugRecord.evidence_level : undefined,
    evidence_summary: typeof debugRecord?.evidence_summary === 'string' ? debugRecord.evidence_summary : undefined,
    outcome_category: typeof debugRecord?.outcome_category === 'string' ? debugRecord.outcome_category : undefined,
    usedRerank: typeof debugRecord?.used_rerank === 'boolean' ? debugRecord.used_rerank : undefined,
    convId: conversationId,
    assistantMsgId: message.role === 'assistant' ? message.id : undefined,
  }
}

export function useSidebarConversations({
  chat,
  convs,
  activeThreadId,
  convRefreshKey,
  activeWorkspaceId,
  workspaceScopeKey,
  onNavigate,
  onClose,
  onLoadingMessages,
  isMobile = false,
}: UseSidebarConversationsArgs) {
  const prevRefreshKeyRef = useRef(convRefreshKey)
  const autoLoadedConversationKeyRef = useRef<string | null>(null)

  const loadConversation = useCallback(async (conversation: Conversation, closeOnMobile = true) => {
    onNavigate('chat')
    onLoadingMessages?.(true)

    try {
      const [messages, pinState] = await Promise.all([
        api.getMessages(conversation.id, activeWorkspaceId),
        api.getConversationPinState(conversation.id, activeWorkspaceId),
      ])

      convs.setActiveId(conversation.id)
      chat.loadMessages(
        messages.map((message) => mapPersistedMessage(message, conversation.id)),
        conversation.thread_id,
        pinState,
      )

      if (closeOnMobile && isMobile) {
        onClose()
      }
    } catch (error) {
      console.error('切换对话失败:', error)
    } finally {
      onLoadingMessages?.(false)
    }
  }, [chat, convs, isMobile, onClose, onLoadingMessages, onNavigate])

  useEffect(() => {
    if (convRefreshKey !== prevRefreshKeyRef.current) {
      prevRefreshKeyRef.current = convRefreshKey
      convs.refresh().then((list) => {
        const matched = list.find((conversation) => conversation.thread_id === activeThreadId)
        if (matched) {
          convs.setActiveId(matched.id)
        }
      })
    }
  }, [activeThreadId, convRefreshKey, convs])

  useEffect(() => {
    if (convs.loading || chat.workspaceId !== activeWorkspaceId || !convs.activeId) return

    const activeConversation = convs.conversations.find((conversation) => conversation.id === convs.activeId)
    if (!activeConversation) return

    const conversationScopeKey = `${workspaceScopeKey}:${activeConversation.id}`
    if (chat.threadId === activeConversation.thread_id) {
      autoLoadedConversationKeyRef.current = conversationScopeKey
      return
    }
    if (autoLoadedConversationKeyRef.current === conversationScopeKey) return

    autoLoadedConversationKeyRef.current = conversationScopeKey
    void loadConversation(activeConversation, false)
  }, [
    activeWorkspaceId,
    chat.threadId,
    chat.workspaceId,
    convs.activeId,
    convs.conversations,
    convs.loading,
    loadConversation,
    workspaceScopeKey,
  ])

  const switchConversation = useCallback(async (conversation: Conversation) => {
    await loadConversation(conversation)
  }, [loadConversation])

  const handleNewConversation = useCallback(() => {
    onNavigate('chat')
    chat.clearMessages()
    convs.setActiveId(null)
    if (isMobile) {
      onClose()
    }
  }, [chat, convs, isMobile, onClose, onNavigate])

  const handleDelete = useCallback(async (conversationId: string) => {
    const isActiveConversation = convs.activeId === conversationId
    await convs.remove(conversationId)
    if (isActiveConversation) {
      chat.clearMessages()
    }
  }, [chat, convs])

  return {
    handleDelete,
    handleNewConversation,
    loadConversation,
    switchConversation,
  }
}
