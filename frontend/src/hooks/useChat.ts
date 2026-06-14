import { useState, useRef, useCallback } from 'react'
import { chatStream, type ChatStreamCallbacks, type Source } from '@/lib/api'

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
}

export function useChat() {
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
                  }
                : m,
            ),
          )
          setIsStreaming(false)
          setStreamingNodes([])
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
    setIsStreaming(false)
    setStreamingNodes([])
    setMessages((prev) =>
      prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
    )
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
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
