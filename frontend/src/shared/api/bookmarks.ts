import { req } from '@/shared/api/client'
import type { Bookmark } from '@/shared/api/types'

export const MASKED_SECRET_VALUE = '__KEEP_EXISTING_SECRET__'

export const getBookmarks = (workspaceId?: string, search?: string) => {
  const params = new URLSearchParams()
  if (workspaceId) params.set('workspace_id', workspaceId)
  if (search) params.set('search', search)
  const qs = params.toString()
  return req<Bookmark[]>(`/bookmarks${qs ? `?${qs}` : ''}`)
}

export const createBookmark = (data: {
  workspace_id?: string
  conversation_id?: string
  message_id?: number
  chunk_id?: string
  note?: string
  content?: string
  source?: string
  tags?: string
}) =>
  req<Bookmark>('/bookmarks', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateBookmark = (id: number, data: { note?: string; tags?: string }) =>
  req<Bookmark>(`/bookmarks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

export const deleteBookmark = (id: number) =>
  req(`/bookmarks/${id}`, { method: 'DELETE' })
