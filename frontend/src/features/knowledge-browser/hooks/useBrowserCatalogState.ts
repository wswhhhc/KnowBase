import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import * as api from '@/shared/api'
import type { DebugSearchResponse, KBChunk, KBConfig, KBStats } from '@/shared/api'

const PAGE_SIZE = 50

function dedupeChunksById(items: KBChunk[]): KBChunk[] {
  const seen = new Set<string>()
  return items.filter((chunk) => {
    if (seen.has(chunk.chunk_id)) return false
    seen.add(chunk.chunk_id)
    return true
  })
}

interface UseBrowserCatalogStateArgs {
  browserWsId: string
}

export function useBrowserCatalogState({ browserWsId }: UseBrowserCatalogStateArgs) {
  const allChunksRef = useRef<KBChunk[]>([])
  const didInitSourceFilter = useRef(false)
  const skipNextSourceSearch = useRef(false)
  const scopeTokenRef = useRef(0)

  const [stats, setStats] = useState<KBStats | null>(null)
  const [chunks, setChunks] = useState<KBChunk[]>([])
  const [sources, setSources] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSource, setSelectedSource] = useState('')
  const [selectedChunk, setSelectedChunk] = useState<KBChunk | null>(null)
  const [chunkView, setChunkView] = useState<'grid' | 'slice'>('grid')
  const [kbConfig, setKbConfig] = useState<KBConfig | null>(null)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [bookmarkedChunks, setBookmarkedChunks] = useState<Set<string>>(new Set())
  const [hasMore, setHasMore] = useState(true)

  const nextScopeToken = useCallback(() => {
    scopeTokenRef.current += 1
    return scopeTokenRef.current
  }, [])

  const getScopeToken = useCallback(() => scopeTokenRef.current, [])
  const isScopeCurrent = useCallback((token: number) => scopeTokenRef.current === token, [])

  const setChunksAccumulate = useCallback((items: KBChunk[], append: boolean) => {
    allChunksRef.current = dedupeChunksById(append ? [...allChunksRef.current, ...items] : items)
    setChunks([...allChunksRef.current])
  }, [])

  const loadChunks = useCallback(async (
    sourceName: string,
    query: string,
    nextPage: number,
    pageSize: number,
    append = false,
    scopeToken = scopeTokenRef.current,
  ) => {
    const result = await api.getKBChunks(sourceName, query, nextPage * pageSize, pageSize, browserWsId)
    if (!isScopeCurrent(scopeToken)) return null
    setChunksAccumulate(result.items, append)
    setTotal(result.total)
    setHasMore((nextPage + 1) * pageSize < result.total)
    return result
  }, [browserWsId, isScopeCurrent, setChunksAccumulate])

  const refreshData = useCallback(async () => {
    const scopeToken = getScopeToken()
    try {
      const [nextStats, nextSources, nextConfig, chunkResult] = await Promise.all([
        api.getKBStats(browserWsId),
        api.getKBSourceNames(browserWsId),
        api.getKBConfig(),
        loadChunks(selectedSource, searchQuery, 0, PAGE_SIZE, false, scopeToken),
      ])
      if (!isScopeCurrent(scopeToken) || !chunkResult) return
      setStats(nextStats)
      setSources(nextSources)
      setKbConfig(nextConfig)
      setPage(0)
    } catch (errorValue) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('刷新失败', { description: String(errorValue) })
      }
    }
  }, [browserWsId, getScopeToken, isScopeCurrent, loadChunks, searchQuery, selectedSource])

  const focusSource = useCallback(async (sourceName: string) => {
    const scopeToken = getScopeToken()
    setLoading(true)
    setSearchQuery('')
    setSelectedSource(sourceName)
    setSelectedChunk(null)
    setChunkView('slice')

    try {
      const chunkResult = await loadChunks(sourceName, '', 0, PAGE_SIZE, false, scopeToken)
      if (!isScopeCurrent(scopeToken) || !chunkResult) return
      const [nextSources, nextStats] = await Promise.all([
        api.getKBSourceNames(browserWsId),
        api.getKBStats(browserWsId),
      ])
      if (!isScopeCurrent(scopeToken)) return
      setSources(nextSources)
      setStats(nextStats)
      setPage(0)
    } catch (errorValue) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('加载来源失败', { description: String(errorValue) })
      }
    } finally {
      if (isScopeCurrent(scopeToken)) {
        setLoading(false)
      }
    }
  }, [browserWsId, getScopeToken, isScopeCurrent, loadChunks])

  const resetBrowseFilters = useCallback(async () => {
    const scopeToken = getScopeToken()
    skipNextSourceSearch.current = true
    setLoading(true)
    setSearchQuery('')
    setSelectedSource('')
    setSelectedChunk(null)
    setChunkView('grid')

    try {
      const chunkResult = await loadChunks('', '', 0, PAGE_SIZE, false, scopeToken)
      if (!isScopeCurrent(scopeToken) || !chunkResult) return
      const [nextSources, nextStats] = await Promise.all([
        api.getKBSourceNames(browserWsId),
        api.getKBStats(browserWsId),
      ])
      if (!isScopeCurrent(scopeToken)) return
      setSources(nextSources)
      setStats(nextStats)
      setPage(0)
    } catch (errorValue) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('重置筛选失败', { description: String(errorValue) })
      }
    } finally {
      if (isScopeCurrent(scopeToken)) {
        setLoading(false)
      }
    }
  }, [browserWsId, getScopeToken, isScopeCurrent, loadChunks])

  const handleSearch = useCallback(async () => {
    const scopeToken = getScopeToken()
    setLoading(true)
    setPage(0)

    try {
      const chunkResult = await loadChunks(selectedSource, searchQuery, 0, PAGE_SIZE, false, scopeToken)
      if (!isScopeCurrent(scopeToken) || !chunkResult) return
      const [nextSources, nextStats] = await Promise.all([
        api.getKBSourceNames(browserWsId),
        api.getKBStats(browserWsId),
      ])
      if (!isScopeCurrent(scopeToken)) return
      setSources(nextSources)
      setStats(nextStats)
    } catch (errorValue) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('搜索失败', { description: String(errorValue) })
      }
    } finally {
      if (isScopeCurrent(scopeToken)) {
        setLoading(false)
      }
    }
  }, [browserWsId, getScopeToken, isScopeCurrent, loadChunks, searchQuery, selectedSource])

  const handlePageChange = useCallback(async (nextPage: number) => {
    const scopeToken = getScopeToken()
    setLoading(true)
    setPage(nextPage)

    try {
      await loadChunks(selectedSource, searchQuery, nextPage, PAGE_SIZE, true, scopeToken)
    } catch (errorValue) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('翻页失败', { description: String(errorValue) })
      }
    } finally {
      if (isScopeCurrent(scopeToken)) {
        setLoading(false)
      }
    }
  }, [getScopeToken, isScopeCurrent, loadChunks, searchQuery, selectedSource])

  const handleSourceClick = useCallback((sourceName: string) => {
    setSelectedSource((previous) => (previous === sourceName ? '' : sourceName))
  }, [])

  const handleChunkBookmark = useCallback(async (chunk: KBChunk) => {
    if (bookmarkedChunks.has(chunk.chunk_id)) return

    try {
      await api.createBookmark({
        chunk_id: chunk.chunk_id,
        content: chunk.content.slice(0, 500),
        source: chunk.source,
        workspace_id: browserWsId || undefined,
      })
      setBookmarkedChunks((previous) => new Set(previous).add(chunk.chunk_id))
    } catch (errorValue) {
      toast.error('收藏失败', { description: String(errorValue) })
    }
  }, [bookmarkedChunks, browserWsId])

  const runDebugSearch = useCallback(async (query: string, strategy: string): Promise<DebugSearchResponse | null> => {
    const scopeToken = getScopeToken()
    try {
      return await api.debugSearch(query, 5, strategy, browserWsId)
    } catch (errorValue) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('检索测试失败', { description: String(errorValue) })
      }
      return null
    }
  }, [browserWsId, getScopeToken, isScopeCurrent])

  const resetCatalogState = useCallback(() => {
    skipNextSourceSearch.current = true
    allChunksRef.current = []
    setChunks([])
    setStats(null)
    setSources([])
    setError(null)
    setSelectedSource('')
    setSearchQuery('')
    setSelectedChunk(null)
    setChunkView('grid')
    setKbConfig(null)
    setPage(0)
    setTotal(0)
    setHasMore(true)
    setBookmarkedChunks(new Set())
  }, [])

  const loadInitialCatalogData = useCallback(async (scopeToken: number) => {
    const [chunkResult, nextStats, nextSources, nextConfig] = await Promise.all([
      loadChunks('', '', 0, PAGE_SIZE, false, scopeToken),
      api.getKBStats(browserWsId),
      api.getKBSourceNames(browserWsId),
      api.getKBConfig(),
    ])
    if (!isScopeCurrent(scopeToken) || !chunkResult) return false

    setStats(nextStats)
    setSources(nextSources)
    setKbConfig(nextConfig)
    return true
  }, [browserWsId, isScopeCurrent, loadChunks])

  useEffect(() => {
    if (!didInitSourceFilter.current) {
      didInitSourceFilter.current = true
      return
    }
    if (skipNextSourceSearch.current) {
      skipNextSourceSearch.current = false
      return
    }
    void handleSearch()
  }, [handleSearch, selectedSource])

  const findOverlap = useCallback((previousChunk: string, currentChunk: string) => {
    const maxOverlap = kbConfig?.chunk_overlap || 200
    for (let index = Math.min(maxOverlap, previousChunk.length, currentChunk.length); index > 10; index -= 1) {
      if (previousChunk.slice(-index) === currentChunk.slice(0, index)) return index
    }
    return 0
  }, [kbConfig])

  return {
    allChunksRef,
    bookmarkedChunks,
    chunkView,
    chunks,
    dedupeChunksById,
    error,
    findOverlap,
    focusSource,
    getScopeToken,
    handleChunkBookmark,
    handlePageChange,
    handleSearch,
    handleSourceClick,
    hasMore,
    isScopeCurrent,
    kbConfig,
    loadChunks,
    loadInitialCatalogData,
    loading,
    nextScopeToken,
    page,
    refreshData,
    resetBrowseFilters,
    resetCatalogState,
    runDebugSearch,
    searchQuery,
    selectedChunk,
    selectedSource,
    setChunkView,
    setChunks,
    setError,
    setLoading,
    setSearchQuery,
    setSelectedChunk,
    setSelectedSource,
    stats,
    sources,
    total,
  }
}
