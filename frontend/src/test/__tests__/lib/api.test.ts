import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as api from '@/shared/api'
import type { ChatStreamCallbacks } from '@/shared/api'

beforeEach(() => {
  vi.restoreAllMocks()
})

// ── req helper via public functions ──

describe('req helper (tested through public functions)', () => {
  it('authHeaders prefers stored JWT access token over legacy API key', () => {
    localStorage.clear()
    localStorage.setItem('knowbase_access_token', 'jwt-token')
    localStorage.setItem('knowbase_api_key', 'legacy-key')

    expect(api.authHeaders()).toEqual({ Authorization: 'Bearer jwt-token' })
  })

  it('authHeaders falls back to the legacy API key when no JWT is stored', () => {
    localStorage.clear()
    localStorage.setItem('knowbase_api_key', 'legacy-key')

    expect(api.authHeaders()).toEqual({ Authorization: 'Bearer legacy-key' })
  })

  it('req preserves computed auth headers when a wrapper passes headers: undefined', async () => {
    localStorage.clear()
    localStorage.setItem('knowbase_access_token', 'jwt-token')
    const fn = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
      text: () => Promise.resolve('[]'),
      headers: new Headers(),
    })
    vi.stubGlobal('fetch', fn)

    await api.listAdminUsers(undefined)

    expect(fn).toHaveBeenCalledWith(
      '/api/admin/users',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer jwt-token' }),
      }),
    )
    vi.unstubAllGlobals()
  })

  it('persists and clears auth session tokens', () => {
    localStorage.clear()

    api.saveAuthSession({
      access_token: 'access-token',
      refresh_token: 'refresh-token',
      token_type: 'bearer',
      expires_in: 1800,
      user: {
        id: 'user-1',
        username: 'admin',
        role: 'admin',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    })

    expect(api.getStoredAccessToken()).toBe('access-token')
    expect(api.getStoredRefreshToken()).toBe('refresh-token')
    expect(api.getStoredUser()?.username).toBe('admin')

    api.clearAuthSession()

    expect(api.getStoredAccessToken()).toBe('')
    expect(api.getStoredRefreshToken()).toBe('')
    expect(api.getStoredUser()).toBeNull()
  })

  it('getConversations calls correct URL', async () => {
    const mock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]), text: () => Promise.resolve('[]'), headers: new Headers() })
    vi.stubGlobal('fetch', mock)
    await api.getConversations()
    expect(mock).toHaveBeenCalledWith('/api/conversations', expect.objectContaining({ headers: expect.any(Object) }))
    vi.unstubAllGlobals()
  })

  it('req throws on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404, text: () => Promise.resolve('Not Found'), headers: new Headers() }))
    await expect(api.getConversations()).rejects.toThrow(/Not Found/)
    vi.unstubAllGlobals()
  })

  it('req extracts JSON detail for 429 responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      text: () => Promise.resolve(JSON.stringify({ detail: '请求过于频繁，请在 60 秒后重试。' })),
      headers: new Headers({ 'Retry-After': '60' }),
    }))
    await expect(api.getConversations()).rejects.toThrow('请求过于频繁，请在 60 秒后重试。')
    vi.unstubAllGlobals()
  })
})

describe('Admin API', () => {
  it('listAdminAuditLogs builds optional query params', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]), text: () => Promise.resolve('[]'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)

    await api.listAdminAuditLogs(undefined, { actorUserId: 'user-1', limit: 25 })

    expect(fn).toHaveBeenCalledWith('/api/admin/audit-logs?actor_user_id=user-1&limit=25', expect.any(Object))
    vi.unstubAllGlobals()
  })
})

