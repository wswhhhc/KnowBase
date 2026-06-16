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

    const { result } = renderHook(() => useSources())

    // useSources does not auto-load on mount; need to call refresh
    await act(async () => {
      await result.current.refresh()
    })

    expect(result.current.sources).toEqual(mockSources)
  })
})
