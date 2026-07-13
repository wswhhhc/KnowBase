import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useSearchPreferences } from '@/features/chat/hooks/useSearchPreferences'

describe('useSearchPreferences', () => {
  beforeEach(() => localStorage.clear())

  it('hydrates persisted web search and strategy preferences', () => {
    localStorage.setItem('kb_web_search', 'true')
    localStorage.setItem('kb_search_strategy', 'deep')

    const { result } = renderHook(() => useSearchPreferences())

    expect(result.current.webSearch).toBe(true)
    expect(result.current.searchStrategy).toBe('deep')
  })

  it('falls back to the balanced strategy when stored data is invalid', () => {
    localStorage.setItem('kb_search_strategy', 'unsupported')

    const { result } = renderHook(() => useSearchPreferences())

    expect(result.current.webSearch).toBe(false)
    expect(result.current.searchStrategy).toBe('balanced')
  })

  it('persists changes for the next chat session', () => {
    const { result } = renderHook(() => useSearchPreferences())

    act(() => {
      result.current.setWebSearch(true)
      result.current.setSearchStrategy('high_quality')
    })

    expect(localStorage.getItem('kb_web_search')).toBe('true')
    expect(localStorage.getItem('kb_search_strategy')).toBe('high_quality')
  })
})
