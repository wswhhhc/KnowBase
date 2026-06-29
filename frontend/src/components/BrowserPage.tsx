import { toast } from 'sonner'
import { useEffect, useState, useRef, useCallback } from 'react'
import { Button, ScrollArea, SkeletonGrid } from '@/components/ui'
import { BookOpen, AlertTriangle, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'
import * as api from '@/lib/api'
import type { KBStats, KBChunk, KBConfig, DebugSearchResponse } from '@/lib/api'
import type { ViewType } from '@/App'
import BrowserHeader from './browser/BrowserHeader'
import DocumentActions from './browser/DocumentActions'
import SearchToolbar from './browser/SearchToolbar'
import DebugSandbox from './browser/DebugSandbox'
import GridView from './browser/GridView'
import SliceView from './browser/SliceView'
import ChunkDetailDialog from './browser/ChunkDetailDialog'

const UPLOAD_TRIGGER_EVENT = 'kb-trigger-upload'
const PAGE_SIZE = 50

interface BrowserPageProps {
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
  highlightChunkId?: string | null
  onHighlightConsumed?: () => void
  workspaceId?: string
}

export default function BrowserPage({ onOpenSidebar, sidebarOpen, onNavigate, highlightChunkId, onHighlightConsumed, workspaceId }: BrowserPageProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const guideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const allChunksRef = useRef<KBChunk[]>([])

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
  const [versionPrompted, setVersionPrompted] = useState<{ kind: 'file'; file: File; sourceName: string } | { kind: 'url'; url: string; sourceName: string } | null>(null)
  const [showPostUploadGuide, setShowPostUploadGuide] = useState(false)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [bookmarkedChunks, setBookmarkedChunks] = useState<Set<string>>(new Set())
  const [hasMore, setHasMore] = useState(true)

  const browserWsId = workspaceId || ''

  const setChunksAccumulate = (items: KBChunk[], append: boolean) => {
    allChunksRef.current = append ? [...allChunksRef.current, ...items] : items
    setChunks([...allChunksRef.current])
  }

  const loadChunks = async (src: string, q: string, p: number, ps: number, append = false) => {
    const res = await api.getKBChunks(src, q, p * ps, ps)
    setChunksAccumulate(res.items, append)
    setTotal(res.total)
    setHasMore((p + 1) * ps < res.total)
    return res
  }

  const refreshData = useCallback(async () => {
    try {
      const [s, srcs, cfg] = await Promise.all([api.getKBStats(), api.getKBSourceNames(), api.getKBConfig()])
      setStats(s); setSources(srcs); setKbConfig(cfg)
      setPage(0); allChunksRef.current = []; setChunks([])
      await loadChunks(selectedSource, searchQuery, 0, PAGE_SIZE, false)
    } catch (e) { toast.error('刷新失败', { description: String(e) }) }
  }, [selectedSource, searchQuery])

  const handleSearch = async () => {
    setLoading(true); setPage(0)
    try {
      await loadChunks(selectedSource, searchQuery, 0, PAGE_SIZE)
      const [srcs, s] = await Promise.all([api.getKBSourceNames(), api.getKBStats()])
      setSources(srcs); setStats(s)
    } catch (e) { toast.error('搜索失败', { description: String(e) }) }
    setLoading(false)
  }

  const handlePageChange = async (newPage: number) => {
    setLoading(true); setPage(newPage)
    try { await loadChunks(selectedSource, searchQuery, newPage, PAGE_SIZE, true) }
    catch (e) { toast.error('翻页失败', { description: String(e) }) }
    setLoading(false)
  }

  const handleSourceClick = (src: string) => setSelectedSource(selectedSource === src ? '' : src)

  // ── Initial load ──
  useEffect(() => {
    setError(null); setLoading(true)
    Promise.all([
      loadChunks('', '', 0, PAGE_SIZE),
      api.getKBStats(), api.getKBSourceNames(), api.getKBConfig(),
    ])
      .then(([, s, srcs, cfg]) => { setStats(s); setSources(srcs); setKbConfig(cfg) })
      .catch((e) => { setError(String(e)); toast.error('加载失败', { description: String(e) }) })
      .finally(() => {
        if (sessionStorage.getItem('kb_trigger_upload') === 'true') {
          sessionStorage.removeItem('kb_trigger_upload')
          requestAnimationFrame(() => fileInputRef.current?.click())
        }
        setLoading(false)
      })
  }, [])

  // ── Upload trigger listener (from FAB) ──
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

  // ── Citation highlight ──
  useEffect(() => {
    if (!highlightChunkId) return
    const existing = allChunksRef.current.find((c) => c.chunk_id === highlightChunkId)
    if (existing) { setSelectedChunk(existing); onHighlightConsumed?.(); return }

    let cancelled = false
    ;(async () => {
      try {
        const chunk = await api.getKBChunkById(highlightChunkId)
        if (cancelled) return
        allChunksRef.current = [chunk, ...allChunksRef.current]
        setChunks([...allChunksRef.current])
        setSelectedChunk(chunk)
        onHighlightConsumed?.()
      } catch (e) { toast.error('定位引用失败', { description: String(e) }); onHighlightConsumed?.() }
    })()
    return () => { cancelled = true }
  }, [highlightChunkId, onHighlightConsumed])

  // ── Source filter side effect ──
  const didInitSourceFilter = useRef(false)
  const skipNextSourceSearch = useRef(false)
  useEffect(() => {
    if (!didInitSourceFilter.current) { didInitSourceFilter.current = true; return }
    if (skipNextSourceSearch.current) { skipNextSourceSearch.current = false; return }
    handleSearch()
  }, [selectedSource])

  // ── Infinite scroll ──
  useEffect(() => {
    if (observerRef.current) observerRef.current.disconnect()
    if (!sentinelRef.current || !hasMore || loading) return
    observerRef.current = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting && hasMore && !loading) handlePageChange(page + 1) },
      { rootMargin: '200px' },
    )
    observerRef.current.observe(sentinelRef.current)
    return () => observerRef.current?.disconnect()
  }, [hasMore, loading, page])

  // ── Guide timer cleanup ──
  useEffect(() => () => { if (guideTimerRef.current) clearTimeout(guideTimerRef.current) }, [])

  // ── Upload/Ingest handlers ──
  const resetProgress = () => { setUploading(false); setIngesting(false); setUploadPhase(''); setUploadPercent(0) }

  const startUpload = async (file: File, versionMode?: 'replace' | 'append') => {
    setUploading(true); setUploadPhase('loading'); setUploadPercent(0); setVersionPrompted(null)
    try {
      const probe = await api.checkSource(file.name)
      if (probe.exists && !versionMode) { setVersionPrompted({ kind: 'file', file, sourceName: file.name }); resetProgress(); return }
    } catch { toast.error('上传前检查失败'); resetProgress(); return }
    api.uploadDocumentStream(file, versionMode, {
      onProgress: (phase, pct) => { setUploadPhase(phase); setUploadPercent(pct) },
      onDone: async (result) => {
        if (result.existing_version && !versionMode) { setVersionPrompted({ kind: 'file', file, sourceName: file.name }); resetProgress(); return }
        await refreshData()
        setShowPostUploadGuide(true)
        if (guideTimerRef.current) clearTimeout(guideTimerRef.current)
        guideTimerRef.current = setTimeout(() => setShowPostUploadGuide(false), 8000)
        toast.success(versionMode === 'replace' ? '文档已替换为新版本' : versionMode === 'append' ? '文档已追加新版本' : '文档已上传', { description: file.name })
        resetProgress()
        if (fileInputRef.current) fileInputRef.current.value = ''
      },
      onError: (msg) => { toast.error('上传失败', { description: msg }); resetProgress(); if (fileInputRef.current) fileInputRef.current.value = '' },
    })
  }

  const startUrlIngest = async (url: string, versionMode?: 'replace' | 'append') => {
    setIngesting(true); setUploadPhase('loading'); setUploadPercent(0); setVersionPrompted(null)
    try {
      const probe = await api.checkSource(url)
      if (probe.exists && !versionMode) { setVersionPrompted({ kind: 'url', url, sourceName: url }); resetProgress(); return }
    } catch { toast.error('导入前检查失败'); resetProgress(); return }
    api.ingestUrlStream(url, versionMode, {
      onProgress: (phase, pct) => { setUploadPhase(phase); setUploadPercent(pct) },
      onDone: async (result) => {
        if (result.existing_version && !versionMode) { setVersionPrompted({ kind: 'url', url, sourceName: url }); resetProgress(); return }
        setUrlInput(''); await refreshData()
        setShowPostUploadGuide(true)
        if (guideTimerRef.current) clearTimeout(guideTimerRef.current)
        guideTimerRef.current = setTimeout(() => setShowPostUploadGuide(false), 8000)
        toast.success(versionMode === 'replace' ? '网页已替换为新版本' : versionMode === 'append' ? '网页已追加新版本' : '网页已导入')
        resetProgress()
      },
      onError: (msg) => { toast.error('导入失败', { description: msg }); resetProgress() },
    })
  }

  const toggleHotspotMode = async () => {
    const next = !hotspotMode; setHotspotMode(next)
    if (next) {
      try { const data = await api.getKBHotspots(); setHotspots(new Map(data.map((h) => [h.chunk_id, h.hits] as [string, number]))) }
      catch (e) { toast.error('热点数据加载失败', { description: String(e) }) }
    }
  }

  const hotspotCount = (chunkId: string) => hotspots.get(chunkId) || 0
  const findOverlap = (prev: string, curr: string) => {
    const maxOverlap = kbConfig?.chunk_overlap || 200
    for (let i = Math.min(maxOverlap, prev.length, curr.length); i > 10; i--)
      if (prev.slice(-i) === curr.slice(0, i)) return i
    return 0
  }

  const displayChunks = hotspotMode
    ? [...chunks].sort((a, b) => (hotspots.get(b.chunk_id) || 0) - (hotspots.get(a.chunk_id) || 0))
    : chunks

  const handleChunkBookmark = async (chunk: KBChunk) => {
    if (bookmarkedChunks.has(chunk.chunk_id)) return
    try {
      await api.createBookmark({ chunk_id: chunk.chunk_id, content: chunk.content.slice(0, 500), source: chunk.source, workspace_id: browserWsId || undefined })
      setBookmarkedChunks((prev) => new Set(prev).add(chunk.chunk_id))
    } catch (e) { toast.error('收藏失败', { description: String(e) }) }
  }

  const runDebugSearch = async (query: string, strategy: string) => {
    try { return await api.debugSearch(query, 5, strategy) }
    catch (e) { toast.error('检索测试失败', { description: String(e) }); return null }
  }

  return (
    <div className="flex flex-col h-full">
      <input type="file" ref={fileInputRef} className="hidden" accept=".txt,.md,.pdf,.docx,.html"
        onChange={async (e) => { const f = e.target.files?.[0]; if (f) await startUpload(f) }} />

      <BrowserHeader stats={stats} onOpenSidebar={onOpenSidebar} sidebarOpen={sidebarOpen} onNavigate={onNavigate} />

      <DocumentActions uploading={uploading} ingesting={ingesting} uploadPhase={uploadPhase} uploadPercent={uploadPercent}
        urlInput={urlInput} setUrlInput={setUrlInput} handleIngestUrl={() => { const u = urlInput.trim(); if (u) startUrlIngest(u) }}
        refreshData={refreshData} onUploadClick={() => fileInputRef.current?.click()} />

      {versionPrompted && (
        <div className="border-b border-border bg-primary/5 px-5 py-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-foreground/80">引用来源"{versionPrompted.sourceName}"已存在，选择处理方式：</span>
            <Button size="sm" variant="outline" onClick={async () => versionPrompted.kind === 'file' ? startUpload(versionPrompted.file, 'replace') : startUrlIngest(versionPrompted.url, 'replace')}>替换</Button>
            <Button size="sm" variant="outline" onClick={async () => versionPrompted.kind === 'file' ? startUpload(versionPrompted.file, 'append') : startUrlIngest(versionPrompted.url, 'append')}>追加版本</Button>
            <Button size="sm" variant="ghost" onClick={() => { setVersionPrompted(null); if (fileInputRef.current) fileInputRef.current.value = '' }}>取消</Button>
          </div>
        </div>
      )}

      <SearchToolbar searchQuery={searchQuery} setSearchQuery={setSearchQuery} handleSearch={handleSearch}
        selectedSource={selectedSource} sources={sources} onSourceClick={handleSourceClick}
        chunkView={chunkView} setChunkView={setChunkView} hotspotMode={hotspotMode} toggleHotspotMode={toggleHotspotMode}
        kbConfig={kbConfig} showViewControls={!!selectedSource} />

      <DebugSandbox onRunSearch={runDebugSearch} />

      <ScrollArea ref={scrollRef} className="flex-1">
        <div className="mx-auto max-w-5xl px-5 py-6">
          {error ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <AlertTriangle className="h-12 w-12 text-destructive/40 mb-4" />
              <p className="text-sm text-muted-foreground mb-1">数据加载失败</p>
              <p className="text-2xs text-muted-foreground/50 mb-4 max-w-xs">{error}</p>
              <Button variant="outline" size="sm" onClick={() => window.location.reload()}>重试</Button>
            </div>
          ) : (<>
            {showPostUploadGuide && (
              <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
                className="mb-4 flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
                <p className="text-xs text-foreground/80">文档已导入！现在可以去提问了</p>
                <Button size="sm" onClick={() => onNavigate('chat')} className="gap-1"><Sparkles className="h-3 w-3" />现在去提问</Button>
              </motion.div>
            )}
            {loading ? <SkeletonGrid count={6} /> : displayChunks.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <BookOpen className="h-12 w-12 text-muted-foreground/20 mb-4" />
                <p className="text-sm text-muted-foreground">知识库为空</p>
                <p className="text-xs text-muted-foreground/50 mt-1">上传文档或导入网页后即可浏览</p>
              </div>
            ) : chunkView === 'slice' && selectedSource ? (
              <SliceView chunks={displayChunks} kbConfig={kbConfig} hotspotMode={hotspotMode} hotspotCount={hotspotCount}
                findOverlap={findOverlap} onChunkClick={setSelectedChunk} bookmarkedChunks={bookmarkedChunks} onBookmark={handleChunkBookmark} />
            ) : (
              <GridView chunks={displayChunks} hotspotMode={hotspotMode} hotspotCount={hotspotCount}
                onChunkClick={setSelectedChunk} bookmarkedChunks={bookmarkedChunks} onBookmark={handleChunkBookmark} />
            )}
            {!loading && total > 0 && (
              <div className="mt-8 flex items-center justify-center gap-4">
                <span className="text-2xs text-muted-foreground/30 font-mono">
                  共 {total} 个段落 · {stats?.source_count ?? 0} 个引用文档 · 总计 {(stats?.total_chars ?? 0) / 1000}k 字符
                </span>
              </div>
            )}
            {hasMore && !loading && <div ref={sentinelRef} className="h-4" />}
          </>)}
          </div>
      </ScrollArea>

      <ChunkDetailDialog chunk={selectedChunk} onClose={() => setSelectedChunk(null)} />
    </div>
  )
}