describe('Conversations API', () => {
  it('createConversation sends POST with title', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ id: '1' }), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.createConversation('新标题')
    expect(fn).toHaveBeenCalledWith('/api/conversations', expect.objectContaining({ method: 'POST' }))
    vi.unstubAllGlobals()
  })

  it('deleteConversation sends DELETE', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}), text: () => Promise.resolve(''), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.deleteConversation('conv-1')
    expect(fn).toHaveBeenCalledWith('/api/conversations/conv-1', expect.objectContaining({ method: 'DELETE' }))
    vi.unstubAllGlobals()
  })

  it('renameConversation sends PATCH', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.renameConversation('conv-1', '新标题')
    expect(fn).toHaveBeenCalledWith('/api/conversations/conv-1', expect.objectContaining({ method: 'PATCH' }))
    vi.unstubAllGlobals()
  })

  it('getMessages calls correct URL', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]), text: () => Promise.resolve('[]'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.getMessages('conv-1')
    expect(fn).toHaveBeenCalledWith('/api/conversations/conv-1/messages', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('getConversationPinState calls correct URL', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ thread_id: 't-1', pinned_chunk_ids: [], excluded_chunk_ids: [] }), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.getConversationPinState('conv-1')
    expect(fn).toHaveBeenCalledWith('/api/conversations/conv-1/pin-state', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('updateFeedback sends POST', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}), text: () => Promise.resolve(''), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.updateFeedback('conv-1', 1, '👍')
    expect(fn).toHaveBeenCalledWith('/api/conversations/conv-1/messages/1/feedback', expect.objectContaining({ method: 'POST' }))
    vi.unstubAllGlobals()
  })

  it('exportConversation returns markdown', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ markdown: '# title' }), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    const result = await api.exportConversation('conv-1')
    expect(result.markdown).toBe('# title')
    vi.unstubAllGlobals()
  })
})

describe('Documents API', () => {
  it('getSources returns list', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([{ source: 'a.txt', count: 1 }]), text: () => Promise.resolve('[]'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    const result = await api.getSources('ws-1')
    expect(result).toHaveLength(1)
    expect(fn).toHaveBeenCalledWith('/api/documents/sources?workspace_id=ws-1', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('uploadDocument uses FormData', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ chunk_count: 2 }), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    const file = new File(['test'], 'test.txt', { type: 'text/plain' })
    await api.uploadDocument(file, 'append', 'ws-1')
    expect(fn).toHaveBeenCalledWith('/api/documents/upload?version_mode=append&workspace_id=ws-1', expect.objectContaining({ method: 'POST' }))
    vi.unstubAllGlobals()
  })

  it('ingestUrl sends POST with URL', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ chunk_count: 1, total_docs: 1, message: 'ok' }), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.ingestUrl('https://example.com', undefined, 'ws-1')
    expect(fn).toHaveBeenCalledWith('/api/documents/ingest-url?workspace_id=ws-1', expect.objectContaining({ method: 'POST' }))
    vi.unstubAllGlobals()
  })

  it('ingestUrlStream passes version_mode when provided', async () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.close()
      },
    })
    const fn = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => stream.getReader() },
    })
    vi.stubGlobal('fetch', fn)
    api.ingestUrlStream('https://example.com', 'append', {}, 'ws-1')
    expect(fn).toHaveBeenCalledWith(
      '/api/documents/ingest-url-stream?version_mode=append&workspace_id=ws-1',
      expect.objectContaining({ method: 'POST' }),
    )
    vi.unstubAllGlobals()
  })

  it('deleteSource encodes URI component', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}), text: () => Promise.resolve(''), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.deleteSource('my file.txt', 'ws-1')
    expect(fn).toHaveBeenCalledWith('/api/documents/source/my%20file.txt?workspace_id=ws-1', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('clearKnowledgeBase sends POST', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ message: 'cleared' }), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.clearKnowledgeBase('ws-1')
    expect(fn).toHaveBeenCalledWith('/api/documents/clear?workspace_id=ws-1', expect.objectContaining({ method: 'POST' }))
    vi.unstubAllGlobals()
  })

  it('rebuildIndex sends POST with workspace scope', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ job_id: 'job-1', job: {} }), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.rebuildIndex('ws-1')
    expect(fn).toHaveBeenCalledWith('/api/documents/rebuild-index?workspace_id=ws-1', expect.objectContaining({ method: 'POST' }))
    vi.unstubAllGlobals()
  })

  it('importDemoDocuments sends POST with workspace scope', async () => {
    const fn = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ chunk_count: 3, total_docs: 12, message: 'ok', imported_sources: ['contract_notice.md'], suggested_questions: [] }),
      text: () => Promise.resolve('{}'),
      headers: new Headers(),
    })
    vi.stubGlobal('fetch', fn)
    await api.importDemoDocuments('ws-1')
    expect(fn).toHaveBeenCalledWith('/api/documents/import-demo?workspace_id=ws-1', expect.objectContaining({ method: 'POST' }))
    vi.unstubAllGlobals()
  })
})

