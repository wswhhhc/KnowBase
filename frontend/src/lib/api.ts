import type {
  Source, Conversation, ApiMessage, KBStats, QueryLogEntry,
  DebugNodeInfo, DebugInfo, DocSource, HotspotEntry, KBConfig, IngestResponse,
} from './api-types.generated'

export type { Source, Conversation, KBStats, QueryLogEntry, DebugNodeInfo, DebugInfo, DocSource, HotspotEntry, KBConfig, IngestResponse }
import type { KBChunk } from './api-types.generated'
export type { KBChunk }

export interface Message extends ApiMessage {
  role: 'user' | 'assistant'
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
  const params = workspaceId !== undefined && workspaceId !== ''
    ? `?workspace_id=${encodeURIComponent(workspaceId)}`
    : workspaceId === '' ? '?workspace_id=' : ''
  return req<Conversation[]>(`/conversations${params}`)
}

export const createConversation = (title = '新对话', workspaceId?: string) => {
  const params = workspaceId !== undefined && workspaceId !== ''
    ? `?workspace_id=${encodeURIComponent(workspaceId)}`
    : workspaceId === '' ? '?workspace_id=' : ''
  return req<Conversation>(`/conversations${params}`, {
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

export const updateFeedback = (convId: string, msgId: number, feedback: string, category?: string, detail?: string) =>
  req(`/conversations/${convId}/messages/${msgId}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ feedback, category, detail }),
  })

export const exportConversation = (convId: string) =>
  req<{ markdown: string }>(`/conversations/${convId}/export`)

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

// ── Documents ──

export const getSources = () => req<DocSource[]>('/documents/sources')

export const uploadDocument = async (file: File) => {
  const form = new FormData()
  form.append('file', file)
  const headers: Record<string, string> = authHeaders()
  const res = await fetch(`${BASE}/documents/upload`, { method: 'POST', body: form, headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export const ingestUrl = (url: string) =>
  req<{ chunk_count: number; total_docs: number; message: string }>('/documents/ingest-url', {
    method: 'POST',
    body: JSON.stringify({ url }),
  })

export const deleteSource = (source: string) =>
  req(`/documents/source/${encodeURIComponent(source)}`, { method: 'DELETE' })

export const clearKnowledgeBase = () =>
  req('/documents/clear', { method: 'POST' })

// ── KB Browser ──

export const getKBStats = () => req<KBStats>('/knowledge-base/stats')

export const getKBChunks = (source?: string, search?: string, skip = 0, limit = 50) => {
  const params = new URLSearchParams()
  if (source) params.set('source', source)
  if (search) params.set('search', search)
  params.set('skip', String(skip))
  params.set('limit', String(limit))
  return req<KBChunkResponse>(`/knowledge-base/chunks?${params}`)
}

export const getKBSourceNames = () => req<string[]>('/knowledge-base/sources')

export const getKBConfig = () => req<KBConfig>('/knowledge-base/config')

export const getKBHotspots = () => req<HotspotEntry[]>('/knowledge-base/hotspots')

// ── Metrics ──

export const queryLogs = (days: number = 7, limit: number = 500) =>
  req<QueryLogEntry[]>(`/metrics/logs?days=${days}&limit=${limit}`)

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
    } catch (e) {
      console.warn('SSE parse error', e)
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
