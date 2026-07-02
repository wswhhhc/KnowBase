import { renderHook, act, waitFor } from '@testing-library/react'
import { useConversations, useSources } from '@/hooks/useData'
import * as api from '@/lib/api'
import { mockConversations, mockSources } from '@/test/mocks/data'

vi.mock('@/lib/api', () => ({
  getConversations: vi.fn(),
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
  renameConversation: vi.fn(),
  getSources: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useConversations', () => {
  it('loads conversations on mount', async () => {
    vi.mocked(api.getConversations).mockResolvedValue(mockConversations)

    const { result } = renderHook(() => useConversations())

    // Wait for loading to finish
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.conversations).toEqual(mockConversations)
  })

  it('create creates conversation, refreshes list, sets activeId', async () => {
    vi.mocked(api.getConversations).mockResolvedValue(mockConversations)
    vi.mocked(api.createConversation).mockResolvedValue(mockConversations[0])

    const { result } = renderHook(() => useConversations())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      const conv = await result.current.create()
      expect(conv).toEqual(mockConversations[0])
    })

    expect(result.current.activeId).toBe('conv-1')
  })

  it('remove deletes, refreshes, clears activeId if matches', async () => {
    vi.mocked(api.getConversations).mockResolvedValue(mockConversations)
    vi.mocked(api.deleteConversation).mockResolvedValue(undefined)

    const { result } = renderHook(() => useConversations())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    // Set activeId to conv-1
    act(() => {
      result.current.setActiveId('conv-1')
    })

    expect(result.current.activeId).toBe('conv-1')

    // Reset mock to return updated (empty) list after delete
    vi.mocked(api.getConversations).mockResolvedValue([])

    await act(async () => {
      await result.current.remove('conv-1')
    })

    expect(api.deleteConversation).toHaveBeenCalledWith('conv-1')
    expect(result.current.activeId).toBeNull()
  })

  it('rename calls api and refreshes', async () => {
    vi.mocked(api.getConversations).mockResolvedValue(mockConversations)
    vi.mocked(api.renameConversation).mockResolvedValue(mockConversations[0])

    const { result } = renderHook(() => useConversations())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.rename('conv-1', '新标题')
    })

    expect(api.renameConversation).toHaveBeenCalledWith('conv-1', '新标题')
  })
})

describe('useSources', () => {
  it('loads sources after refresh', async () => {
    vi.mocked(api.getSources).mockResolvedValue(mockSources)

    const { result } = renderHook(() => useSources('ws-1'))

    // useSources does not auto-load on mount; need to call refresh
    await act(async () => {
      await result.current.refresh()
    })

    expect(result.current.sources).toEqual(mockSources)
    expect(api.getSources).toHaveBeenCalledWith('ws-1')
  })

  it('refresh catches error and does not throw', async () => {
    vi.mocked(api.getSources).mockRejectedValue(new Error('network error'))

    const { result } = renderHook(() => useSources('ws-1'))

    await act(async () => {
      // Should not throw
      await result.current.refresh()
    })

    expect(result.current.sources).toEqual([])
    expect(api.getSources).toHaveBeenCalledWith('ws-1')
  })

  it('clears stale sources and replaces them when the workspace changes', async () => {
    const ws2Sources = [{ source: 'beta.txt', count: 2 }]
    let resolveWs2Sources: ((value: typeof ws2Sources) => void) | undefined

    vi.mocked(api.getSources).mockImplementation((workspaceId?: string) => {
      if (workspaceId === 'ws-2') {
        return new Promise((resolve) => {
          resolveWs2Sources = resolve
        }) as ReturnType<typeof api.getSources>
      }
      return Promise.resolve(mockSources)
    })

    const { result, rerender } = renderHook(
      ({ workspaceId }) => useSources(workspaceId),
      { initialProps: { workspaceId: 'ws-1' as string | undefined } },
    )

    await waitFor(() => {
      expect(result.current.sources).toEqual(mockSources)
    })

    rerender({ workspaceId: 'ws-2' })

    expect(result.current.sources).toEqual([])

    await act(async () => {
      resolveWs2Sources?.(ws2Sources)
    })

    await waitFor(() => {
      expect(result.current.sources).toEqual(ws2Sources)
    })
  })

  it('ignores stale source responses from the previous workspace', async () => {
    const ws1Sources = [{ source: 'alpha.txt', count: 1 }]
    const ws2Sources = [{ source: 'beta.txt', count: 2 }]
    let resolveWs1Sources: ((value: typeof ws1Sources) => void) | undefined
    let resolveWs2Sources: ((value: typeof ws2Sources) => void) | undefined

    vi.mocked(api.getSources).mockImplementation((workspaceId?: string) => {
      if (workspaceId === 'ws-1') {
        return new Promise((resolve) => {
          resolveWs1Sources = resolve
        }) as ReturnType<typeof api.getSources>
      }
      return new Promise((resolve) => {
        resolveWs2Sources = resolve
      }) as ReturnType<typeof api.getSources>
    })

    const { result, rerender } = renderHook(
      ({ workspaceId }) => useSources(workspaceId),
      { initialProps: { workspaceId: 'ws-1' as string | undefined } },
    )

    rerender({ workspaceId: 'ws-2' })

    await act(async () => {
      resolveWs2Sources?.(ws2Sources)
    })

    await waitFor(() => {
      expect(result.current.sources).toEqual(ws2Sources)
    })

    await act(async () => {
      resolveWs1Sources?.(ws1Sources)
    })

    await waitFor(() => {
      expect(result.current.sources).toEqual(ws2Sources)
    })
  })
})

describe('useConversations error paths', () => {
  it('create failure does not break state', async () => {
    vi.mocked(api.getConversations).mockResolvedValue([])
    vi.mocked(api.createConversation).mockRejectedValue(new Error('create failed'))

    const { result } = renderHook(() => useConversations())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      try {
        await result.current.create()
      } catch {
        // expected
      }
    })
    // Should keep existing conversations
    expect(result.current.conversations).toEqual([])
  })

  it('remove when activeId differs does not clear', async () => {
    const initialConvs = [{ id: 'conv-1', thread_id: 't1', title: 'A', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }]
    vi.mocked(api.getConversations).mockResolvedValue(initialConvs)
    vi.mocked(api.deleteConversation).mockResolvedValue(undefined)

    const { result } = renderHook(() => useConversations())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    act(() => {
      result.current.setActiveId('conv-1')
    })

    vi.mocked(api.getConversations).mockResolvedValue([])

    await act(async () => {
      await result.current.remove('conv-2')  // different id
    })

    expect(result.current.activeId).toBe('conv-1')  // not cleared
  })
})
