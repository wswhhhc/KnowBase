import type {
  Source, Conversation, ApiMessage, KBStats, QueryLogEntry,
  DebugNodeInfo, DebugInfo, DocSource, HotspotEntry, KBConfig, IngestResponse, KBChunk,
  RuntimeSettings, SettingsUpdateResult,
} from './api-types'

export interface QueryLogsResponse {
  logs: QueryLogEntry[]
  total_cost: number
  total_tokens: number
  total_prompt_tokens: number
  total_completion_tokens: number
}

export type {
  Source,
  Conversation,
  KBStats,
  QueryLogEntry,
  DebugNodeInfo,
  DebugInfo,
  DocSource,
  HotspotEntry,
  KBConfig,
  IngestResponse,
  KBChunk,
  RuntimeSettings,
  SettingsUpdateResult,
}

export interface Message extends ApiMessage {
  role: 'user' | 'assistant'
}

export interface PinStateResponse {
  thread_id: string
  pinned_chunk_ids: string[]
  excluded_chunk_ids: string[]
}

export interface KBChunkResponse {
  items: KBChunk[]
  total: number
}

const BASE = '/api'

function authHeaders(): Record<string, string> {
  const key = localStorage.getItem('knowbase_api_key')
  return key ? { 'Authorization': `Bearer ${key}` } : {}
}

