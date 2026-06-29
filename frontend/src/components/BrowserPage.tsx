import { Button, ScrollArea, SkeletonGrid } from '@/components/ui'
import { BookOpen, AlertTriangle, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'
import type { ViewType } from '@/App'
import { useBrowserPage } from '@/hooks/useBrowserPage'
import BrowserHeader from './browser/BrowserHeader'
import DocumentActions from './browser/DocumentActions'
import SearchToolbar from './browser/SearchToolbar'
import DebugSandbox from './browser/DebugSandbox'
import GridView from './browser/GridView'
import SliceView from './browser/SliceView'
import ChunkDetailDialog from './browser/ChunkDetailDialog'

interface BrowserPageProps {
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
  highlightChunkId?: string | null
  onHighlightConsumed?: () => void
  workspaceId?: string
}

export default function BrowserPage({ onOpenSidebar, sidebarOpen, onNavigate, highlightChunkId, onHighlightConsumed, workspaceId }: BrowserPageProps) {
  const {
    fileInputRef,
    scrollRef,
    sentinelRef,
    stats,
    loading,
    error,
    searchQuery,
    setSearchQuery,
    selectedSource,
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
    total,
    hasMore,
    bookmarkedChunks,
    displayChunks,
    hotspotCount,
    findOverlap,
    refreshData,
    handleSearch,
    handleSourceClick,
    startUpload,
    startUrlIngest,
    toggleHotspotMode,
    handleChunkBookmark,
    runDebugSearch,
  } = useBrowserPage({
    highlightChunkId,
    onHighlightConsumed,
    workspaceId,
  })

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
