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
  { id: 1, role: 'user', content: '你好', sources: [], quality_reason: '', feedback: null, created_at: '2026-06-16T08:05:00Z' },
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
  { timestamp: '2026-06-16T08:00:00Z', thread_id: 'thread-1', question: '你好', elapsed_ms: 1500, retrieval_count: 3, quality_ok: true, quality_reason: 'PASS', used_web_search: false, used_rerank: false, question_type: 'knowledge_base', retry_count: 0, source_count: 2, answer_preview: '你好！', error: '' },
]

export const mockDebugInfo: DebugInfo = {
  nodes: [
    { name: 'route_question', label: '问题路由', elapsed_ms: 200, summary: 'knowledge_base' },
    { name: 'retrieve_docs', label: '检索文档', elapsed_ms: 300, summary: '3 条结果' },
  ],
  rewritten_question: '',
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
  web_results_count: 0,
}

export const mockMessagesFull: Message[] = [
  { id: 1, role: 'user', content: '年假政策', sources: [], quality_reason: '', feedback: null, created_at: '2026-06-16T08:00:00Z' },
  { id: 2, role: 'assistant', content: '根据文档 [1]，年假为 5 天。\n\n引用编号 [1] 和 [2] 来自不同来源[1,2]。', sources: [{ source: 'policy.txt', index: 1, content: '年假5天' }, { source: 'hr.txt', index: 2, content: '试用期员工适用' }], quality_reason: 'PASS', feedback: null, created_at: '2026-06-16T08:00:05Z' },
]

export const mockSSEDebugEvent: DebugInfo = {
  nodes: [
    { name: 'route_question', label: '问题路由', elapsed_ms: 100, summary: '→ knowledge_base' },
    { name: 'rewrite_query', label: '查询改写', elapsed_ms: 50, summary: '无需改写' },
    { name: 'retrieve_docs', label: '混合检索', elapsed_ms: 200, summary: '3 候选' },
    { name: 'generate_answer', label: '生成回答', elapsed_ms: 1500, summary: '120 字' },
    { name: 'check_quality', label: '质量检查', elapsed_ms: 300, summary: '✓ 通过' },
  ],
  rewritten_question: '',
  retrieval_k: 30,
  candidates_before: 3,
  candidates_after: 3,
  after_rerank: 3,
  used_rerank: false,
  used_rewrite: false,
  quality_passed: true,
  quality_reason: 'PASS',
  retry_count: 0,
  used_web_search: false,
  web_results_count: 0,
}

export const mockExportData = { markdown: '# 测试对话\n\n### 👤 用户\n年假政策\n\n### 🤖 助手\n5天\n\n---\n' }

export const mockLongConversationList: Conversation[] = Array.from({ length: 25 }, (_, i) => ({
  id: `conv-${i}`,
  thread_id: `thread-${i}`,
  title: `对话 ${i + 1}`,
  created_at: '2026-06-16T00:00:00Z',
  updated_at: `2026-06-16T${String(i).padStart(2, '0')}:00:00Z`,
}))

export const mockHotspotData = [
  { chunk_id: 'doc1.txt:0:abc', source: 'doc1.txt', hits: 10, content_preview: '第一段' },
  { chunk_id: 'doc1.txt:1:def', source: 'doc1.txt', hits: 5, content_preview: '第二段' },
]

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
