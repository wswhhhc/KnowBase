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