describe('Jobs API', () => {
  const queuedJob = {
    id: 'job-1',
    job_type: 'ingest_file',
    status: 'queued',
    workspace_id: '',
    error: '',
    attempts: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
  const succeededJob = { ...queuedJob, status: 'succeeded' }

  it('listJobs calls the jobs endpoint', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]), text: () => Promise.resolve('[]'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.listJobs()
    expect(fn).toHaveBeenCalledWith('/api/jobs', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('getJob encodes the job id in the path', async () => {
    const fn = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ...queuedJob, id: 'job/1' }),
      text: () => Promise.resolve('{}'),
      headers: new Headers(),
    })
    vi.stubGlobal('fetch', fn)
    await api.getJob('job/1')
    expect(fn).toHaveBeenCalledWith('/api/jobs/job%2F1', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('cancelJob sends POST to the cancel endpoint', async () => {
    const fn = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ...queuedJob, status: 'canceled' }),
      text: () => Promise.resolve('{}'),
      headers: new Headers(),
    })
    vi.stubGlobal('fetch', fn)
    await api.cancelJob('job-1')
    expect(fn).toHaveBeenCalledWith('/api/jobs/job-1/cancel', expect.objectContaining({ method: 'POST' }))
    vi.unstubAllGlobals()
  })

  it('retryJob sends POST to the retry endpoint', async () => {
    const fn = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ...queuedJob, status: 'queued' }),
      text: () => Promise.resolve('{}'),
      headers: new Headers(),
    })
    vi.stubGlobal('fetch', fn)
    await api.retryJob('job/1')
    expect(fn).toHaveBeenCalledWith('/api/jobs/job%2F1/retry', expect.objectContaining({ method: 'POST' }))
    vi.unstubAllGlobals()
  })

  it('detects terminal job statuses', () => {
    expect(api.isTerminalJob({ status: 'queued' })).toBe(false)
    expect(api.isTerminalJob({ status: 'running' })).toBe(false)
    expect(api.isTerminalJob({ status: 'succeeded' })).toBe(true)
    expect(api.isTerminalJob({ status: 'failed' })).toBe(true)
    expect(api.isTerminalJob({ status: 'canceled' })).toBe(true)
  })

  it('pollJob fetches until the job reaches a terminal status', async () => {
    const onUpdate = vi.fn()
    const fn = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(queuedJob), text: () => Promise.resolve('{}'), headers: new Headers() })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(succeededJob), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)

    const result = await api.pollJob('job-1', { intervalMs: 1, onUpdate })

    expect(result.status).toBe('succeeded')
    expect(onUpdate).toHaveBeenCalledTimes(2)
    expect(fn).toHaveBeenCalledTimes(2)
    expect(fn).toHaveBeenNthCalledWith(1, '/api/jobs/job-1', expect.any(Object))
    expect(fn).toHaveBeenNthCalledWith(2, '/api/jobs/job-1', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('pollJob respects an already aborted signal', async () => {
    const controller = new AbortController()
    controller.abort()
    const fn = vi.fn()
    vi.stubGlobal('fetch', fn)

    await expect(api.pollJob('job-1', { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
    expect(fn).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('waitForImportJob returns direct ingest responses without polling', async () => {
    const onProgress = vi.fn()
    const response = { chunk_count: 1, total_docs: 1, message: 'ok', existing_version: false }

    await expect(api.waitForImportJob(response, onProgress)).resolves.toBe(response)
    expect(onProgress).not.toHaveBeenCalled()
  })

  it('waitForImportJob polls job responses and maps progress updates', async () => {
    const onProgress = vi.fn()
    const runningJob = { ...queuedJob, status: 'running', progress: { phase: 'embedding', percent: 60, message: '' } }
    const doneJob = { ...succeededJob, progress: { phase: 'done', percent: 100, message: '' } }
    const fn = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(runningJob), text: () => Promise.resolve('{}'), headers: new Headers() })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(doneJob), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)

    const result = await api.waitForImportJob({ job_id: 'job-1', job: queuedJob }, onProgress)

    expect(result).toBeNull()
    expect(onProgress).toHaveBeenCalledWith('queued', 0)
    expect(onProgress).toHaveBeenCalledWith('embedding', 60)
    expect(onProgress).toHaveBeenCalledWith('done', 100)
    vi.unstubAllGlobals()
  })
})

describe('Knowledge Base API', () => {
  it('getKBChunks builds query params', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ items: [], total: 0 }), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.getKBChunks('doc.txt', 'keyword', 10, 20, 'ws-1')
    expect(fn).toHaveBeenCalledWith('/api/knowledge-base/chunks?source=doc.txt&search=keyword&skip=10&limit=20&workspace_id=ws-1', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('getKBChunks without source/search', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ items: [], total: 0 }), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.getKBChunks()
    const calledUrl = fn.mock.calls[0][0] as string
    expect(calledUrl).toContain('skip=0')
    expect(calledUrl).toContain('limit=50')
    expect(calledUrl).not.toContain('source=')
    vi.unstubAllGlobals()
  })

  it('getKBChunkById encodes the chunk id in the path', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.getKBChunkById('doc.txt:1:hash value', 'ws-1')
    expect(fn).toHaveBeenCalledWith('/api/knowledge-base/chunks/doc.txt%3A1%3Ahash%20value?workspace_id=ws-1', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('getKBSourceNames returns list', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(['a.txt']), text: () => Promise.resolve('[]'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    const result = await api.getKBSourceNames('ws-1')
    expect(result).toEqual(['a.txt'])
    expect(fn).toHaveBeenCalledWith('/api/knowledge-base/sources?workspace_id=ws-1', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('getKBConfig returns config', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ chunk_size: 500, chunk_overlap: 50 }), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    const result = await api.getKBConfig()
    expect(result.chunk_size).toBe(500)
    vi.unstubAllGlobals()
  })

  it('getKBHotspots returns list', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([{ chunk_id: 'a', source: 'b', hits: 1, content_preview: 'c' }]), text: () => Promise.resolve('[]'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    const result = await api.getKBHotspots('ws-1')
    expect(result).toHaveLength(1)
    expect(fn).toHaveBeenCalledWith('/api/knowledge-base/hotspots?workspace_id=ws-1', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('getKBStats returns stats', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ chunk_count: 10, source_count: 2, total_chars: 1000 }), text: () => Promise.resolve('{}'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    const result = await api.getKBStats('ws-1')
    expect(result.chunk_count).toBe(10)
    expect(fn).toHaveBeenCalledWith('/api/knowledge-base/stats?workspace_id=ws-1', expect.any(Object))
    vi.unstubAllGlobals()
  })

  it('debugSearch sends search strategy in body', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]), text: () => Promise.resolve('[]'), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.debugSearch('test query', 7, 'deep', 'ws-1')
    expect(fn).toHaveBeenCalledWith(
      '/api/knowledge-base/debug-search?workspace_id=ws-1',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ query: 'test query', k: 7, search_strategy: 'deep' }),
      }),
    )
    vi.unstubAllGlobals()
  })
})

