import { useEffect, useState } from 'react'

type Theme = 'dark' | 'light'

const KEY = 'knowbase-theme'

function getInitialTheme(): Theme {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem(KEY) as Theme | null
    if (stored === 'light' || stored === 'dark') return stored
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  }
  return 'dark'
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    document.documentElement.classList.toggle('light', theme === 'light')
    localStorage.setItem(KEY, theme)
  }, [theme])

  const toggle = () => setThemeState((t) => (t === 'dark' ? 'light' : 'dark'))

  return { theme, toggle }
}
