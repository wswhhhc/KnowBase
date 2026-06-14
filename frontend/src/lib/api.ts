export interface Source {
  source: string
  chunk_index?: number
  page?: number
  score?: number
  content: string
  url?: string
}

export interface Conversation {
  id: string
  thread_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  sources: Source[]
  quality_reason: string
  feedback?: string | null
  created_at: string
}

export interface DocSource {
  source: string
  count: number
}

export interface KBStats {
  chunk_count: number
  source_count: number
  total_chars: number
}

export interface KBChunk {
  source: string
  chunk_index: number
  chunk_id: string
  page: number | null
  content: string
  original_content: string | null
  section: string | null
}

export interface QueryLogEntry {
  timestamp: string
  question: string
  elapsed_ms: number
  retrieval_count: number
  quality_ok: boolean
  quality_reason: string
  used_web_search: boolean | null
  used_rerank: boolean | null
  question_type: string
  retry_count: number
  source_count: number
  answer_preview: string
  error: string
}

const BASE = '/api'

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Conversations ──

export const getConversations = () => req<Conversation[]>('/conversations')

export const createConversation = (title = '新对话') =>
  req<Conversation>('/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })

export const deleteConversation = (id: string) =>
  req(`/conversations/${id}`, { method: 'DELETE' })

export const renameConversation = (id: string, title: string) =>
  req<Conversation>(`/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })

export const getMessages = (convId: string) =>
  req<Message[]>(`/conversations/${convId}/messages`)

export const updateFeedback = (convId: string, msgId: number, feedback: string) =>
  req(`/conversations/${convId}/messages/${msgId}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ feedback }),
  })

export const exportConversation = (convId: string) =>
  req<{ markdown: string }>(`/conversations/${convId}/export`)

// ── Documents ──

export const getSources = () => req<DocSource[]>('/documents/sources')

export const uploadDocument = async (file: File) => {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/documents/upload`, { method: 'POST', body: form })
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

export const getKBChunks = (source?: string, search?: string) => {
  const params = new URLSearchParams()
  if (source) params.set('source', source)
  if (search) params.set('search', search)
  return req<KBChunk[]>(`/knowledge-base/chunks?${params}`)
}

export const getKBSourceNames = () => req<string[]>('/knowledge-base/sources')

// ── Metrics ──

export const queryLogs = (days: number = 7, limit: number = 500) =>
  req<QueryLogEntry[]>(`/metrics/logs?days=${days}&limit=${limit}`)

// ── Chat SSE ──

export interface ChatStreamCallbacks {
  onNode?: (label: string, nodes: string[]) => void
  onToken?: (text: string) => void
  onSources?: (data: { sources: Source[]; quality_reason: string; evidence_level: string; evidence_summary: string; outcome_category: string }) => void
  onDone?: (data: { thread_id: string; answer: string; sources: Source[]; quality_reason: string; evidence_level: string; evidence_summary: string; outcome_category: string; elapsed_ms: number }) => void
  onError?: (message: string) => void
}

export function chatStream(
  question: string,
  threadId: string | null,
  webSearchEnabled: boolean,
  searchStrategy: string,
  callbacks: ChatStreamCallbacks,
): AbortController {
  const controller = new AbortController()

  fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      thread_id: threadId,
      web_search_enabled: webSearchEnabled,
      search_strategy: searchStrategy,
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
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let event = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            event = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6)
            try {
              const parsed = JSON.parse(data)
              switch (event) {
                case 'node':
                  callbacks.onNode?.(parsed.label, parsed.nodes)
                  break
                case 'token':
                  callbacks.onToken?.(parsed.text)
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
            } catch { /* skip parse errors */ }
          }
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
