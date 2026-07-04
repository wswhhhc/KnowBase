import { req, withWorkspaceScope } from '@/shared/api/client'
import type { Conversation, Message, PinStateResponse } from '@/shared/api/types'

export const getConversations = (workspaceId?: string) =>
  req<Conversation[]>(withWorkspaceScope('/conversations', workspaceId))

export const createConversation = (title = '新对话', workspaceId?: string) =>
  req<Conversation>(withWorkspaceScope('/conversations', workspaceId), {
    method: 'POST',
    body: JSON.stringify({ title }),
  })

export const deleteConversation = (id: string, workspaceId?: string) =>
  req(withWorkspaceScope(`/conversations/${id}`, workspaceId), { method: 'DELETE' })

export const deleteConversations = (ids: string[]) =>
  req('/conversations/batch-delete', {
    method: 'POST',
    body: JSON.stringify(ids),
  })

export const renameConversation = (id: string, title: string, workspaceId?: string) =>
  req<Conversation>(withWorkspaceScope(`/conversations/${id}`, workspaceId), {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })

export const getMessages = (convId: string, workspaceId?: string) =>
  req<Message[]>(withWorkspaceScope(`/conversations/${convId}/messages`, workspaceId))

export const getConversationPinState = (convId: string, workspaceId?: string) =>
  req<PinStateResponse>(withWorkspaceScope(`/conversations/${convId}/pin-state`, workspaceId))

export const updateFeedback = (
  convId: string,
  msgId: number,
  feedback: string,
  category?: string,
  detail?: string,
  workspaceId?: string,
) =>
  req(withWorkspaceScope(`/conversations/${convId}/messages/${msgId}/feedback`, workspaceId), {
    method: 'POST',
    body: JSON.stringify({ feedback, category, detail }),
  })

export const exportConversation = (
  convId: string,
  format = 'markdown',
  includeSources = true,
  includeDebug = false,
  workspaceId?: string,
) => {
  const params = new URLSearchParams({ format, include_sources: String(includeSources), include_debug: String(includeDebug) })
  return req<{ markdown?: string; json?: any }>(withWorkspaceScope(`/conversations/${convId}/export`, workspaceId, params))
}
