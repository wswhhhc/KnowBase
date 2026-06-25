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
  /** The original question text that produced this answer (for reroll) */
  originalQuestion?: string
  /** Feedback category restored from backend */
  feedbackCategory?: string
}

export interface PinnedSource {
  chunk_id: string
  source: string
  content: string
  pinned: boolean
  excluded: boolean
  score: number
  index: number
}

export function useChat(onNewConversation?: (threadId: string) => void) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingNodes, setStreamingNodes] = useState<string[]>([])
  const [pinnedSources, setPinnedSources] = useState<PinnedSource[]>([])
  const abortRef = useRef<AbortController | null>(null)
  const threadIdRef = useRef<string | null>(null)

  const _finalizeStream = useCallback(() => {
    setIsStreaming(false)
    setStreamingNodes([])
  }, [])

  const sendMessage = useCallback(
    (question: string, webSearchEnabled: boolean, searchStrategy: string, extraSources?: Source[]) => {
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
        originalQuestion: question,
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
          // Merge new sources into pinnedSources
          setPinnedSources((prev) => {
            const prevIds = new Set(prev.map((ps) => ps.chunk_id))
            const newEntries: PinnedSource[] = (data.sources || [])
              .filter((s: any) => s.chunk_id && !prevIds.has(s.chunk_id))
              .map((s: any) => ({
                chunk_id: s.chunk_id,
                source: s.source || '',
                content: s.content || '',
                pinned: false,
                excluded: false,
                score: s.score ?? 0,
                index: s.index ?? 0,
              }))
            return newEntries.length > 0 ? [...prev, ...newEntries] : prev
          })
          _finalizeStream()
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
          _finalizeStream()
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
    _finalizeStream()
    setMessages((prev) =>
      prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
    )
  }, [_finalizeStream])

  const clearMessages = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setMessages([])
    setPinnedSources([])
    _finalizeStream()
    threadIdRef.current = null
  }, [_finalizeStream])

  const loadMessages = useCallback((msgs: ChatMessage[], threadId?: string) => {
    setMessages(msgs)
    // Restore pinned sources from loaded messages
    const allSources = msgs.flatMap((m) => m.sources || [])
    const seen = new Set<string>()
    const restored: PinnedSource[] = []
    for (const s of allSources) {
      if (s.chunk_id && !seen.has(s.chunk_id)) {
        seen.add(s.chunk_id)
        restored.push({
          chunk_id: s.chunk_id,
          source: s.source || '',
          content: s.content || '',
          pinned: false,
          excluded: false,
          score: s.score ?? 0,
          index: s.index ?? 0,
        })
      }
    }
    setPinnedSources(restored)
    threadIdRef.current = threadId || null
  }, [])

  return {
    messages,
    isStreaming,
    streamingNodes,
    pinnedSources,
    setPinnedSources,
    sendMessage,
    stopStreaming,
    clearMessages,
    loadMessages,
    threadId: threadIdRef.current,
  }
}
