import { useState, useRef, useCallback } from 'react'
import { chatStream, type ChatStreamCallbacks, type DebugInfo, type PinStateResponse } from '@/lib/api'
import { useChatMessages } from '@/hooks/chat/useChatMessages'
import { usePinnedSourcesState } from '@/hooks/chat/usePinnedSourcesState'
import type { ChatMessage, PinnedSource } from '@/hooks/chat/types'

export type { ChatMessage, PinnedSource } from '@/hooks/chat/types'

export function useChat(onNewConversation?: (threadId: string) => void) {
  const {
    visibleMessages,
    appendPendingExchange,
    updateAssistantContent,
    mergeAssistantMetadata,
    finalizeAssistantMessage,
    setAssistantError,
    stopStreamingMessages,
    clearMessages: clearConversationMessages,
    loadMessages: loadConversationMessages,
  } = useChatMessages()
  const {
    getPinnedSources,
    setCurrentPinnedSources,
    mergeSourcesForConversation,
    hydrateConversationPinnedSources,
  } = usePinnedSourcesState()
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingNodes, setStreamingNodes] = useState<string[]>([])
  const [workspaceId, setWorkspaceId] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const threadIdRef = useRef<string | null>(null)
  const rafRef = useRef<number | null>(null)

  const finalizeStream = useCallback(() => {
    setIsStreaming(false)
    setStreamingNodes([])
  }, [])

  const sendMessage = useCallback(
    (question: string, webSearchEnabled: boolean, searchStrategy: string) => {
      if (isStreaming) return

      setIsStreaming(true)
      setStreamingNodes([])

      const assistantId = `assistant-${Date.now()}`
      appendPendingExchange(question, assistantId)

      let accumulatedContent = ''
      let debugData: DebugInfo | undefined

      const callbacks: ChatStreamCallbacks = {
        onNode(_label, nodes) {
          setStreamingNodes([...nodes])
        },
        onToken(text) {
          accumulatedContent += text
          if (rafRef.current) cancelAnimationFrame(rafRef.current)
          rafRef.current = requestAnimationFrame(() => {
            updateAssistantContent(assistantId, accumulatedContent)
            rafRef.current = null
          })
        },
        onDebug(data) {
          debugData = data
        },
        onSources(data) {
          mergeAssistantMetadata(assistantId, data)
        },
        onDone(data) {
          const isNewConversation = !threadIdRef.current
          threadIdRef.current = data.thread_id

          finalizeAssistantMessage(assistantId, data, debugData)
          mergeSourcesForConversation(data.thread_id, data.sources || [])
          finalizeStream()

          if (isNewConversation) {
            onNewConversation?.(data.thread_id)
          }
        },
        onError(message) {
          setAssistantError(assistantId, message)
          finalizeStream()
        },
      }

      const currentPinnedSources = getPinnedSources(threadIdRef.current)
      const pinnedChunkIds = currentPinnedSources.filter((source) => source.pinned).map((source) => source.chunk_id)
      const excludedChunkIds = currentPinnedSources.filter((source) => source.excluded).map((source) => source.chunk_id)

      abortRef.current = chatStream(
        question,
        threadIdRef.current,
        webSearchEnabled,
        searchStrategy,
        callbacks,
        pinnedChunkIds,
        excludedChunkIds,
        workspaceId,
      )
    },
    [
      appendPendingExchange,
      finalizeAssistantMessage,
      finalizeStream,
      getPinnedSources,
      isStreaming,
      mergeAssistantMetadata,
      mergeSourcesForConversation,
      onNewConversation,
      setAssistantError,
      updateAssistantContent,
      workspaceId,
    ],
  )

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    finalizeStream()
    stopStreamingMessages()
  }, [finalizeStream, stopStreamingMessages])

  const clearMessages = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    clearConversationMessages()
    finalizeStream()
    threadIdRef.current = null
  }, [clearConversationMessages, finalizeStream])

  const loadMessages = useCallback((nextMessages: ChatMessage[], threadId?: string, pinState?: PinStateResponse) => {
    loadConversationMessages(nextMessages)
    threadIdRef.current = threadId || null
    if (threadId) {
      hydrateConversationPinnedSources(threadId, nextMessages, pinState)
    }
  }, [hydrateConversationPinnedSources, loadConversationMessages])

  return {
    messages: visibleMessages,
    isStreaming,
    streamingNodes,
    pinnedSources: getPinnedSources(threadIdRef.current),
    setPinnedSources: (updater: PinnedSource[] | ((previous: PinnedSource[]) => PinnedSource[])) =>
      setCurrentPinnedSources(threadIdRef.current, updater),
    workspaceId,
    setWorkspaceId,
    sendMessage,
    stopStreaming,
    clearMessages,
    loadMessages,
    threadId: threadIdRef.current,
  }
}
