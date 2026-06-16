import { renderHook, act } from '@testing-library/react'
import { useTheme } from '@/hooks/useTheme'

beforeEach(() => {
  localStorage.clear()
})

describe('useTheme', () => {
  it('reads initial theme from localStorage', () => {
    localStorage.setItem('knowbase-theme', 'light')

    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe('light')
  })

  it('toggles theme from dark to light', () => {
    localStorage.setItem('knowbase-theme', 'dark')

    const { result } = renderHook(() => useTheme())

    act(() => {
      result.current.toggle()
    })

    expect(result.current.theme).toBe('light')
  })

  it('updates localStorage on toggle', () => {
    localStorage.setItem('knowbase-theme', 'dark')

    const { result } = renderHook(() => useTheme())

    act(() => {
      result.current.toggle()
    })

    expect(localStorage.getItem('knowbase-theme')).toBe('light')
  })

  it('respects prefers-color-scheme when no stored value', () => {
    // Set matchMedia to report light preference
    window.matchMedia = ((query: string) => ({
      matches: query === '(prefers-color-scheme: light)',
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })) as typeof window.matchMedia

    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe('light')
  })
})
