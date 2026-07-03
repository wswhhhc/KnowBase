import { toast } from 'sonner'
import { useEffect, useState, useRef, useCallback } from 'react'

import * as api from '@/lib/api'
import type { KBStats, KBChunk, KBConfig, DebugSearchResponse } from '@/lib/api'
import { UPLOAD_TRIGGER_EVENT } from '@/lib/ui-events'

const PAGE_SIZE = 50

interface UseBrowserPageArgs {
  highlightChunkId?: string | null
  onHighlightConsumed?: () => void
  workspaceId?: string
}

function dedupeChunksById(items: KBChunk[]): KBChunk[] {
  const seen = new Set<string>()
  return items.filter((chunk) => {
    if (seen.has(chunk.chunk_id)) return false
    seen.add(chunk.chunk_id)
    return true
  })
}

export function useBrowserPage({
  highlightChunkId,
  onHighlightConsumed,
  workspaceId,
}: UseBrowserPageArgs) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const guideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)
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
  const [hotspotMode, setHotspotMode] = useState(false)
  const [hotspots, setHotspots] = useState<Map<string, number>>(new Map())
  const [kbConfig, setKbConfig] = useState<KBConfig | null>(null)
  const [urlInput, setUrlInput] = useState('')
  const [ingesting, setIngesting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadPhase, setUploadPhase] = useState('')
  const [uploadPercent, setUploadPercent] = useState(0)
  const [versionPrompted, setVersionPrompted] = useState<
    { kind: 'file'; file: File; sourceName: string } |
    { kind: 'url'; url: string; sourceName: string } |
    null
  >(null)
  const [showPostUploadGuide, setShowPostUploadGuide] = useState(false)
  const [lastImportedSource, setLastImportedSource] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [bookmarkedChunks, setBookmarkedChunks] = useState<Set<string>>(new Set())
  const [hasMore, setHasMore] = useState(true)

  const browserWsId = workspaceId || ''
  const nextScopeToken = () => {
    scopeTokenRef.current += 1
    return scopeTokenRef.current
  }
  const isScopeCurrent = (token: number) => scopeTokenRef.current === token

  const setChunksAccumulate = (items: KBChunk[], append: boolean) => {
    allChunksRef.current = dedupeChunksById(append ? [...allChunksRef.current, ...items] : items)
    setChunks([...allChunksRef.current])
  }

  const loadChunks = async (src: string, q: string, p: number, ps: number, append = false, scopeToken = scopeTokenRef.current) => {
    const res = await api.getKBChunks(src, q, p * ps, ps, browserWsId)
    if (!isScopeCurrent(scopeToken)) return null
    setChunksAccumulate(res.items, append)
    setTotal(res.total)
    setHasMore((p + 1) * ps < res.total)
    return res
  }

  const refreshData = useCallback(async () => {
    const scopeToken = scopeTokenRef.current
    try {
      const [s, srcs, cfg, chunkResult] = await Promise.all([
        api.getKBStats(browserWsId),
        api.getKBSourceNames(browserWsId),
        api.getKBConfig(),
        loadChunks(selectedSource, searchQuery, 0, PAGE_SIZE, false, scopeToken),
      ])
      if (!isScopeCurrent(scopeToken) || !chunkResult) return
      setStats(s)
      setSources(srcs)
      setKbConfig(cfg)
      setPage(0)
    } catch (e) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('刷新失败', { description: String(e) })
      }
    }
  }, [browserWsId, selectedSource, searchQuery])

  const focusSource = useCallback(async (sourceName: string) => {
    const scopeToken = scopeTokenRef.current
    setLoading(true)
    setSearchQuery('')
    setSelectedSource(sourceName)
    setSelectedChunk(null)
    setChunkView('slice')
    try {
      const chunkResult = await loadChunks(sourceName, '', 0, PAGE_SIZE, false, scopeToken)
      if (!isScopeCurrent(scopeToken) || !chunkResult) return
      const [srcs, s] = await Promise.all([api.getKBSourceNames(browserWsId), api.getKBStats(browserWsId)])
      if (!isScopeCurrent(scopeToken)) return
      setSources(srcs)
      setStats(s)
      setPage(0)
    } catch (e) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('加载来源失败', { description: String(e) })
      }
    } finally {
      if (isScopeCurrent(scopeToken)) {
        setLoading(false)
      }
    }
  }, [browserWsId])

  const resetBrowseFilters = useCallback(async () => {
    const scopeToken = scopeTokenRef.current
    skipNextSourceSearch.current = true
    setLoading(true)
    setSearchQuery('')
    setSelectedSource('')
    setSelectedChunk(null)
    setChunkView('grid')
    try {
      const chunkResult = await loadChunks('', '', 0, PAGE_SIZE, false, scopeToken)
      if (!isScopeCurrent(scopeToken) || !chunkResult) return
      const [srcs, s] = await Promise.all([api.getKBSourceNames(browserWsId), api.getKBStats(browserWsId)])
      if (!isScopeCurrent(scopeToken)) return
      setSources(srcs)
      setStats(s)
      setPage(0)
    } catch (e) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('重置筛选失败', { description: String(e) })
      }
    } finally {
      if (isScopeCurrent(scopeToken)) {
        setLoading(false)
      }
    }
  }, [browserWsId])

  const handleSearch = useCallback(async () => {
    const scopeToken = scopeTokenRef.current
    setLoading(true)
    setPage(0)
    try {
      const chunkResult = await loadChunks(selectedSource, searchQuery, 0, PAGE_SIZE, false, scopeToken)
      if (!isScopeCurrent(scopeToken) || !chunkResult) return
      const [srcs, s] = await Promise.all([api.getKBSourceNames(browserWsId), api.getKBStats(browserWsId)])
      if (!isScopeCurrent(scopeToken)) return
      setSources(srcs)
      setStats(s)
    } catch (e) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('搜索失败', { description: String(e) })
      }
    } finally {
      if (isScopeCurrent(scopeToken)) {
        setLoading(false)
      }
    }
  }, [browserWsId, searchQuery, selectedSource])

  const handlePageChange = useCallback(async (newPage: number) => {
    const scopeToken = scopeTokenRef.current
    setLoading(true)
    setPage(newPage)
    try {
      await loadChunks(selectedSource, searchQuery, newPage, PAGE_SIZE, true, scopeToken)
    } catch (e) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('翻页失败', { description: String(e) })
      }
    } finally {
      if (isScopeCurrent(scopeToken)) {
        setLoading(false)
      }
    }
  }, [searchQuery, selectedSource])

  const handleSourceClick = useCallback((src: string) => {
    setSelectedSource((prev) => (prev === src ? '' : src))
  }, [])

  const resetProgress = useCallback(() => {
    setUploading(false)
    setIngesting(false)
    setUploadPhase('')
    setUploadPercent(0)
  }, [])

  const startUpload = useCallback(async (file: File, versionMode?: 'replace' | 'append') => {
    const scopeToken = scopeTokenRef.current
    setUploading(true)
    setUploadPhase('loading')
    setUploadPercent(0)
    setVersionPrompted(null)
    try {
      const probe = await api.checkSource(file.name, browserWsId)
      if (!isScopeCurrent(scopeToken)) return
      if (probe.exists && !versionMode) {
        setVersionPrompted({ kind: 'file', file, sourceName: file.name })
        resetProgress()
        return
      }
    } catch {
      if (isScopeCurrent(scopeToken)) {
        toast.error('上传前检查失败')
        resetProgress()
      }
      return
    }
    api.uploadDocumentStream(file, versionMode, {
      onProgress: (phase, pct) => {
        if (!isScopeCurrent(scopeToken)) return
        setUploadPhase(phase)
        setUploadPercent(pct)
      },
      onDone: async (result) => {
        if (!isScopeCurrent(scopeToken)) return
        if (result.existing_version && !versionMode) {
          setVersionPrompted({ kind: 'file', file, sourceName: file.name })
          resetProgress()
          return
        }
        await refreshData()
        if (!isScopeCurrent(scopeToken)) return
        setLastImportedSource(file.name)
        await focusSource(file.name)
        if (!isScopeCurrent(scopeToken)) return
        setShowPostUploadGuide(true)
        if (guideTimerRef.current) clearTimeout(guideTimerRef.current)
        guideTimerRef.current = setTimeout(() => setShowPostUploadGuide(false), 8000)
        toast.success(
          versionMode === 'replace'
            ? '文档已替换为新版本'
            : versionMode === 'append'
              ? '文档已追加新版本'
              : '文档已上传',
          { description: file.name },
        )
        resetProgress()
        if (fileInputRef.current) fileInputRef.current.value = ''
      },
      onError: (msg) => {
        if (!isScopeCurrent(scopeToken)) return
        toast.error('上传失败', { description: msg })
        resetProgress()
        if (fileInputRef.current) fileInputRef.current.value = ''
      },
    }, browserWsId)
  }, [browserWsId, focusSource, refreshData, resetProgress])

  const startUrlIngest = useCallback(async (url: string, versionMode?: 'replace' | 'append') => {
    const scopeToken = scopeTokenRef.current
    setIngesting(true)
    setUploadPhase('loading')
    setUploadPercent(0)
    setVersionPrompted(null)
    try {
      const probe = await api.checkSource(url, browserWsId)
      if (!isScopeCurrent(scopeToken)) return
      if (probe.exists && !versionMode) {
        setVersionPrompted({ kind: 'url', url, sourceName: url })
        resetProgress()
        return
      }
    } catch {
      if (isScopeCurrent(scopeToken)) {
        toast.error('导入前检查失败')
        resetProgress()
      }
      return
    }
    api.ingestUrlStream(url, versionMode, {
      onProgress: (phase, pct) => {
        if (!isScopeCurrent(scopeToken)) return
        setUploadPhase(phase)
        setUploadPercent(pct)
      },
      onDone: async (result) => {
        if (!isScopeCurrent(scopeToken)) return
        if (result.existing_version && !versionMode) {
          setVersionPrompted({ kind: 'url', url, sourceName: url })
          resetProgress()
          return
        }
        setUrlInput('')
        await refreshData()
        if (!isScopeCurrent(scopeToken)) return
        setLastImportedSource(url)
        await focusSource(url)
        if (!isScopeCurrent(scopeToken)) return
        setShowPostUploadGuide(true)
        if (guideTimerRef.current) clearTimeout(guideTimerRef.current)
        guideTimerRef.current = setTimeout(() => setShowPostUploadGuide(false), 8000)
        toast.success(
          versionMode === 'replace'
            ? '网页已替换为新版本'
            : versionMode === 'append'
              ? '网页已追加新版本'
              : '网页已导入',
        )
        resetProgress()
      },
      onError: (msg) => {
        if (!isScopeCurrent(scopeToken)) return
        toast.error('导入失败', { description: msg })
        resetProgress()
      },
    }, browserWsId)
  }, [browserWsId, focusSource, refreshData, resetProgress])

  const toggleHotspotMode = useCallback(async () => {
    const scopeToken = scopeTokenRef.current
    const next = !hotspotMode
    setHotspotMode(next)
    if (!next) {
      setHotspots(new Map())
      return
    }
    if (next) {
      try {
        const data = await api.getKBHotspots(browserWsId)
        if (!isScopeCurrent(scopeToken)) return
        setHotspots(new Map(data.map((h) => [h.chunk_id, h.hits] as [string, number])))
      } catch (e) {
        if (isScopeCurrent(scopeToken)) {
          toast.error('热点数据加载失败', { description: String(e) })
        }
      }
    }
  }, [browserWsId, hotspotMode])

  const hotspotCount = useCallback((chunkId: string) => hotspots.get(chunkId) || 0, [hotspots])

  const findOverlap = useCallback((prev: string, curr: string) => {
    const maxOverlap = kbConfig?.chunk_overlap || 200
    for (let i = Math.min(maxOverlap, prev.length, curr.length); i > 10; i -= 1) {
      if (prev.slice(-i) === curr.slice(0, i)) return i
    }
    return 0
  }, [kbConfig])

  const handleChunkBookmark = useCallback(async (chunk: KBChunk) => {
    if (bookmarkedChunks.has(chunk.chunk_id)) return
    try {
      await api.createBookmark({
        chunk_id: chunk.chunk_id,
        content: chunk.content.slice(0, 500),
        source: chunk.source,
        workspace_id: browserWsId || undefined,
      })
      setBookmarkedChunks((prev) => new Set(prev).add(chunk.chunk_id))
    } catch (e) {
      toast.error('收藏失败', { description: String(e) })
    }
  }, [bookmarkedChunks, browserWsId])

  const runDebugSearch = useCallback(async (query: string, strategy: string): Promise<DebugSearchResponse | null> => {
    const scopeToken = scopeTokenRef.current
    try {
      return await api.debugSearch(query, 5, strategy, browserWsId)
    } catch (e) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('检索测试失败', { description: String(e) })
      }
      return null
    }
  }, [browserWsId])

  useEffect(() => {
    const scopeToken = nextScopeToken()
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
    setHotspotMode(false)
    setHotspots(new Map())
    setKbConfig(null)
    setUrlInput('')
    setVersionPrompted(null)
    setShowPostUploadGuide(false)
    setLastImportedSource(null)
    setPage(0)
    setTotal(0)
    setHasMore(true)
    setBookmarkedChunks(new Set())
    resetProgress()
    if (fileInputRef.current) fileInputRef.current.value = ''
    setError(null)
    setLoading(true)
    Promise.all([
      loadChunks('', '', 0, PAGE_SIZE, false, scopeToken),
      api.getKBStats(browserWsId),
      api.getKBSourceNames(browserWsId),
      api.getKBConfig(),
    ])
      .then(([, s, srcs, cfg]) => {
        if (!isScopeCurrent(scopeToken)) return
        setStats(s)
        setSources(srcs)
        setKbConfig(cfg)
      })
      .catch((e) => {
        if (!isScopeCurrent(scopeToken)) return
        setError(String(e))
        toast.error('加载失败', { description: String(e) })
      })
      .finally(() => {
        if (!isScopeCurrent(scopeToken)) return
        if (sessionStorage.getItem('kb_trigger_upload') === 'true') {
          sessionStorage.removeItem('kb_trigger_upload')
          requestAnimationFrame(() => fileInputRef.current?.click())
        }
        setLoading(false)
      })
  }, [browserWsId, resetProgress])

  useEffect(() => {
    const handler = () => {
      if (sessionStorage.getItem('kb_trigger_upload') === 'true') {
        sessionStorage.removeItem('kb_trigger_upload')
        requestAnimationFrame(() => fileInputRef.current?.click())
      }
    }
    window.addEventListener(UPLOAD_TRIGGER_EVENT, handler)
    return () => window.removeEventListener(UPLOAD_TRIGGER_EVENT, handler)
  }, [])

  useEffect(() => {
    if (!highlightChunkId) return
    const existing = allChunksRef.current.find((c) => c.chunk_id === highlightChunkId)
    if (existing) {
      setSelectedChunk(existing)
      onHighlightConsumed?.()
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const chunk = await api.getKBChunkById(highlightChunkId, browserWsId)
        if (cancelled) return
        allChunksRef.current = dedupeChunksById([chunk, ...allChunksRef.current])
        setChunks([...allChunksRef.current])
        setSelectedChunk(chunk)
        onHighlightConsumed?.()
      } catch (e) {
        toast.error('无法在当前工作区定位该引用', { description: String(e) })
        onHighlightConsumed?.()
      }
    })()
    return () => { cancelled = true }
  }, [browserWsId, highlightChunkId, onHighlightConsumed])

  useEffect(() => {
    if (!didInitSourceFilter.current) {
      didInitSourceFilter.current = true
      return
    }
    if (skipNextSourceSearch.current) {
      skipNextSourceSearch.current = false
      return
    }
    handleSearch()
  }, [handleSearch, selectedSource])

  useEffect(() => {
    if (observerRef.current) observerRef.current.disconnect()
    if (!sentinelRef.current || !hasMore || loading) return
    observerRef.current = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasMore && !loading) handlePageChange(page + 1)
      },
      { rootMargin: '200px' },
    )
    observerRef.current.observe(sentinelRef.current)
    return () => observerRef.current?.disconnect()
  }, [handlePageChange, hasMore, loading, page])

  useEffect(() => () => {
    if (guideTimerRef.current) clearTimeout(guideTimerRef.current)
  }, [])

  const displayChunks = hotspotMode
    ? [...chunks].sort((a, b) => (hotspots.get(b.chunk_id) || 0) - (hotspots.get(a.chunk_id) || 0))
    : chunks

  return {
    fileInputRef,
    scrollRef,
    sentinelRef,
    stats,
    loading,
    error,
    searchQuery,
    setSearchQuery,
    selectedSource,
    setSelectedSource,
    sources,
    selectedChunk,
    setSelectedChunk,
    chunkView,
    setChunkView,
    hotspotMode,
    kbConfig,
    urlInput,
    setUrlInput,
    ingesting,
    uploading,
    uploadPhase,
    uploadPercent,
    versionPrompted,
    setVersionPrompted,
    showPostUploadGuide,
    setShowPostUploadGuide,
    lastImportedSource,
    total,
    hasMore,
    bookmarkedChunks,
    displayChunks,
    hotspotCount,
    findOverlap,
    refreshData,
    handleSearch,
    handleSourceClick,
    focusSource,
    resetBrowseFilters,
    startUpload,
    startUrlIngest,
    toggleHotspotMode,
    handleChunkBookmark,
    runDebugSearch,
  }
}
