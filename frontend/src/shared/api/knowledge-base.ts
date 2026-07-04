import { req, withWorkspaceScope } from '@/shared/api/client'
import type { DebugSearchResponse, HotspotEntry, KBChunk, KBChunkResponse, KBConfig, KBStats } from '@/shared/api/types'

export const getKBStats = (workspaceId?: string) =>
  req<KBStats>(withWorkspaceScope('/knowledge-base/stats', workspaceId))

export const getKBChunks = (source?: string, search?: string, skip = 0, limit = 50, workspaceId?: string) => {
  const params = new URLSearchParams()
  if (source) params.set('source', source)
  if (search) params.set('search', search)
  params.set('skip', String(skip))
  params.set('limit', String(limit))
  return req<KBChunkResponse>(withWorkspaceScope('/knowledge-base/chunks', workspaceId, params))
}

export const getKBChunkById = (chunkId: string, workspaceId?: string) =>
  req<KBChunk>(withWorkspaceScope(`/knowledge-base/chunks/${encodeURIComponent(chunkId)}`, workspaceId))

export const getKBSourceNames = (workspaceId?: string) =>
  req<string[]>(withWorkspaceScope('/knowledge-base/sources', workspaceId))

export const getKBConfig = () => req<KBConfig>('/knowledge-base/config')

export const getKBHotspots = (workspaceId?: string) =>
  req<HotspotEntry[]>(withWorkspaceScope('/knowledge-base/hotspots', workspaceId))

export const debugSearch = (query: string, k = 5, searchStrategy = 'balanced', workspaceId?: string) =>
  req<DebugSearchResponse>(
    withWorkspaceScope('/knowledge-base/debug-search', workspaceId),
    { method: 'POST', body: JSON.stringify({ query, k, search_strategy: searchStrategy }) },
  )
