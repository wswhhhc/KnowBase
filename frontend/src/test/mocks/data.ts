import type { Conversation, Message, DocSource, KBChunk, KBStats, QueryLogEntry, DebugInfo } from '@/lib/api'

export const mockConversations: Conversation[] = [
  { id: 'conv-1', thread_id: 'thread-1', title: '测试对话', created_at: '2026-06-16T08:00:00Z', updated_at: '2026-06-16T08:30:00Z' },
  { id: 'conv-2', thread_id: 'thread-2', title: '关于 LLM 的讨论', created_at: '2026-06-15T10:00:00Z', updated_at: '2026-06-15T11:00:00Z' },
]

export const mockSources: DocSource[] = [
  { source: 'doc1.txt', count: 3 },
  { source: 'doc2.md', count: 5 },
]

export const mockMessages: Message[] = [
  { id: 1, role: 'user', content: '你好', sources: null, quality_reason: null, feedback: null, created_at: '2026-06-16T08:05:00Z' },
  { id: 2, role: 'assistant', content: '你好！有什么可以帮助你的？', sources: [], quality_reason: 'ok', feedback: null, created_at: '2026-06-16T08:05:10Z' },
]

export const mockKBStats: KBStats = {
  chunk_count: 150,
  source_count: 3,
  total_chars: 50000,
}

export const mockKBChunks: KBChunk[] = [
  { source: 'doc1.txt', chunk_index: 0, chunk_id: 'doc1.txt:0:abc', page: null, content: '这是第一段内容', original_content: '这是第一段内容', section: null },
  { source: 'doc1.txt', chunk_index: 1, chunk_id: 'doc1.txt:1:def', page: null, content: '这是第二段内容', original_content: '这是第二段内容', section: null },
]

export const mockQueryLogs: QueryLogEntry[] = [
  { timestamp: '2026-06-16T08:00:00Z', thread_id: 'thread-1', question: '你好', elapsed_ms: 1500, retrieval_count: 3, quality_ok: true, quality_reason: 'PASS', used_web_search: false, used_rerank: false, question_type: 'knowledge_base', retry_count: 0, source_count: 2, answer_preview: '你好！', error: null },
]

export const mockDebugInfo: DebugInfo = {
  nodes: [
    { name: 'route_question', label: '问题路由', elapsed_ms: 200, summary: 'knowledge_base' },
    { name: 'retrieve_docs', label: '检索文档', elapsed_ms: 300, summary: '3 条结果' },
  ],
  rewritten_question: null,
  retrieval_k: 30,
  candidates_before: 30,
  candidates_after: 3,
  after_rerank: 3,
  used_rerank: false,
  used_rewrite: false,
  quality_passed: true,
  quality_reason: 'PASS',
  retry_count: 0,
  used_web_search: false,
  web_results_count: null,
}

export function createMockFetch(response: any, ok = true, status = 200): ReturnType<typeof vi.fn> {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(response),
    text: () => Promise.resolve(typeof response === 'string' ? response : JSON.stringify(response)),
    headers: new Headers({ 'content-type': 'application/json' }),
  })
}

export function createMockSSEStream(events: { event: string; data: string }[]): ReadableStream {
  const encoder = new TextEncoder()
  const chunks = events.map(e => encoder.encode(`event: ${e.event}\ndata: ${e.data}\n\n`))
  return new ReadableStream({
    start(controller) {
      chunks.forEach(chunk => controller.enqueue(chunk))
      controller.close()
    },
  })
}
