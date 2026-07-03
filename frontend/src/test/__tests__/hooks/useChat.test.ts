import { renderHook, act, waitFor } from '@testing-library/react'
import { useChat } from '@/hooks/useChat'
import { createMockSSEStream } from '@/test/mocks/data'

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('useChat', () => {
  const donePayload = {
    thread_id: 'thread-1',
    answer: '这是回答',
    sources: [],
    quality_reason: 'PASS',
    evidence_level: 'strong',
    evidence_summary: '充分',
    outcome_category: 'success',
    elapsed_ms: 500,
  }

  it('sendMessage adds user and assistant messages, marks assistant as streaming', async () => {
    const stream = createMockSSEStream([
      { event: 'token', data: JSON.stringify({ text: '这是' }) },
      { event: 'token', data: JSON.stringify({ text: '回答' }) },
      { event: 'done', data: JSON.stringify(donePayload) },
    ])

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
      headers: new Headers(),
    }))

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage('你好', false, 'balanced')
    })

    // After send, user and assistant messages should exist; assistant is streaming
    await waitFor(() => {
      expect(result.current.messages.length).toBeGreaterThanOrEqual(2)
    })

    expect(result.current.messages[0].role).toBe('user')
    expect(result.current.messages[0].content).toBe('你好')
    expect(result.current.messages[1].role).toBe('assistant')
    expect(result.current.messages[1].searchStrategy).toBe('balanced')
    expect(result.current.messages[1].webSearchEnabled).toBe(false)
  })

  it('onDone finalizes message with streaming=false and correct content', async () => {
    const stream = createMockSSEStream([
      { event: 'token', data: JSON.stringify({ text: '这是回答' }) },
      { event: 'sources', data: JSON.stringify({ sources: [], quality_reason: 'PASS', evidence_level: 'strong', evidence_summary: '充分', outcome_category: 'success' }) },
      { event: 'done', data: JSON.stringify(donePayload) },
    ])

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
      headers: new Headers(),
    }))

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage('你好', false, 'balanced')
    })

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false)
    })

    const assistantMsg = result.current.messages[1]
    expect(assistantMsg.role).toBe('assistant')
    expect(assistantMsg.streaming).toBeFalsy()
    expect(assistantMsg.content).toBeTruthy()
    expect(assistantMsg.elapsedMs).toBe(500)
  })

  it('onError sets error content', async () => {
    const stream = createMockSSEStream([
      { event: 'error', data: JSON.stringify({ message: '服务器错误' }) },
    ])

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
      headers: new Headers(),
    }))

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage('你好', false, 'balanced')
    })

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false)
    })

    const assistantMsg = result.current.messages[1]
    expect(assistantMsg.content).toContain('错误：')
  })

  it('shows a clear error when chat stream receives HTTP 429', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      text: () => Promise.resolve(JSON.stringify({ detail: '请求过于频繁，请在 60 秒后重试。' })),
      headers: new Headers({ 'Retry-After': '60' }),
    }))

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage('你好', false, 'balanced')
    })

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false)
    })

    expect(result.current.messages[1].content).toContain('请求过于频繁，请在 60 秒后重试。')
  })

  it('stopStreaming aborts and resets streaming state', async () => {
    // Create a stream that never ends to keep streaming active
    const stream = new ReadableStream({
      start(controller) {
        // Don't close - keep streaming indefinitely
      },
    })

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
      headers: new Headers(),
    }))

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage('你好', false, 'balanced')
    })

    // Should be streaming
    await waitFor(() => {
      expect(result.current.isStreaming).toBe(true)
    })

    act(() => {
      result.current.stopStreaming()
    })

    expect(result.current.isStreaming).toBe(false)
    expect(result.current.messages[1].streaming).toBeFalsy()
  })

  it('clearMessages clears all state', async () => {
    const stream = createMockSSEStream([
      { event: 'token', data: JSON.stringify({ text: '回答' }) },
      { event: 'done', data: JSON.stringify(donePayload) },
    ])

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
      headers: new Headers(),
    }))

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage('你好', false, 'balanced')
    })

    await waitFor(() => {
      expect(result.current.messages.length).toBeGreaterThan(0)
    })

    act(() => {
      result.current.clearMessages()
    })

    expect(result.current.messages).toEqual([])
    expect(result.current.isStreaming).toBe(false)
  })

  it('loadMessages loads history', () => {
    const { result } = renderHook(() => useChat())

    const mockMessages = [
      { id: '1', role: 'user' as const, content: '你好' },
      { id: '2', role: 'assistant' as const, content: '你好！' },
    ]

    act(() => {
      result.current.loadMessages(mockMessages, 'thread-1')
    })

    expect(result.current.messages).toEqual(mockMessages)
  })

  it('loadMessages prefers dedicated pin state over debug_info', () => {
    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.loadMessages(
        [
          {
            id: '2',
            role: 'assistant',
            content: '你好！',
            sources: [{ chunk_id: 'doc.txt:0:a', source: 'doc.txt', content: 'chunk A', score: 0.9, index: 1 }],
            debugData: { pinned: [], excluded: ['doc.txt:0:a'] } as any,
          },
        ],
        'thread-1',
        { thread_id: 'thread-1', pinned_chunk_ids: ['doc.txt:0:a'], excluded_chunk_ids: [] },
      )
    })

    expect(result.current.pinnedSources).toHaveLength(1)
    expect(result.current.pinnedSources[0].pinned).toBe(true)
    expect(result.current.pinnedSources[0].excluded).toBe(false)
  })

  describe('pinned / excluded source isolation', () => {
    const sourceMsg = {
      id: 'm1', role: 'assistant' as const, content: '回答',
      sources: [{ chunk_id: 'doc.txt:0:a', source: 'doc.txt', content: 'chunk A', score: 0.9, index: 1 }],
    }

    it('pinned_chunk_ids and excluded_chunk_ids sent in fetch body', async () => {
      // 1. Simulate a chat that returns sources
      const donePayload = {
        thread_id: 'thread-pin',
        answer: '回答',
        sources: [{ chunk_id: 'doc.txt:0:a', source: 'doc.txt', content: 'chunk A', score: 0.9, index: 1 }],
        quality_reason: 'PASS', evidence_level: 'strong', evidence_summary: '充分', outcome_category: 'success', elapsed_ms: 100,
      }
      const stream = createMockSSEStream([
        { event: 'done', data: JSON.stringify(donePayload) },
      ])
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, body: stream, headers: new Headers() })
      vi.stubGlobal('fetch', fetchMock)

      const { result } = renderHook(() => useChat())
      await act(async () => { await result.current.sendMessage('q', false, 'balanced') })

      // Wait for stream to finish
      await waitFor(() => expect(result.current.isStreaming).toBe(false))

      // 2. Pin the source
      act(() => {
        result.current.setPinnedSources((prev) =>
          prev.map((ps) => (ps.chunk_id === 'doc.txt:0:a' ? { ...ps, pinned: true } : ps)),
        )
      })

      // 3. Send another message — fetch body should include pinned_chunk_ids
      const stream2 = createMockSSEStream([
        { event: 'done', data: JSON.stringify({ thread_id: 'thread-pin', answer: '回答2', sources: [], quality_reason: 'PASS', evidence_level: 'strong', evidence_summary: '充分', outcome_category: 'success', elapsed_ms: 10 }) },
      ])
      const fetchMock2 = vi.fn().mockResolvedValue({ ok: true, body: stream2, headers: new Headers() })
      vi.stubGlobal('fetch', fetchMock2)

      await act(async () => { await result.current.sendMessage('q2', false, 'balanced') })
      await waitFor(() => expect(result.current.isStreaming).toBe(false))

      const lastCallBody = JSON.parse(fetchMock2.mock.calls[0][1].body)
      expect(lastCallBody.pinned_chunk_ids).toContain('doc.txt:0:a')
      vi.unstubAllGlobals()
    })

    it('sends the latest workspace_id in fetch body after workspace switch', async () => {
      const stream = createMockSSEStream([
        {
          event: 'done',
          data: JSON.stringify({
            thread_id: 'thread-ws',
            answer: '回答',
            sources: [],
            quality_reason: 'PASS',
            evidence_level: 'strong',
            evidence_summary: '充分',
            outcome_category: 'success',
            elapsed_ms: 10,
          }),
        },
      ])
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, body: stream, headers: new Headers() })
      vi.stubGlobal('fetch', fetchMock)

      const { result } = renderHook(() => useChat())

      act(() => {
        result.current.setWorkspaceId('ws-2')
      })

      await act(async () => {
        await result.current.sendMessage('q', false, 'balanced')
      })
      await waitFor(() => expect(result.current.isStreaming).toBe(false))

      const lastCallBody = JSON.parse(fetchMock.mock.calls[0][1].body)
      expect(lastCallBody.workspace_id).toBe('ws-2')
      vi.unstubAllGlobals()
    })

    it('pinnedSources are isolated between conversations', async () => {
      const { result } = renderHook(() => useChat())

      // Load conversation A with a source
      act(() => {
        result.current.loadMessages([
          { id: '1', role: 'user' as const, content: 'hi' },
          sourceMsg,
        ], 'thread-a')
      })

      expect(result.current.pinnedSources.length).toBeGreaterThan(0)
      const pinnedInA = result.current.pinnedSources.length

      // Load conversation B — pinnedSources should be empty (different conversation)
      act(() => {
        result.current.loadMessages([
          { id: '1', role: 'user' as const, content: 'hello' },
        ], 'thread-b')
      })

      expect(result.current.pinnedSources).toEqual([])
    })
  })

  it('blocks concurrent sendMessage when isStreaming', async () => {
    const stream = new ReadableStream({
      start(controller) {
        // Keep alive so streaming stays active
      },
    })

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
      headers: new Headers(),
    }))

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage('first', false, 'balanced')
    })

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(true)
    })

    // Try to send again while streaming
    act(() => {
      result.current.sendMessage('second', false, 'balanced')
    })

    // fetch should only have been called once
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1)
  })
})
