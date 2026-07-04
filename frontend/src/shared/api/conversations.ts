import { req, withWorkspaceScope } from '@/shared/api/client'
import type { Conversation, Message, PinStateResponse } from '@/shared/api/types'

export const getConversations = (workspaceId?: string) =>
  req<Conversation[]>(withWorkspaceScope('/conversations', workspaceId))

export const createConversation = (title = '新对话', workspaceId?: string) =>
  req<Conversation>(withWorkspaceScope('/conversations', workspaceId), {
    method: 'POST',
    body: JSON.stringify({ title }),
  })

export const deleteConversation = (id: string) =>
  req(`/conversations/${id}`, { method: 'DELETE' })

export const deleteConversations = (ids: string[]) =>
  req('/conversations/batch-delete', {
    method: 'POST',
    body: JSON.stringify(ids),
  })

export const renameConversation = (id: string, title: string) =>
  req<Conversation>(`/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })

export const getMessages = (convId: string) =>
  req<Message[]>(`/conversations/${convId}/messages`)

export const getConversationPinState = (convId: string) =>
  req<PinStateResponse>(`/conversations/${convId}/pin-state`)

export const updateFeedback = (convId: string, msgId: number, feedback: string, category?: string, detail?: string) =>
  req(`/conversations/${convId}/messages/${msgId}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ feedback, category, detail }),
  })

export const exportConversation = (convId: string, format = 'markdown', includeSources = true, includeDebug = false) => {
  const params = new URLSearchParams({ format, include_sources: String(includeSources), include_debug: String(includeDebug) })
  return req<{ markdown?: string; json?: any }>(`/conversations/${convId}/export?${params}`)
}
