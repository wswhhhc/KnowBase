import { useState } from 'react'
import type { DebugInfo } from '@/shared/api'
import type { Source } from '@/shared/api'
import type { ChatMessage } from './types'

interface AssistantCompletion {
  answer: string
  sources: Source[]
  quality_reason: string
  evidence_level: string
  evidence_summary: string
  outcome_category: string
  conv_id: string
  assistant_msg_id: number
  elapsed_ms: number
}

export function useChatMessages(maxVisibleMessages = 100) {
  const [messages, setMessages] = useState<ChatMessage[]>([])

  const visibleMessages = messages.length > maxVisibleMessages
    ? messages.slice(-maxVisibleMessages)
    : messages

  const appendPendingExchange = (
    question: string,
    assistantId: string,
    metadata?: { searchStrategy?: string; webSearchEnabled?: boolean },
  ) => {
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: question,
    }
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      streaming: true,
      originalQuestion: question,
      searchStrategy: metadata?.searchStrategy,
      webSearchEnabled: metadata?.webSearchEnabled,
    }

    setMessages((prev) => [...prev, userMessage, assistantMessage])
  }

  const updateAssistantContent = (messageId: string, content: string) => {
    setMessages((prev) =>
      prev.map((message) => (
        message.id === messageId
          ? { ...message, content }
          : message
      )),
    )
  }

  const mergeAssistantMetadata = (
    messageId: string,
    payload: {
      sources: Source[]
      quality_reason: string
      evidence_level: string
      evidence_summary: string
      outcome_category: string
    },
  ) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId
          ? {
              ...message,
              sources: payload.sources,
              quality_reason: payload.quality_reason,
              evidence_level: payload.evidence_level,
              evidence_summary: payload.evidence_summary,
              outcome_category: payload.outcome_category,
            }
          : message,
      ),
    )
  }

  const finalizeAssistantMessage = (messageId: string, payload: AssistantCompletion, debugData?: DebugInfo) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId
          ? {
              ...message,
              content: payload.answer,
              sources: payload.sources,
              quality_reason: payload.quality_reason,
              evidence_level: payload.evidence_level,
              evidence_summary: payload.evidence_summary,
              outcome_category: payload.outcome_category,
              usedRerank: debugData?.used_rerank,
              elapsedMs: payload.elapsed_ms,
              streaming: false,
              debugData,
              convId: payload.conv_id,
              assistantMsgId: payload.assistant_msg_id,
            }
          : message,
      ),
    )
  }

  const setAssistantError = (messageId: string, errorMessage: string) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId
          ? { ...message, content: `错误：${errorMessage}`, streaming: false }
          : message,
      ),
    )
  }

  const stopStreamingMessages = () => {
    setMessages((prev) =>
      prev.map((message) => (message.streaming ? { ...message, streaming: false } : message)),
    )
  }

  const clearMessages = () => {
    setMessages([])
  }

  const loadMessages = (nextMessages: ChatMessage[]) => {
    setMessages(nextMessages)
  }

  return {
    messages,
    visibleMessages,
    appendPendingExchange,
    updateAssistantContent,
    mergeAssistantMetadata,
    finalizeAssistantMessage,
    setAssistantError,
    stopStreamingMessages,
    clearMessages,
    loadMessages,
  }
}
