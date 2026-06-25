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
  const pinnedSourcesRef = useRef(pinnedSources)
  pinnedSourcesRef.current = pinnedSources

  const getPinnedIds = useCallback(() => {
    return pinnedSourcesRef.current.filter((ps) => ps.pinned).map((ps) => ps.chunk_id)
  }, [])

  const getExcludedIds = useCallback(() => {
    return pinnedSourcesRef.current.filter((ps) => ps.excluded).map((ps) => ps.chunk_id)
  }, [])

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
          // Merge new sources into pinnedSources (preserve existing pin/exclude states)
          setPinnedSources((prev) => {
            const prevMap = new Map(prev.map((ps) => [ps.chunk_id, ps]))
            const newEntries: PinnedSource[] = (data.sources || [])
              .filter((s: any) => s.chunk_id && !prevMap.has(s.chunk_id))
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
        getPinnedIds(),
        getExcludedIds(),
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
    // Merge loaded sources into pinnedSources — *preserve* existing pin/exclude states
    // The key insight: pinnedSources from earlier in the session should keep their
    // pinned/excluded flags. Only add *new* chunk_ids that haven't been seen.
    const newFromMessages: PinnedSource[] = []
    const allMsgsSources = msgs.flatMap((m) => m.sources || [])
    for (const s of allMsgsSources) {
      if (s.chunk_id && !newFromMessages.some((n) => n.chunk_id === s.chunk_id)) {
        newFromMessages.push({
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
    setPinnedSources((prev) => {
      const prevMap = new Map(prev.map((ps) => [ps.chunk_id, ps]))
      const trulyNew = newFromMessages.filter((n) => !prevMap.has(n.chunk_id))
      return trulyNew.length > 0 ? [...prev, ...trulyNew] : prev
    })
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