describe('Metrics API', () => {
  it('queryLogs builds query params', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('[]'), json: () => Promise.resolve([]), headers: new Headers() })
    vi.stubGlobal('fetch', fn)
    await api.queryLogs(7, 100)
    expect(fn).toHaveBeenCalledWith('/api/metrics/logs?days=7&limit=100', expect.any(Object))
    vi.unstubAllGlobals()
  })
})

describe('chatStream (SSE)', () => {
  function mockFetchSSE(events: { event: string; data: string }[]) {
    const encoder = new TextEncoder()
    const chunks = events.map(e => encoder.encode(`event: ${e.event}\ndata: ${e.data}\n\n`))
    const stream = new ReadableStream({
      start(controller) {
        chunks.forEach(c => controller.enqueue(c))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => stream.getReader() },
    }))
  }

  it('handles all SSE event types', async () => {
    const callbacks: ChatStreamCallbacks = {
      onNode: vi.fn(),
      onToken: vi.fn(),
      onDebug: vi.fn(),
      onSources: vi.fn(),
      onDone: vi.fn(),
    }

    mockFetchSSE([
      { event: 'node', data: JSON.stringify({ label: '问题路由', nodes: ['问题路由'] }) },
      { event: 'token', data: JSON.stringify({ text: '你好' }) },
      { event: 'debug', data: JSON.stringify({ used_rerank: false }) },
      { event: 'sources', data: JSON.stringify({ sources: [] }) },
      { event: 'done', data: JSON.stringify({ thread_id: 't-1', answer: '你好' }) },
    ])

    api.chatStream('你好', null, false, 'balanced', callbacks)

    // Wait for async processing
    await vi.waitFor(() => {
      expect(callbacks.onNode).toHaveBeenCalled()
    })
    await vi.waitFor(() => {
      expect(callbacks.onToken).toHaveBeenCalled()
    })
    await vi.waitFor(() => {
      expect(callbacks.onDone).toHaveBeenCalled()
    })
    expect(callbacks.onDebug).toHaveBeenCalled()
    expect(callbacks.onSources).toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('calls onError on HTTP error', async () => {
    const onError = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      text: () => Promise.resolve(JSON.stringify({ detail: '请求过于频繁，请在 60 秒后重试。' })),
      headers: new Headers({ 'Retry-After': '60' }),
    }))

    api.chatStream('q', null, false, 'balanced', { onError })

    await vi.waitFor(() => {
      expect(onError).toHaveBeenCalledWith('请求过于频繁，请在 60 秒后重试。')
    })
    vi.unstubAllGlobals()
  })

  it('uploadDocumentStream surfaces parsed 429 messages', async () => {
    const onError = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      text: () => Promise.resolve(JSON.stringify({ detail: '导入过于频繁，请稍后再试。' })),
      headers: new Headers({ 'Retry-After': '60' }),
    }))

    api.uploadDocumentStream(new File(['test'], 'test.txt', { type: 'text/plain' }), undefined, { onError }, 'ws-1')

    await vi.waitFor(() => {
      expect(onError).toHaveBeenCalledWith('导入过于频繁，请稍后再试。')
    })
    vi.unstubAllGlobals()
  })

  it('returns AbortController that can cancel', () => {
    const controller = api.chatStream('q', null, false, 'balanced', {})
    expect(controller).toBeInstanceOf(AbortController)
    controller.abort()
  })

  it('silently skips JSON parse errors in SSE', async () => {
    const onToken = vi.fn()
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    mockFetchSSE([
      { event: 'token', data: '{invalid json' },
    ])

    api.chatStream('q', null, false, 'balanced', { onToken })

    await vi.waitFor(() => {
      // fetch was called, no crash
      expect(vi.mocked(fetch)).toHaveBeenCalled()
    })
    // onToken should NOT be called (parse error silently skipped)
    expect(onToken).not.toHaveBeenCalled()
    expect(warnSpy).not.toHaveBeenCalled()
    warnSpy.mockRestore()
    vi.unstubAllGlobals()
  })

  it('parses CRLF line endings correctly', async () => {
    const callbacks: ChatStreamCallbacks = {
      onNode: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
    }

    // Simulate a real server that sends CRLF — if SSEParser doesn't normalize,
    // events get stuck in the buffer and the last flush() merges them.
    const encoder = new TextEncoder()
    const crlfPayload = 'event: node\r\ndata: {"label":"路由","nodes":["路由"]}\r\n\r\nevent: token\r\ndata: {"text":"hi"}\r\n\r\n'
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(crlfPayload))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => stream.getReader() },
    }))

    api.chatStream('q', null, false, 'balanced', callbacks)

    await vi.waitFor(() => {
      expect(callbacks.onNode).toHaveBeenCalled()
    })
    await vi.waitFor(() => {
      expect(callbacks.onToken).toHaveBeenCalled()
    })
    // Node and token must fire as TWO separate events, not merged into one
    expect(callbacks.onNode).toHaveBeenCalledWith('路由', ['路由'])
    expect(callbacks.onToken).toHaveBeenCalledWith('hi')
    // done should NOT fire (we didn't send one)
    expect(callbacks.onDone).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('handles mixed CR and LF correctly', async () => {
    const callbacks: ChatStreamCallbacks = {
      onToken: vi.fn(),
    }

    // Bare \r (old Mac style) must also be normalized
    const encoder = new TextEncoder()
    const crPayload = 'event: token\rdata: {"text":"ok"}\r\r'
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(crPayload))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => stream.getReader() },
    }))

    api.chatStream('q', null, false, 'balanced', callbacks)

    await vi.waitFor(() => {
      expect(callbacks.onToken).toHaveBeenCalledWith('ok')
    })
    vi.unstubAllGlobals()
  })

  it('passes webSearchEnabled and searchStrategy in body', async () => {
    const mock = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => new ReadableStream({ start(c) { c.close() } }).getReader() },
    })
    vi.stubGlobal('fetch', mock)

    api.chatStream('my question', 'thread-1', true, 'deep', {})
    const callArg = JSON.parse(mock.mock.calls[0][1].body)
    expect(callArg.web_search_enabled).toBe(true)
    expect(callArg.search_strategy).toBe('deep')
    expect(callArg.thread_id).toBe('thread-1')
    vi.unstubAllGlobals()
  })

  it('chatStream sends workspace_id in body', async () => {
    const mock = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => new ReadableStream({ start(c) { c.close() } }).getReader() },
    })
    vi.stubGlobal('fetch', mock)

    api.chatStream('q', 't-1', false, 'balanced', {}, [], [], 'ws-2')
    const callArg = JSON.parse(mock.mock.calls[0][1].body)
    expect(callArg.workspace_id).toBe('ws-2')
    vi.unstubAllGlobals()
  })
})
