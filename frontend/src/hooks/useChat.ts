import { useState, useRef, useCallback } from 'react'
import { chatStream, type ChatStreamCallbacks, type Source, type DebugInfo } from '@/lib/api'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  quality_reason?: string
  evidence_level?: string
  evidence_summary?: string
  outcome_category?: string
  streaming?: boolean
  debugData?: DebugInfo
  /** Conversation ID, set on first SSE done event */
  convId?: string
  /** Message row ID from backend, set on SSE done */
  assistantMsgId?: number
}

export function useChat(onNewConversation?: (threadId: string) => void) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingNodes, setStreamingNodes] = useState<string[]>([])
  const abortRef = useRef<AbortController | null>(null)
  const threadIdRef = useRef<string | null>(null)

  const sendMessage = useCallback(
    (question: string, webSearchEnabled: boolean, searchStrategy: string) => {
      if (isStreaming) return

      setIsStreaming(true)
      setStreamingNodes([])

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: question,
      }
      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: '',
        streaming: true,
      }

      setMessages((prev) => [...prev, userMsg, assistantMsg])

      let accumulatedContent = ''
      let debugData: DebugInfo | undefined
      const msgId = assistantMsg.id

      const callbacks: ChatStreamCallbacks = {
        onNode(label, nodes) {
          setStreamingNodes([...nodes])
        },
        onToken(text) {
          accumulatedContent += text
          setMessages((prev) =>
            prev.map((m) => (m.id === msgId ? { ...m, content: accumulatedContent } : m)),
          )
        },
        onDebug(data) {
          debugData = data
        },
        onSources(data) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === msgId
                ? {
                    ...m,
                    sources: data.sources,
                    quality_reason: data.quality_reason,
                    evidence_level: data.evidence_level,
                    evidence_summary: data.evidence_summary,
                    outcome_category: data.outcome_category,
                  }
                : m,
            ),
          )
        },
        onDone(data) {
          const isNew = !threadIdRef.current
          threadIdRef.current = data.thread_id
          setMessages((prev) =>
            prev.map((m) =>
              m.id === msgId
                ? {
                    ...m,
                    content: data.answer,
                    sources: data.sources,
                    quality_reason: data.quality_reason,
                    evidence_level: data.evidence_level,
                    evidence_summary: data.evidence_summary,
                    outcome_category: data.outcome_category,
                    streaming: false,
                    debugData: debugData,
                    convId: data.conv_id,
                    assistantMsgId: data.assistant_msg_id,
                  }
                : m,
            ),
          )
          setIsStreaming(false)
          setStreamingNodes([])
          if (isNew) onNewConversation?.(data.thread_id)
        },
        onError(message) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === msgId
                ? { ...m, content: `错误：${message}`, streaming: false }
                : m,
            ),
          )
          setIsStreaming(false)
          setStreamingNodes([])
        },
      }

      abortRef.current = chatStream(
        question,
        threadIdRef.current,
        webSearchEnabled,
        searchStrategy,
        callbacks,
      )
    },
    [isStreaming],
  )

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsStreaming(false)
    setStreamingNodes([])
    setMessages((prev) =>
      prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
    )
  }, [])

  const clearMessages = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setMessages([])
    setIsStreaming(false)
    setStreamingNodes([])
    threadIdRef.current = null
  }, [])

  const loadMessages = useCallback((msgs: ChatMessage[], threadId?: string) => {
    setMessages(msgs)
    threadIdRef.current = threadId || null
  }, [])

  return {
    messages,
    isStreaming,
    streamingNodes,
    sendMessage,
    stopStreaming,
    clearMessages,
    loadMessages,
    threadId: threadIdRef.current,
  }
}
