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
  convId?: string
  assistantMsgId?: number
  originalQuestion?: string
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
  const [pinnedByConv, setPinnedByConv] = useState<Record<string, PinnedSource[]>>({})
  const [workspaceId, setWorkspaceId] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const threadIdRef = useRef<string | null>(null)

  // Helper: get pinnedSources for current thread
  const currentPinned = threadIdRef.current ? pinnedByConv[threadIdRef.current] ?? [] : []

  const setCurrentPinned = useCallback(
    (updater: PinnedSource[] | ((prev: PinnedSource[]) => PinnedSource[])) => {
      const tid = threadIdRef.current
      if (!tid) return
      setPinnedByConv((prev) => {
        const current = prev[tid] ?? []
        const next = typeof updater === 'function' ? updater(current) : updater
        return { ...prev, [tid]: next }
      })
    },
    [],
  )

  const _finalizeStream = useCallback(() => {
    setIsStreaming(false)
    setStreamingNodes([])
  }, [])

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
          // Merge new sources into current conversation's pinnedSources
          setPinnedByConv((prev) => {
            const tid = data.thread_id
            const current = prev[tid] ?? []
            const prevMap = new Map(current.map((ps) => [ps.chunk_id, ps]))
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
            return newEntries.length > 0 ? { ...prev, [tid]: [...current, ...newEntries] } : prev
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

      const currentTid = threadIdRef.current || ''
      const convPinned = pinnedByConv[currentTid] ?? []
      const pinnedChunkIds = convPinned.filter((ps) => ps.pinned).map((ps) => ps.chunk_id)
      const excludedChunkIds = convPinned.filter((ps) => ps.excluded).map((ps) => ps.chunk_id)

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
    [isStreaming, pinnedByConv],
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
    _finalizeStream()
    threadIdRef.current = null
  }, [_finalizeStream])

  const loadMessages = useCallback((msgs: ChatMessage[], threadId?: string) => {
    setMessages(msgs)
    threadIdRef.current = threadId || null
    // Populate pinnedSources for this conversation from loaded messages' debug_info
    if (threadId) {
      const loaded: PinnedSource[] = []
      const seen = new Set<string>()
      for (const m of msgs) {
        const dbg = m.debugData as Record<string, any> | undefined
        const pinnedIds = new Set<string>(dbg?.pinned || [])
        const excludedIds = new Set<string>(dbg?.excluded || [])
        for (const s of m.sources || []) {
          if (s.chunk_id && !seen.has(s.chunk_id)) {
            seen.add(s.chunk_id)
            loaded.push({
              chunk_id: s.chunk_id,
              source: s.source || '',
              content: s.content || '',
              pinned: pinnedIds.has(s.chunk_id),
              excluded: excludedIds.has(s.chunk_id),
              score: s.score ?? 0,
              index: s.index ?? 0,
            })
          }
        }
      }
      setPinnedByConv((prev) => ({ ...prev, [threadId]: loaded }))
    }
  }, [])

  return {
    messages,
    isStreaming,
    streamingNodes,
    pinnedSources: currentPinned,
    setPinnedSources: setCurrentPinned,
    workspaceId,
    setWorkspaceId,
    sendMessage,
    stopStreaming,
    clearMessages,
    loadMessages,
    threadId: threadIdRef.current,
  }
}
