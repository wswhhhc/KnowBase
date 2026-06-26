import { toast } from 'sonner'
import { useEffect, useState, useRef } from 'react'
import { Button, Input, ScrollArea, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, SkeletonGrid } from '@/components/ui'
import { BookOpen, PanelRightOpen, ArrowLeft, Search, FileText, Hash, ExternalLink, Layers, Flame, List, LayoutGrid, Upload, Globe, RefreshCw, Bookmark, BookmarkCheck, AlertTriangle, Bug, Loader2 } from 'lucide-react'
import * as api from '@/lib/api'
import type { KBStats, KBChunk, KBConfig, DebugSearchResponse, DebugSearchHit } from '@/lib/api'
import { motion, AnimatePresence } from 'framer-motion'
import type { ViewType } from '@/App'
import { Separator, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui'

interface BrowserPageProps {
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
  highlightChunkId?: string | null
  onHighlightConsumed?: () => void
  workspaceId?: string
}

type VersionPrompt =
  | { kind: 'file'; file: File; sourceName: string }
  | { kind: 'url'; url: string; sourceName: string }

export default function BrowserPage({ onOpenSidebar, sidebarOpen, onNavigate, highlightChunkId, onHighlightConsumed, workspaceId }: BrowserPageProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const didInitSourceFilterRef = useRef(false)
  const skipNextSourceSearchRef = useRef(false)
  const [stats, setStats] = useState<KBStats | null>(null)
  const [chunks, setChunks] = useState<KBChunk[]>([])
  const [sources, setSources] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSource, setSelectedSource] = useState('')
  const [selectedChunk, setSelectedChunk] = useState<KBChunk | null>(null)
  const [highlightId, setHighlightId] = useState<string | null>(null)
  const [chunkView, setChunkView] = useState<'grid' | 'slice'>('grid')
  const [hotspotMode, setHotspotMode] = useState(false)
  const [hotspots, setHotspots] = useState<Map<string, number>>(new Map())
  const [kbConfig, setKbConfig] = useState<KBConfig | null>(null)
  const [urlInput, setUrlInput] = useState('')
  const [ingesting, setIngesting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadPhase, setUploadPhase] = useState('')
  const [uploadPercent, setUploadPercent] = useState(0)
  const [versionPrompted, setVersionPrompted] = useState<VersionPrompt | null>(null)
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugQuery, setDebugQuery] = useState('')
  const [debugResults, setDebugResults] = useState<DebugSearchResponse | null>(null)
  const [debugSearching, setDebugSearching] = useState(false)
  const [debugStrategy, setDebugStrategy] = useState<'fast' | 'balanced' | 'high_quality' | 'deep'>('balanced')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [bookmarkedChunks, setBookmarkedChunks] = useState<Set<string>>(new Set())
  const browserWsId = workspaceId || ''
  const pageSize = 50
  const allChunksRef = useRef<KBChunk[]>([])
  const [hasMore, setHasMore] = useState(true)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)

  // Replace chunks setter with accumulation
  const setChunksAccumulate = (items: KBChunk[], append: boolean) => {
    if (append) {
      allChunksRef.current = [...allChunksRef.current, ...items]
    } else {
      allChunksRef.current = items
    }
    setChunks([...allChunksRef.current])
  }

  const handleChunkBookmark = async (chunk: KBChunk) => {
    if (bookmarkedChunks.has(chunk.chunk_id)) return
    try {
      await api.createBookmark({
        chunk_id: chunk.chunk_id,
        content: chunk.content.slice(0, 500),
        source: chunk.source,
        workspace_id: browserWsId || undefined,
      })
      setBookmarkedChunks((prev) => new Set(prev).add(chunk.chunk_id))
    } catch (e) { toast.error('收藏失败', { description: String(e) }) }
  }

  const loadChunks = async (src: string, q: string, p: number, ps: number, append = false) => {
    const res = await api.getKBChunks(src, q, p * ps, ps)
    setChunksAccumulate(res.items, append)
    setTotal(res.total)
    setHasMore((p + 1) * ps < res.total)
    return res
  }

  useEffect(() => {
    setError(null)
    setLoading(true)
    Promise.all([
      loadChunks('', '', 0, pageSize),
      api.getKBStats(),
      api.getKBSourceNames(),
      api.getKBConfig(),
    ])
      .then(([, s, srcs, cfg]) => { setStats(s); setSources(srcs); setKbConfig(cfg) })
      .catch((e) => { setError(String(e)); toast.error('加载失败', { description: String(e) }) })
      .finally(() => setLoading(false))
  }, [])

  // Load additional chunk pages when a citation points beyond the first page.
  useEffect(() => {
    if (!highlightChunkId) return

    const existing = allChunksRef.current.find((chunk) => chunk.chunk_id === highlightChunkId)
    if (existing) {
      setHighlightId(highlightChunkId)
      return
    }

    let cancelled = false

    const revealHighlightedChunk = async () => {
      setLoading(true)
      if (selectedSource) {
        skipNextSourceSearchRef.current = true
        setSelectedSource('')
      }
      setSearchQuery('')

      try {
        const loaded: KBChunk[] = []
        let currentPage = 0

        while (!cancelled) {
          const res = await api.getKBChunks('', '', currentPage * pageSize, pageSize)
          loaded.push(...res.items)

          const found = loaded.find((chunk) => chunk.chunk_id === highlightChunkId)
          if (found) {
            allChunksRef.current = loaded
            setChunks([...loaded])
            setTotal(res.total)
            setPage(currentPage)
            setHasMore((currentPage + 1) * pageSize < res.total)
            setHighlightId(highlightChunkId)
            return
          }

          if ((currentPage + 1) * pageSize >= res.total || res.items.length === 0) {
            break
          }

          currentPage += 1
        }

        onHighlightConsumed?.()
      } catch (e) {
        toast.error('定位引用失败', { description: String(e) })
        onHighlightConsumed?.()
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    revealHighlightedChunk()

    return () => {
      cancelled = true
    }
  }, [highlightChunkId, onHighlightConsumed, selectedSource])

  useEffect(() => {
    if (!highlightId) return

    const found = chunks.find((chunk) => chunk.chunk_id === highlightId)
    if (!found) return

    const el = document.getElementById(`chunk-${highlightId}`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('ring-2', 'ring-primary/40', 'bg-primary/5')
      setTimeout(() => el.classList.remove('ring-2', 'ring-primary/40', 'bg-primary/5'), 2500)
    }

    setSelectedChunk(found)
    setHighlightId(null)
    onHighlightConsumed?.()
  }, [chunks, highlightId, onHighlightConsumed])

  const handleSearch = async () => {
    setLoading(true)
    setPage(0)
    try {
      await loadChunks(selectedSource, searchQuery, 0, pageSize)
      const [srcs, s] = await Promise.all([api.getKBSourceNames(), api.getKBStats()])
      setSources(srcs)
      setStats(s)
    } catch (e) { toast.error('搜索失败', { description: String(e) }) }
    setLoading(false)
  }

  const handlePageChange = async (newPage: number) => {
    setLoading(true)
    setPage(newPage)
    try {
      await loadChunks(selectedSource, searchQuery, newPage, pageSize, true)
    } catch (e) { toast.error('翻页失败', { description: String(e) }) }
    setLoading(false)
  }

  // Infinite scroll via IntersectionObserver
  useEffect(() => {
    if (observerRef.current) observerRef.current.disconnect()
    if (!sentinelRef.current || !hasMore || loading) return
    observerRef.current = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasMore && !loading) {
          handlePageChange(page + 1)
        }
      },
      { rootMargin: '200px' },
    )
    observerRef.current.observe(sentinelRef.current)
    return () => observerRef.current?.disconnect()
  }, [hasMore, loading, page])

  const toggleHotspotMode = async () => {
    const next = !hotspotMode
    setHotspotMode(next)
    if (next) {
      try {
        const data = await api.getKBHotspots()
        const m = new Map<string, number>()
        data.forEach((h) => m.set(h.chunk_id, h.hits))
        setHotspots(m)
      } catch (e) { toast.error('热点数据加载失败', { description: String(e) }) }
    }
  }

  // Sort chunks by hotspot hits when hotspot mode is active
  const displayChunks = hotspotMode
    ? [...chunks].sort((a, b) => (hotspots.get(b.chunk_id) || 0) - (hotspots.get(a.chunk_id) || 0))
    : chunks

  const resetProgressState = () => {
    setUploading(false)
    setIngesting(false)
    setUploadPhase('')
    setUploadPercent(0)
  }

  const runDebugSearch = async (query: string, strategy = debugStrategy) => {
    if (!query.trim()) return
    setDebugSearching(true)
    try {
      const results = await api.debugSearch(query.trim(), 5, strategy)
      setDebugResults(results)
    } catch (e) {
      toast.error('检索测试失败', { description: String(e) })
    }
    setDebugSearching(false)
  }

  const handleDebugSearch = async () => {
    await runDebugSearch(debugQuery, debugStrategy)
  }

  // Compute overlap marking for slice view
  const findOverlap = (prev: string, curr: string): number => {
    const maxOverlap = kbConfig?.chunk_overlap || 200
    for (let i = Math.min(maxOverlap, prev.length, curr.length); i > 10; i--) {
      if (prev.slice(-i) === curr.slice(0, i)) return i
    }
    return 0
  }

  const hotspotCount = (chunkId: string): number => hotspots.get(chunkId) || 0

  const hotspotColor = (count: number): string => {
    if (count <= 0) return 'text-muted-foreground/20'
    if (count <= 2) return 'text-muted-foreground/50'
    if (count <= 5) return 'text-orange-400/70'
    return 'text-red-400/80'
  }

  useEffect(() => {
    if (!didInitSourceFilterRef.current) {
      didInitSourceFilterRef.current = true
      return
    }
    if (skipNextSourceSearchRef.current) {
      skipNextSourceSearchRef.current = false
      return
    }
    handleSearch()
  }, [selectedSource])

  const handleSourceClick = (src: string) => {
    setSelectedSource(selectedSource === src ? '' : src)
  }

  const startUpload = async (file: File, versionMode?: 'replace' | 'append') => {
    setUploading(true)
    setUploadPhase('loading')
    setUploadPercent(0)
    setVersionPrompted(null)
    try {
      const probe = await api.checkSource(file.name)
      if (probe.exists && !versionMode) {
        setVersionPrompted({ kind: 'file', file, sourceName: file.name })
        resetProgressState()
        return
      }
    } catch (error) {
      toast.error('上传前检查失败', { description: String(error) })
      resetProgressState()
      return
    }

    api.uploadDocumentStream(file, versionMode, {
      onProgress: (phase, percent) => {
        setUploadPhase(phase)
        setUploadPercent(percent)
      },
      onDone: async (result) => {
        if (result.existing_version && !versionMode) {
          setVersionPrompted({ kind: 'file', file, sourceName: file.name })
          resetProgressState()
          return
        }
        await refreshData()
        const message = versionMode === 'replace'
          ? '文档已替换为新版本'
          : versionMode === 'append'
            ? '文档已追加新版本'
            : '文档已上传'
        toast.success(message, { description: file.name })
        resetProgressState()
        if (fileInputRef.current) fileInputRef.current.value = ''
      },
      onError: (message) => {
        toast.error('上传失败', { description: message })
        resetProgressState()
        if (fileInputRef.current) fileInputRef.current.value = ''
      },
    })
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    await startUpload(file)
  }

  const handleVersionAction = async (action: 'replace' | 'append' | 'skip') => {
    if (!versionPrompted) return
    if (action === 'skip') {
      setVersionPrompted(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      toast.info('已跳过，未重复导入')
      return
    }
    if (versionPrompted.kind === 'file') {
      await startUpload(versionPrompted.file, action)
      return
    }
    await startUrlIngest(versionPrompted.url, action)
  }

  const startUrlIngest = async (url: string, versionMode?: 'replace' | 'append') => {
    setIngesting(true)
    setUploadPhase('loading')
    setUploadPercent(0)
    setVersionPrompted(null)
    try {
      const probe = await api.checkSource(url)
      if (probe.exists && !versionMode) {
        setVersionPrompted({ kind: 'url', url, sourceName: url })
        resetProgressState()
        return
      }
    } catch (error) {
      toast.error('导入前检查失败', { description: String(error) })
      resetProgressState()
      return
    }

    api.ingestUrlStream(url, versionMode, {
      onProgress: (phase, percent) => {
        setUploadPhase(phase)
        setUploadPercent(percent)
      },
      onDone: async (result) => {
        if (result.existing_version && !versionMode) {
          setVersionPrompted({ kind: 'url', url, sourceName: url })
          resetProgressState()
          return
        }
        setUrlInput('')
        await refreshData()
        const message = versionMode === 'replace'
          ? '网页已替换为新版本'
          : versionMode === 'append'
            ? '网页已追加新版本'
            : '网页已导入'
        toast.success(message)
        resetProgressState()
      },
      onError: (message) => {
        toast.error('导入失败', { description: message })
        resetProgressState()
      },
    })
  }

  const handleIngestUrl = async () => {
    const url = urlInput.trim()
    if (!url) return
    await startUrlIngest(url)
  }

  const refreshData = async () => {
    try {
      const [s, srcs, cfg] = await Promise.all([api.getKBStats(), api.getKBSourceNames(), api.getKBConfig()])
      setStats(s); setSources(srcs); setKbConfig(cfg)
      setPage(0)
      allChunksRef.current = []
      setChunks([])
      await loadChunks(selectedSource, searchQuery, 0, pageSize, false)
    } catch (e) { toast.error('刷新失败', { description: String(e) }) }
  }

  const totalPages = chunks.reduce((acc, c) => acc + Math.ceil(c.content.length / 800), 0)

  const renderDebugSection = (title: string, hits: DebugSearchHit[], scoreMode: 'vector' | 'bm25' | 'rrf') => (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <h4 className="text-2xs font-medium text-foreground/80">{title}</h4>
        <span className="text-2xs text-muted-foreground/40">{hits.length} 条</span>
      </div>
      {hits.length === 0 ? (
        <div className="rounded border border-dashed border-border/60 px-2 py-3 text-2xs text-muted-foreground/50">
          没有命中结果
        </div>
      ) : (
        <div className="space-y-1 max-h-52 overflow-y-auto">
          {hits.map((hit) => (
            <div key={`${title}-${hit.chunk_id}`} className="rounded border border-border/50 p-2 text-xs">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-2xs font-mono text-primary/60">
                  #
                  {scoreMode === 'vector' ? hit.vector_rank : scoreMode === 'bm25' ? hit.bm25_rank : hit.rrf_rank}
                </span>
                <span className="text-2xs font-mono text-muted-foreground/40 truncate">{hit.chunk_id}</span>
              </div>
              <p className="text-2xs text-muted-foreground/50 truncate mb-1">{hit.source}</p>
              <p className="text-2xs text-foreground/70 line-clamp-3 mb-1">{hit.content}</p>
              <div className="flex flex-wrap gap-3 text-2xs text-muted-foreground/40 font-mono">
                {scoreMode === 'vector' && <span>向量: {hit.vector_score?.toFixed(4) ?? '-'}</span>}
                {scoreMode === 'bm25' && <span>BM25: {hit.bm25_score?.toFixed(4) ?? '-'}</span>}
                {scoreMode === 'rrf' && <span>RRF: {hit.rrf_score?.toFixed(4) ?? '-'}</span>}
                {hit.vector_rank != null && <span>V#{hit.vector_rank}</span>}
                {hit.bm25_rank != null && <span>B#{hit.bm25_rank}</span>}
                {hit.rrf_rank != null && <span>R#{hit.rrf_rank}</span>}
                {hit.rerank_rank != null && <span>重排#{hit.rerank_rank}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border px-5 py-3 bg-background/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          {!sidebarOpen && (
            <Button variant="ghost" size="sm" onClick={onOpenSidebar}>
              <PanelRightOpen className="h-4 w-4" />
            </Button>
          )}
          <button onClick={() => onNavigate('chat')}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mr-1">
            <ArrowLeft className="h-3.5 w-3.5" />返回
          </button>
          <div className="h-4 w-px bg-border" />
          <BookOpen className="h-4 w-4 text-primary" />
          <h1 className="font-heading text-lg text-foreground tracking-tight">知识库</h1>
        </div>

        <div className="flex items-center gap-4">
            {stats && (
              <div className="hidden md:flex items-center gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1"><FileText className="h-3 w-3" />{stats.chunk_count} 段落</span>
                <span className="flex items-center gap-1"><Layers className="h-3 w-3" />{stats.source_count} 引用文档</span>
                <span className="flex items-center gap-1"><Hash className="h-3 w-3" />{(stats.total_chars / 1000).toFixed(0)}k 字符</span>
              </div>
            )}
          </div>
      </header>

      {/* Document actions bar */}
      <div className="flex items-center gap-2 border-b border-border px-5 py-2 bg-surface/20">
        <input type="file" ref={fileInputRef} className="hidden" accept=".txt,.md,.pdf,.docx,.html" onChange={handleUpload} />
        <button onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-md bg-primary/10 text-primary hover:bg-primary/15 transition-colors">
          <Upload className="h-3 w-3" />上传文档
        </button>
        <div className="flex items-center gap-1 flex-1 max-w-sm">
          <Input
            placeholder="导入公开网页 https://…"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleIngestUrl() }}
            className="h-7 text-xs flex-1"
          />
          <Button size="sm" onClick={handleIngestUrl} disabled={ingesting || !urlInput.trim()}>
            <Globe className="h-3 w-3" />
          </Button>
        </div>
        {(uploading || ingesting) && (
          <div className="min-w-[120px] text-right">
            <div className="text-2xs text-muted-foreground/60">
              {{
                loading: '正在加载文档…',
                splitting: '正在切分段落…',
                embedding: '正在向量化…',
                done: '完成',
              }[uploadPhase] || '正在处理…'}
            </div>
            <div className="mt-1 h-1 w-full rounded-full bg-muted overflow-hidden">
              <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${uploadPercent}%` }} />
            </div>
          </div>
        )}
        <button onClick={refreshData}
          className="p-1.5 rounded-md text-muted-foreground/50 hover:text-foreground hover:bg-muted/30 transition-colors">
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
      {versionPrompted && (
        <div className="border-b border-border bg-primary/5 px-5 py-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-foreground/80">引用来源“{versionPrompted.sourceName}”已存在，选择处理方式：</span>
            <Button size="sm" variant="outline" onClick={() => handleVersionAction('replace')}>替换</Button>
            <Button size="sm" variant="outline" onClick={() => handleVersionAction('append')}>追加版本</Button>
            <Button size="sm" variant="ghost" onClick={() => handleVersionAction('skip')}>取消</Button>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-3 border-b border-border px-5 py-2.5 bg-surface/30">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/50" />
          <Input
            placeholder="搜索文档内容…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSearch() }}
            className="pl-9 h-8 text-xs"
          />
        </div>
        <div className="flex gap-1 flex-wrap flex-1">
          <button onClick={() => setSelectedSource('')}
            className={`px-2.5 py-1 text-2xs font-medium rounded-md transition-colors ${
              !selectedSource ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground bg-muted/50'
            }`}>
            全部
          </button>
          {sources.slice(0, 8).map((s) => (
            <button key={s} onClick={() => handleSourceClick(s)}
              className={`px-2.5 py-1 text-2xs font-medium rounded-md transition-colors max-w-[120px] truncate ${
                selectedSource === s ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground bg-muted/50'
              }`}>
              {s}
            </button>
          ))}
          {sources.length > 8 && (
            <span className="px-2 py-1 text-2xs text-muted-foreground">+{sources.length - 8}</span>
          )}
        </div>
      </div>

      {/* View mode toggles */}
      {selectedSource && (
        <div className="flex items-center gap-2 border-b border-border px-5 py-1.5 bg-surface/20">
          <div className="flex items-center gap-0.5 rounded-md border border-border p-0.5">
            <button onClick={() => setChunkView('grid')}
              className={`p-1 rounded-sm transition-colors ${chunkView === 'grid' ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
              <LayoutGrid className="h-3 w-3" />
            </button>
            <button onClick={() => setChunkView('slice')}
              className={`p-1 rounded-sm transition-colors ${chunkView === 'slice' ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
              <List className="h-3 w-3" />
            </button>
          </div>
          <span className="text-2xs text-muted-foreground/50">
            {chunkView === 'grid' ? '网格视图' : '切片视图'}
          </span>
          <div className="h-3 w-px bg-border mx-1" />
          <button onClick={toggleHotspotMode}
            className={`flex items-center gap-1 px-2 py-1 text-2xs font-medium rounded-md transition-colors ${
              hotspotMode ? 'bg-orange-500/15 text-orange-400' : 'text-muted-foreground hover:text-foreground bg-muted/30'
            }`}>
            <Flame className="h-3 w-3" />
            热点
          </button>
          {kbConfig && (
            <span className="text-2xs text-muted-foreground/30 ml-auto font-mono">
              chunk: {kbConfig.chunk_size} · overlap: {kbConfig.chunk_overlap}
            </span>
          )}
        </div>
      )}

      {/* Debug Search Sandbox */}
      <div className="border-b border-border">
        <button
          onClick={() => setDebugOpen(!debugOpen)}
          className="flex items-center gap-2 px-5 py-2 w-full text-left text-2xs text-muted-foreground/50 hover:text-muted-foreground transition-colors"
        >
          <Bug className="h-3 w-3" />
          检索测试沙盒
          <span className="text-2xs text-muted-foreground/30 mr-1">高级功能</span>
          <span className="ml-auto">{debugOpen ? '收起' : '展开'}</span>
        </button>
        {debugOpen && (
          <div className="px-5 pb-3 space-y-3">
            <div className="flex flex-wrap gap-1">
              {[
                { value: 'fast', label: '快速' },
                { value: 'balanced', label: '标准' },
                { value: 'high_quality', label: '严谨' },
                { value: 'deep', label: '深度' },
              ].map((option) => (
                <button
                  key={option.value}
                  onClick={() => {
                    const nextStrategy = option.value as typeof debugStrategy
                    setDebugStrategy(nextStrategy)
                    if (debugQuery.trim()) void runDebugSearch(debugQuery, nextStrategy)
                  }}
                  className={`rounded-md px-2 py-1 text-2xs transition-colors ${
                    debugStrategy === option.value
                      ? 'bg-primary/15 text-primary'
                      : 'bg-muted/50 text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                placeholder="输入测试查询…"
                value={debugQuery}
                onChange={(e) => setDebugQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleDebugSearch() }}
                className="flex-1 h-8 text-xs"
              />
              <Button size="sm" onClick={handleDebugSearch} disabled={debugSearching}>
                {debugSearching ? <Loader2 className="h-3 w-3 animate-spin" /> : '检索'}
              </Button>
            </div>
            {debugResults && (
              <div className="grid gap-3 md:grid-cols-3">
                {renderDebugSection('向量 Top-5', debugResults.vector_results, 'vector')}
                {renderDebugSection('BM25 Top-5', debugResults.bm25_results, 'bm25')}
                {renderDebugSection('RRF 融合', debugResults.fused_results, 'rrf')}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Content — magazine shelf layout */}
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-5xl px-5 py-6">
          {error ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <AlertTriangle className="h-12 w-12 text-destructive/40 mb-4" />
              <p className="text-sm text-muted-foreground mb-1">数据加载失败</p>
              <p className="text-2xs text-muted-foreground/50 mb-4 max-w-xs">{error}</p>
              <Button variant="outline" size="sm" onClick={() => { setError(null); setLoading(true); window.location.reload() }}>重试</Button>
            </div>
          ) : loading ? (
            <SkeletonGrid count={6} />
          ) : displayChunks.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <BookOpen className="h-12 w-12 text-muted-foreground/20 mb-4" />
              <p className="text-sm text-muted-foreground">知识库为空</p>
              <p className="text-xs text-muted-foreground/50 mt-1">上传文档或导入网页后即可浏览</p>
            </div>
          ) : chunkView === 'slice' && selectedSource ? (
            /* ── Slice view (vertical timeline) ── */
            <div className="max-w-2xl mx-auto space-y-3">
              {displayChunks.map((chunk, i) => {
                const overlapLen = i > 0 ? findOverlap(displayChunks[i - 1].content, chunk.content) : 0
                const content = chunk.original_content || chunk.content
                const hc = hotspotCount(chunk.chunk_id)
                return (
                  <motion.div
                    key={chunk.chunk_id}
                    id={`chunk-${chunk.chunk_id}`}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03, duration: 0.25 }}
                    onClick={() => setSelectedChunk(chunk)}
                    className="group cursor-pointer rounded-lg border border-border bg-surface/30 p-3.5 hover:border-primary/20 transition-all"
                  >
                    {/* Header */}
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-2xs font-mono text-muted-foreground/40">#{chunk.chunk_index}</span>
                        <span className="text-2xs text-muted-foreground/30">{chunk.content.length} 字</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {hotspotMode && (
                          <span className={`inline-flex items-center gap-0.5 text-2xs font-mono ${hotspotColor(hc)}`}>
                            <Flame className="h-2.5 w-2.5" />{hc}
                          </span>
                        )}
                        {overlapLen > 0 && (
                          <span className="text-2xs text-yellow-500/50 font-mono">overlap {overlapLen}</span>
                        )}
                      </div>
                    </div>
                    {/* Content with overlap highlight */}
                    <p className="text-xs text-foreground/70 leading-relaxed font-body">
                      {overlapLen > 0 ? (
                        <>
                          <mark className="bg-yellow-500/15 text-foreground/80 rounded-sm px-0.5">
                            {content.slice(0, overlapLen)}
                          </mark>
                          {content.slice(overlapLen)}
                        </>
                      ) : (
                        content
                      )}
                    </p>
                    {/* Decorative index bar */}
                    <div className="mt-2 h-0.5 w-full rounded-full bg-muted/30">
                      <div className="h-full rounded-full bg-primary/20" style={{ width: `${(chunk.content.length / (kbConfig?.chunk_size || 1000)) * 100}%` }} />
                    </div>
                    {/* Bookmark for slice view */}
                    <div className="mt-1.5 flex items-center justify-end">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleChunkBookmark(chunk)
                        }}
                        className={`${bookmarkedChunks.has(chunk.chunk_id) ? 'text-amber-400' : 'text-muted-foreground/20 hover:text-amber-400'} transition-colors`}
                        title={bookmarkedChunks.has(chunk.chunk_id) ? '已收藏' : '收藏此段落'}
                      >
                        {bookmarkedChunks.has(chunk.chunk_id) ? <BookmarkCheck className="h-3 w-3" /> : <Bookmark className="h-3 w-3" />}
                      </button>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          ) : (
            /* ── Grid view (default magazine layout) ── */
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <AnimatePresence>
                {displayChunks.map((chunk, i) => {
                  const hc = hotspotCount(chunk.chunk_id)
                  return (
                    <motion.div
                      key={chunk.chunk_id}
                      id={`chunk-${chunk.chunk_id}`}
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: (i % 12) * 0.04, duration: 0.3 }}
                      onClick={() => setSelectedChunk(chunk)}
                      className="group cursor-pointer rounded-lg border border-border bg-surface/30 p-4 hover:border-primary/20 hover:bg-surface/60 transition-all"
                    >
                      {/* Magazine-style header */}
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className="text-2xs font-mono text-muted-foreground/50 tracking-wider uppercase">
                          {chunk.source}
                        </span>
                        <span className="flex items-center gap-1">
                          {hotspotMode && (
                            <span className={`text-2xs font-mono ${hotspotColor(hc)}`}>
                              <Flame className="inline h-2.5 w-2.5 mr-0.5" />{hc}
                            </span>
                          )}
                          <span className="text-2xs font-mono text-muted-foreground/30">
                            #{chunk.chunk_index}
                          </span>
                        </span>
                      </div>

                      {/* Decorative line */}
                      <div className="w-8 h-0.5 bg-primary/30 rounded-full mb-2.5" />

                      {/* Section tag */}
                      {chunk.section && (
                        <span className="inline-block px-1.5 py-0.5 text-2xs font-medium rounded bg-primary/8 text-primary/70 mb-2">
                          {chunk.section}
                        </span>
                      )}

                      {/* Content preview */}
                      <p className="text-xs text-foreground/70 leading-relaxed line-clamp-5 font-body">
                        {chunk.original_content || chunk.content}
                      </p>

                      {/* Meta footer */}
                      <div className="mt-3 flex items-center gap-2 text-2xs text-muted-foreground/40">
                        <span>{chunk.content.length} 字</span>
                        {chunk.page && <><span>·</span><span>第 {chunk.page} 页</span></>}
                        <button
                          onClick={(e) => { e.stopPropagation(); handleChunkBookmark(chunk) }}
                          className={`ml-auto ${bookmarkedChunks.has(chunk.chunk_id) ? 'text-amber-400' : 'text-muted-foreground/20 hover:text-amber-400'} transition-colors`}
                          title={bookmarkedChunks.has(chunk.chunk_id) ? '已收藏' : '收藏此段落'}
                        >
                          {bookmarkedChunks.has(chunk.chunk_id) ? <BookmarkCheck className="h-3 w-3" /> : <Bookmark className="h-3 w-3" />}
                        </button>
                      </div>

                      {/* Hover indicator */}
                      <div className="mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <span className="text-2xs text-primary/60">点击查看全文 →</span>
                      </div>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            </div>
          )}

          {/* Bottom stats & pagination */}
          {!loading && total > 0 && (
            <div className="mt-8 flex items-center justify-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-2xs text-muted-foreground/30 font-mono">
                  共 {total} 个段落 · {stats?.source_count ?? 0} 个引用文档 · 总计 {(stats?.total_chars ?? 0) / 1000}k 字符
                </span>
              </div>
            </div>
          )}

          {/* Infinite scroll sentinel */}
          {hasMore && !loading && <div ref={sentinelRef} className="h-4" />}
        </div>
      </ScrollArea>

      {/* Detail dialog */}
        <Dialog open={!!selectedChunk} onOpenChange={(open) => { if (!open) setSelectedChunk(null) }}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-primary" />
                <span className="text-sm font-medium">{selectedChunk?.source}</span>
                <span className="text-xs text-muted-foreground font-mono">#{selectedChunk?.chunk_index}</span>
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                查看当前段落的完整内容与基础元信息。
              </DialogDescription>
            </DialogHeader>

          <div className="space-y-4">
            {/* Metadata chips */}
            <div className="flex flex-wrap gap-2">
              {selectedChunk?.section && (
                <span className="px-2 py-0.5 text-2xs font-medium rounded-full bg-primary/10 text-primary/80">
                  {selectedChunk.section}
                </span>
              )}
              {selectedChunk?.page && (
                <span className="px-2 py-0.5 text-2xs font-medium rounded-full bg-muted text-muted-foreground">
                  第 {selectedChunk.page} 页
                </span>
              )}
              <span className="px-2 py-0.5 text-2xs font-mono rounded-full bg-muted text-muted-foreground">
                {selectedChunk?.chunk_id.slice(0, 24)}…
              </span>
            </div>

            <Separator />

            {/* Full content */}
            <div className="prose-chat text-sm leading-relaxed">
              {selectedChunk?.original_content || selectedChunk?.content}
            </div>

            <div className="text-2xs text-muted-foreground/40 font-mono">
              {selectedChunk?.content.length} 字符
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
