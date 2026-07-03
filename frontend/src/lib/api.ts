import type {
  DebugNodeInfo,
  DebugInfo,
  ChatStreamDonePayload,
  ChatStreamSourcesPayload,
} from './api-types'
import type { components } from './api-types.openapi'

type Schemas = components['schemas']

export type Source = Schemas['ChatSource']
export type Conversation = Schemas['ConversationOut']
export type ApiMessage = Schemas['MessageOut']
export type KBStats = Schemas['KBStats']
export type QueryLogEntry = Schemas['QueryLogEntry']
export type QueryLogsResponse = Schemas['QueryLogsResponse']
export type DocSource = Schemas['SourceOut']
export type HotspotEntry = Schemas['HotspotEntry']
export type KBConfig = Schemas['KBConfig']
export type IngestResponse = Schemas['IngestResponse']
export type DemoImportResponse = Schemas['DemoImportResponse']
export type KBChunk = Schemas['KBChunk']
export type RuntimeSettings = Schemas['RuntimeSettingsOut']
export type RuntimeSettingsUpdate = Schemas['RuntimeSettingsUpdate']
export type SettingsUpdateResult = Schemas['SettingsUpdateResult']
export type Workspace = Schemas['WorkspaceOut']
export type Bookmark = Schemas['BookmarkOut']
export type DebugSearchHit = Schemas['DebugSearchResult']
export type DebugSearchResponse = Schemas['DebugSearchResponse']
export type PinStateResponse = Schemas['PinStateOut']

export type {
  DebugNodeInfo,
  DebugInfo,
  ChatStreamDonePayload,
  ChatStreamSourcesPayload,
}

export interface Message extends ApiMessage {
  role: 'user' | 'assistant'
}

export interface KBChunkResponse {
  items: KBChunk[]
  total: number
}

export class ApiError extends Error {
  status: number
  retryAfter?: number

  constructor(status: number, message: string, retryAfter?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.retryAfter = retryAfter
  }
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
    throw await createApiErrorFromResponse(res)
  }
  return res.json()
}

async function createApiErrorFromResponse(res: Response): Promise<ApiError> {
  const retryAfter = Number(res.headers.get('Retry-After') || '') || undefined
  const text = await res.text()
  let message = text.trim()

  if (message) {
    try {
      const parsed = JSON.parse(message)
      if (typeof parsed === 'string') {
        message = parsed
      } else if (typeof parsed?.detail === 'string') {
        message = parsed.detail
      } else if (typeof parsed?.message === 'string') {
        message = parsed.message
      }
    } catch {
      // Keep plain-text responses unchanged.
    }
  }

  if (!message) {
    message = res.status === 429 && retryAfter
      ? `请求过于频繁，请在 ${retryAfter} 秒后重试。`
      : `HTTP ${res.status}`
  }

  return new ApiError(res.status, message, retryAfter)
}

// ── Conversations ──

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
  if (!res.ok) throw await createApiErrorFromResponse(res)
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
      if (!res.ok) {
        callbacks.onError?.((await createApiErrorFromResponse(res)).message)
        return
      }
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
      if (!res.ok) {
        callbacks.onError?.((await createApiErrorFromResponse(res)).message)
        return
      }
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

export const importDemoDocuments = (workspaceId?: string) =>
  req<DemoImportResponse>(withWorkspaceScope('/documents/import-demo', workspaceId), { method: 'POST' })

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

export const updateSettings = (data: RuntimeSettingsUpdate) =>
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
  onSources?: (data: ChatStreamSourcesPayload) => void
  onDone?: (data: ChatStreamDonePayload) => void
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
        callbacks.onError?.((await createApiErrorFromResponse(res)).message)
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