function withQuery(path: string, params: URLSearchParams): string {
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

function withWorkspaceScope(path: string, workspaceId?: string, params?: URLSearchParams): string {
  const scopedParams = params ? new URLSearchParams(params) : new URLSearchParams()
  if (workspaceId !== undefined) {
    scopedParams.set('workspace_id', workspaceId)
  }
  return withQuery(path, scopedParams)
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Conversations ──

export interface Workspace {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
}

export const getConversations = (workspaceId?: string) => {
  return req<Conversation[]>(withWorkspaceScope('/conversations', workspaceId))
}

export const createConversation = (title = '新对话', workspaceId?: string) => {
  return req<Conversation>(withWorkspaceScope('/conversations', workspaceId), {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

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

// ── Workspaces ──

export const getWorkspaces = () => req<Workspace[]>('/workspaces')

export const createWorkspace = (name = '新工作区', description = '') =>
  req<Workspace>('/workspaces', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  })

export const renameWorkspace = (id: string, name: string) =>
  req<Workspace>(`/workspaces/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })

export const deleteWorkspace = (id: string) =>
  req(`/workspaces/${id}`, { method: 'DELETE' })

// ── Bookmarks ──

export interface Bookmark {
  id: number
  workspace_id: string
  conversation_id: string
  message_id: number
  chunk_id: string
  note: string
  content: string
  source: string
  tags: string
  created_at: string
}

export interface DebugSearchHit {
  chunk_id: string
  source: string
  content: string
  score: number | null
  vector_score: number | null
  bm25_score: number | null
  rrf_score: number | null
  vector_rank: number | null
  bm25_rank: number | null
  rrf_rank: number | null
  rerank_rank: number | null
}

export interface DebugSearchResponse {
  strategy: string
  vector_results: DebugSearchHit[]
  bm25_results: DebugSearchHit[]
  fused_results: DebugSearchHit[]
}

export const MASKED_SECRET_VALUE = '__KEEP_EXISTING_SECRET__'

export const getBookmarks = (workspaceId?: string, search?: string) => {
  const params = new URLSearchParams()
  if (workspaceId) params.set('workspace_id', workspaceId)
  if (search) params.set('search', search)
  const qs = params.toString()
  return req<Bookmark[]>(`/bookmarks${qs ? `?${qs}` : ''}`)
}

export const createBookmark = (data: {
  workspace_id?: string; conversation_id?: string; message_id?: number;
  chunk_id?: string; note?: string; content?: string; source?: string; tags?: string
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

// ── Documents ──

export const checkSource = (sourceName: string, workspaceId?: string) => {
  const params = new URLSearchParams({ source_name: sourceName })
  return req<{ exists: boolean }>(withWorkspaceScope('/documents/check-source', workspaceId, params))
}

export const getSources = (workspaceId?: string) =>
  req<DocSource[]>(withWorkspaceScope('/documents/sources', workspaceId))

export const uploadDocument = async (file: File, versionMode?: string, workspaceId?: string) => {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams()
  if (versionMode) params.set('version_mode', versionMode)
  const headers: Record<string, string> = authHeaders()
  const res = await fetch(`${BASE}${withWorkspaceScope('/documents/upload', workspaceId, params)}`, { method: 'POST', body: form, headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export function uploadDocumentStream(
  file: File,
  versionMode: string | undefined,
  callbacks: {
    onProgress?: (phase: string, percent: number) => void
    onDone?: (result: any) => void
    onError?: (message: string) => void
  },
  workspaceId?: string,
): AbortController {
  const controller = new AbortController()
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams()
  if (versionMode) params.set('version_mode', versionMode)

  fetch(`${BASE}${withWorkspaceScope('/documents/upload-stream', workspaceId, params)}`, {
    method: 'POST',
    body: form,
    headers: authHeaders(),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) { callbacks.onError?.(await res.text()); return }
      const reader = res.body?.getReader()
      if (!reader) return
      const decoder = new TextDecoder()
      const parser = new SSEParser()
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          for (const parsed of parser.flush()) {
            handleSSEEvent(parsed.event, parsed.data, callbacks)
          }
          break
        }
        const text = decoder.decode(value, { stream: true })
        for (const parsed of parser.feed(text)) {
          handleSSEEvent(parsed.event, parsed.data, callbacks)
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') callbacks.onError?.(err.message)
    })
  return controller
}

export function ingestUrlStream(
  url: string,
  versionMode: string | undefined,
  callbacks: {
    onProgress?: (phase: string, percent: number) => void
    onDone?: (result: any) => void
    onError?: (message: string) => void
  },
  workspaceId?: string,
): AbortController {
  const controller = new AbortController()
  const params = new URLSearchParams()
  if (versionMode) params.set('version_mode', versionMode)
  fetch(`${BASE}${withWorkspaceScope('/documents/ingest-url-stream', workspaceId, params)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ url }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) { callbacks.onError?.(await res.text()); return }
      const reader = res.body?.getReader()
      if (!reader) return
      const decoder = new TextDecoder()
      const parser = new SSEParser()
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          for (const parsed of parser.flush()) {
            handleSSEEvent(parsed.event, parsed.data, callbacks)
          }
          break
        }
        const text = decoder.decode(value, { stream: true })
        for (const parsed of parser.feed(text)) {
          handleSSEEvent(parsed.event, parsed.data, callbacks)
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') callbacks.onError?.(err.message)
    })
  return controller
}

function handleSSEEvent(
  event: string,
  data: string,
  callbacks: {
    onProgress?: (phase: string, percent: number) => void
    onDone?: (result: any) => void
    onError?: (message: string) => void
  },
) {
  try {
    const parsed = JSON.parse(data)
    switch (event) {
      case 'progress':
        callbacks.onProgress?.(parsed.phase, parsed.percent)
        break
      case 'done':
        callbacks.onDone?.(parsed)
        break
      case 'error':
        callbacks.onError?.(parsed.message)
        break
    }
  } catch { /* ignore parse errors */ }
}

export const ingestUrl = (url: string, versionMode?: string, workspaceId?: string) => {
  const params = new URLSearchParams()
  if (versionMode) params.set('version_mode', versionMode)
  return req<{ chunk_count: number; total_docs: number; message: string }>(withWorkspaceScope('/documents/ingest-url', workspaceId, params), {
    method: 'POST',
    body: JSON.stringify({ url }),
  })
}

export const deleteSource = (source: string, workspaceId?: string) =>
  req(withWorkspaceScope(`/documents/source/${encodeURIComponent(source)}`, workspaceId), { method: 'DELETE' })

export const clearKnowledgeBase = (workspaceId?: string) =>
  req(withWorkspaceScope('/documents/clear', workspaceId), { method: 'POST' })

// ── KB Browser ──

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

// ── Metrics ──

export const queryLogs = (days: number = 7, limit: number = 500) =>
  req<QueryLogsResponse>(`/metrics/logs?days=${days}&limit=${limit}`)

// ── Settings ──

export const getSettings = () =>
  req<RuntimeSettings>('/settings')

export const updateSettings = (data: Partial<RuntimeSettings>) =>
  req<SettingsUpdateResult>('/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  })

// ── Chat SSE ──

class SSEParser {
  private buffer = ''
  private currentEvent = 'message'
  private currentData: string[] = []

  /**
   * Feed raw text chunks into the parser. Returns an array of parsed events.
   * Each event has { event: string, data: string }.
   */
  feed(chunk: string): Array<{ event: string; data: string }> {
    // Normalize CRLF / bare CR to LF so SSE events parse correctly
    // regardless of the server's line-ending convention.
    this.buffer += chunk.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
    const events: Array<{ event: string; data: string }> = []
    const lines = this.buffer.split('\n')
    this.buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        this.currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        this.currentData.push(line.slice(6))
      } else if (line === '') {
        // Empty line = event delimiter (SSE spec: CR / LF / CRLF blank line)
        if (this.currentData.length > 0) {
          events.push({
            event: this.currentEvent,
            data: this.currentData.join('\n'),
          })
        }
        this.currentEvent = 'message'
        this.currentData = []
      }
      // Ignore comments (lines starting with :) and other lines
    }
    return events
  }

  /**
   * Flush remaining buffered data. Call after the stream ends.
   */
  flush(): Array<{ event: string; data: string }> {
    if (this.currentData.length > 0) {
      const events = [{
        event: this.currentEvent,
        data: this.currentData.join('\n'),
      }]
      this.currentEvent = 'message'
      this.currentData = []
      return events
    }
    return []
  }
}

