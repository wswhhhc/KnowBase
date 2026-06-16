import { useEffect, useState, useRef } from 'react'
import { Button, Input, ScrollArea, Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui'
import { BookOpen, PanelRightOpen, ArrowLeft, Search, FileText, Hash, ExternalLink, Layers, Sun, Moon, Flame, List, LayoutGrid, Upload, Globe, RefreshCw } from 'lucide-react'
import * as api from '@/lib/api'
import type { KBStats, KBChunk, KBConfig, HotspotEntry } from '@/lib/api'
import { motion, AnimatePresence } from 'framer-motion'
import type { ViewType } from '@/App'
import { Separator, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui'

interface BrowserPageProps {
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
  theme: { theme: 'dark' | 'light'; toggle: () => void }
}

export default function BrowserPage({ onOpenSidebar, sidebarOpen, onNavigate, theme }: BrowserPageProps) {
  const [stats, setStats] = useState<KBStats | null>(null)
  const [chunks, setChunks] = useState<KBChunk[]>([])
  const [sources, setSources] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSource, setSelectedSource] = useState('')
  const [selectedChunk, setSelectedChunk] = useState<KBChunk | null>(null)
  const [chunkView, setChunkView] = useState<'grid' | 'slice'>('grid')
  const [hotspotMode, setHotspotMode] = useState(false)
  const [hotspots, setHotspots] = useState<Map<string, number>>(new Map())
  const [kbConfig, setKbConfig] = useState<KBConfig | null>(null)
  const [urlInput, setUrlInput] = useState('')
  const [ingesting, setIngesting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const pageSize = 50

  const loadChunks = async (src: string, q: string, p: number, ps: number) => {
    const res = await api.getKBChunks(src, q, p * ps, ps)
    setChunks(res.items)
    setTotal(res.total)
    return res
  }

  useEffect(() => {
    loadChunks('', '', 0, pageSize)
    Promise.all([api.getKBStats(), api.getKBSourceNames(), api.getKBConfig()])
      .then(([s, srcs, cfg]) => { setStats(s); setSources(srcs); setKbConfig(cfg) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleSearch = async () => {
    setLoading(true)
    setPage(0)
    try {
      await loadChunks(selectedSource, searchQuery, 0, pageSize)
      const [srcs, s] = await Promise.all([api.getKBSourceNames(), api.getKBStats()])
      setSources(srcs)
      setStats(s)
    } catch { /* ignore */ }
    setLoading(false)
  }

  const handlePageChange = async (newPage: number) => {
    setLoading(true)
    setPage(newPage)
    try {
      await loadChunks(selectedSource, searchQuery, newPage, pageSize)
    } catch { /* ignore */ }
    setLoading(false)
  }

  const toggleHotspotMode = async () => {
    const next = !hotspotMode
    setHotspotMode(next)
    if (next) {
      try {
        const data = await api.getKBHotspots()
        const m = new Map<string, number>()
        data.forEach((h) => m.set(h.chunk_id, h.hits))
        setHotspots(m)
      } catch { /* ignore */ }
    }
  }

  // Sort chunks by hotspot hits when hotspot mode is active
  const displayChunks = hotspotMode
    ? [...chunks].sort((a, b) => (hotspots.get(b.chunk_id) || 0) - (hotspots.get(a.chunk_id) || 0))
    : chunks

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

  useEffect(() => { handleSearch() }, [selectedSource])

  const handleSourceClick = (src: string) => {
    setSelectedSource(selectedSource === src ? '' : src)
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await api.uploadDocument(file)
      await refreshData()
    } catch (err) { alert(String(err)) }
    e.target.value = ''
  }

  const handleIngestUrl = async () => {
    if (!urlInput.trim()) return
    setIngesting(true)
    try {
      await api.ingestUrl(urlInput.trim())
      setUrlInput('')
      await refreshData()
    } catch (err) { alert(String(err)) }
    setIngesting(false)
  }

  const refreshData = async () => {
    try {
      const [s, srcs, cfg] = await Promise.all([api.getKBStats(), api.getKBSourceNames(), api.getKBConfig()])
      setStats(s); setSources(srcs); setKbConfig(cfg)
      await loadChunks(selectedSource, searchQuery, page, pageSize)
    } catch { /* ignore */ }
  }

  const totalPages = chunks.reduce((acc, c) => acc + Math.ceil(c.content.length / 800), 0)

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
              <span className="flex items-center gap-1"><FileText className="h-3 w-3" />{stats.chunk_count} 片段</span>
              <span className="flex items-center gap-1"><Layers className="h-3 w-3" />{stats.source_count} 来源</span>
              <span className="flex items-center gap-1"><Hash className="h-3 w-3" />{(stats.total_chars / 1000).toFixed(0)}k 字符</span>
            </div>
          )}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button onClick={theme.toggle}
                  className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
                  {theme.theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
                </button>
              </TooltipTrigger>
              <TooltipContent>{theme.theme === 'dark' ? '切换浅色模式' : '切换深色模式'}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </header>

      {/* Document actions bar */}
      <div className="flex items-center gap-2 border-b border-border px-5 py-2 bg-surface/20">
        <input type="file" ref={fileInputRef} className="hidden" accept=".txt,.md,.pdf,.docx,.html" onChange={handleUpload} />
        <button onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium rounded-md bg-primary/10 text-primary hover:bg-primary/15 transition-colors">
          <Upload className="h-3 w-3" />上传文档
        </button>
        <div className="flex items-center gap-1 flex-1 max-w-sm">
          <Input
            placeholder="导入公开网页 https://…"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleIngestUrl() }}
            className="h-7 text-[11px] flex-1"
          />
          <Button size="sm" onClick={handleIngestUrl} disabled={ingesting || !urlInput.trim()}>
            <Globe className="h-3 w-3" />
          </Button>
        </div>
        <button onClick={refreshData}
          className="p-1.5 rounded-md text-muted-foreground/50 hover:text-foreground hover:bg-muted/30 transition-colors">
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

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
            className={`px-2.5 py-1 text-[10px] font-medium rounded-md transition-colors ${
              !selectedSource ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground bg-muted/50'
            }`}>
            全部
          </button>
          {sources.slice(0, 8).map((s) => (
            <button key={s} onClick={() => handleSourceClick(s)}
              className={`px-2.5 py-1 text-[10px] font-medium rounded-md transition-colors max-w-[120px] truncate ${
                selectedSource === s ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground bg-muted/50'
              }`}>
              {s}
            </button>
          ))}
          {sources.length > 8 && (
            <span className="px-2 py-1 text-[10px] text-muted-foreground">+{sources.length - 8}</span>
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
          <span className="text-[10px] text-muted-foreground/50">
            {chunkView === 'grid' ? '网格视图' : '切片视图'}
          </span>
          <div className="h-3 w-px bg-border mx-1" />
          <button onClick={toggleHotspotMode}
            className={`flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-md transition-colors ${
              hotspotMode ? 'bg-orange-500/15 text-orange-400' : 'text-muted-foreground hover:text-foreground bg-muted/30'
            }`}>
            <Flame className="h-3 w-3" />
            热点
          </button>
          {kbConfig && (
            <span className="text-[10px] text-muted-foreground/30 ml-auto font-mono">
              chunk: {kbConfig.chunk_size} · overlap: {kbConfig.chunk_overlap}
            </span>
          )}
        </div>
      )}

      {/* Content — magazine shelf layout */}
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-5xl px-5 py-6">
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="rounded-lg border border-border bg-surface/30 p-4 animate-pulse">
                  <div className="h-3 bg-muted rounded w-2/3 mb-3" />
                  <div className="h-2 bg-muted rounded w-full mb-2" />
                  <div className="h-2 bg-muted rounded w-5/6 mb-2" />
                  <div className="h-2 bg-muted rounded w-4/6" />
                </div>
              ))}
            </div>
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
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03, duration: 0.25 }}
                    onClick={() => setSelectedChunk(chunk)}
                    className="group cursor-pointer rounded-lg border border-border bg-surface/30 p-3.5 hover:border-primary/20 transition-all"
                  >
                    {/* Header */}
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-muted-foreground/40">#{chunk.chunk_index}</span>
                        <span className="text-[10px] text-muted-foreground/30">{chunk.content.length} 字</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {hotspotMode && (
                          <span className={`inline-flex items-center gap-0.5 text-[10px] font-mono ${hotspotColor(hc)}`}>
                            <Flame className="h-2.5 w-2.5" />{hc}
                          </span>
                        )}
                        {overlapLen > 0 && (
                          <span className="text-[9px] text-yellow-500/50 font-mono">overlap {overlapLen}</span>
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
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: (i % 12) * 0.04, duration: 0.3 }}
                      onClick={() => setSelectedChunk(chunk)}
                      className="group cursor-pointer rounded-lg border border-border bg-surface/30 p-4 hover:border-primary/20 hover:bg-surface/60 transition-all"
                    >
                      {/* Magazine-style header */}
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className="text-[9px] font-mono text-muted-foreground/50 tracking-wider uppercase">
                          {chunk.source}
                        </span>
                        <span className="flex items-center gap-1">
                          {hotspotMode && (
                            <span className={`text-[9px] font-mono ${hotspotColor(hc)}`}>
                              <Flame className="inline h-2.5 w-2.5 mr-0.5" />{hc}
                            </span>
                          )}
                          <span className="text-[9px] font-mono text-muted-foreground/30">
                            #{chunk.chunk_index}
                          </span>
                        </span>
                      </div>

                      {/* Decorative line */}
                      <div className="w-8 h-0.5 bg-primary/30 rounded-full mb-2.5" />

                      {/* Section tag */}
                      {chunk.section && (
                        <span className="inline-block px-1.5 py-0.5 text-[9px] font-medium rounded bg-primary/8 text-primary/70 mb-2">
                          {chunk.section}
                        </span>
                      )}

                      {/* Content preview */}
                      <p className="text-xs text-foreground/70 leading-relaxed line-clamp-5 font-body">
                        {chunk.original_content || chunk.content}
                      </p>

                      {/* Meta footer */}
                      <div className="mt-3 flex items-center gap-2 text-[9px] text-muted-foreground/40">
                        <span>{chunk.content.length} 字</span>
                        {chunk.page && <><span>·</span><span>第 {chunk.page} 页</span></>}
                      </div>

                      {/* Hover indicator */}
                      <div className="mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <span className="text-[9px] text-primary/60">点击查看全文 →</span>
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
              {total > pageSize && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handlePageChange(page - 1)}
                    disabled={page === 0}
                    className="px-3 py-1 text-[11px] font-medium rounded-md bg-muted/50 text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  >
                    上一页
                  </button>
                  <span className="text-[10px] text-muted-foreground/50 font-mono">
                    {page + 1} / {Math.ceil(total / pageSize)}
                  </span>
                  <button
                    onClick={() => handlePageChange(page + 1)}
                    disabled={(page + 1) * pageSize >= total}
                    className="px-3 py-1 text-[11px] font-medium rounded-md bg-muted/50 text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  >
                    下一页
                  </button>
                </div>
              )}
              <span className="text-[10px] text-muted-foreground/30 font-mono">
                共 {total} 个片段 · {stats?.source_count ?? 0} 个来源 · 总计 {(stats?.total_chars ?? 0) / 1000}k 字符
              </span>
            </div>
          )}
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
          </DialogHeader>

          <div className="space-y-4">
            {/* Metadata chips */}
            <div className="flex flex-wrap gap-2">
              {selectedChunk?.section && (
                <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-primary/10 text-primary/80">
                  {selectedChunk.section}
                </span>
              )}
              {selectedChunk?.page && (
                <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-muted text-muted-foreground">
                  第 {selectedChunk.page} 页
                </span>
              )}
              <span className="px-2 py-0.5 text-[10px] font-mono rounded-full bg-muted text-muted-foreground">
                {selectedChunk?.chunk_id.slice(0, 24)}…
              </span>
            </div>

            <Separator />

            {/* Full content */}
            <div className="prose-chat text-sm leading-relaxed">
              {selectedChunk?.original_content || selectedChunk?.content}
            </div>

            <div className="text-[10px] text-muted-foreground/40 font-mono">
              {selectedChunk?.content.length} 字符
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
