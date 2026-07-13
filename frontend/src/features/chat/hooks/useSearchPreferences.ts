import { useEffect, useState } from 'react'
import { FileSearch, Scale, Search, Zap } from 'lucide-react'

export const SEARCH_STRATEGIES = [
  { key: 'fast', icon: Zap, label: '快速', description: '快速回答：不重排，最快响应。适合简单事实性问题' },
  { key: 'balanced', icon: Scale, label: '标准', description: '标准模式：智能判断是否需要重排。适合大多数情况' },
  { key: 'high_quality', icon: FileSearch, label: '严谨', description: '严谨模式：强制重排+质量检查。质量优先，速度次之' },
  { key: 'deep', icon: Search, label: '深度', description: '深度检索：扩检索+综合回答。需要全面覆盖时使用' },
] as const

export type SearchStrategy = typeof SEARCH_STRATEGIES[number]['key']

const DEFAULT_SEARCH_STRATEGY: SearchStrategy = 'balanced'

function isSearchStrategy(value: string): value is SearchStrategy {
  return SEARCH_STRATEGIES.some(({ key }) => key === value)
}

export function useSearchPreferences() {
  const [webSearch, setWebSearch] = useState(() => localStorage.getItem('kb_web_search') === 'true')
  const [searchStrategy, setSearchStrategy] = useState<SearchStrategy>(() => {
    const stored = localStorage.getItem('kb_search_strategy')
    return stored && isSearchStrategy(stored) ? stored : DEFAULT_SEARCH_STRATEGY
  })

  useEffect(() => {
    localStorage.setItem('kb_web_search', String(webSearch))
  }, [webSearch])

  useEffect(() => {
    localStorage.setItem('kb_search_strategy', searchStrategy)
  }, [searchStrategy])

  return { webSearch, setWebSearch, searchStrategy, setSearchStrategy }
}