function createChatStreamAdapter(callbacks: ChatStreamCallbacks) {
  return (event: string, data: string) => {
    try {
      const parsed = JSON.parse(data)
      switch (event) {
        case 'node':
          callbacks.onNode?.(parsed.label, parsed.nodes)
          break
        case 'token':
          callbacks.onToken?.(parsed.text)
          break
        case 'debug':
          callbacks.onDebug?.(parsed)
          break
        case 'sources':
          callbacks.onSources?.(parsed)
          break
        case 'done':
          callbacks.onDone?.(parsed)
          break
        case 'error':
          callbacks.onError?.(parsed.message)
          break
      }
    } catch {
      // Ignore malformed SSE payloads so the stream can continue.
    }
  }
}

export interface ChatStreamCallbacks {
  onNode?: (label: string, nodes: string[]) => void
  onToken?: (text: string) => void
  onDebug?: (data: DebugInfo) => void
  onSources?: (data: { sources: Source[]; quality_reason: string; evidence_level: string; evidence_summary: string; outcome_category: string }) => void
  onDone?: (data: { thread_id: string; conv_id: string; assistant_msg_id: number; answer: string; sources: Source[]; quality_reason: string; evidence_level: string; evidence_summary: string; outcome_category: string; elapsed_ms: number }) => void
  onError?: (message: string) => void
}

export function chatStream(
  question: string,
  threadId: string | null,
  webSearchEnabled: boolean,
  searchStrategy: string,
  callbacks: ChatStreamCallbacks,
  pinnedChunkIds?: string[],
  excludedChunkIds?: string[],
  workspaceId?: string,
): AbortController {
  const controller = new AbortController()

  fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      question,
      thread_id: threadId,
      web_search_enabled: webSearchEnabled,
      search_strategy: searchStrategy,
      pinned_chunk_ids: pinnedChunkIds || [],
      excluded_chunk_ids: excludedChunkIds || [],
      workspace_id: workspaceId || '',
    }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const text = await res.text()
        callbacks.onError?.(text)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      const parser = new SSEParser()
      const processSSEEvent = createChatStreamAdapter(callbacks)

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          for (const parsed of parser.flush()) {
            processSSEEvent(parsed.event, parsed.data)
          }
          break
        }

        const text = decoder.decode(value, { stream: true })
        for (const parsed of parser.feed(text)) {
          processSSEEvent(parsed.event, parsed.data)
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        callbacks.onError?.(err.message)
      }
    })

  return controller
}
