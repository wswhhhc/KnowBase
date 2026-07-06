import { Button, ScrollArea, SkeletonGrid } from '@/components/ui'
import { BookOpen, AlertTriangle, Sparkles, X, Upload } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import type { ViewType } from '@/app/navigation'
import BrowserHeader from '@/components/browser/BrowserHeader'
import ChunkDetailDialog from '@/components/browser/ChunkDetailDialog'
import DebugSandbox from '@/components/browser/DebugSandbox'
import DocumentActions from '@/components/browser/DocumentActions'
import GridView from '@/components/browser/GridView'
import SearchToolbar from '@/components/browser/SearchToolbar'
import SliceView from '@/components/browser/SliceView'
import { useBrowserPage } from '@/features/knowledge-browser/hooks/useBrowserPage'

interface BrowserPageProps {
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
  highlightChunkId?: string | null
  onHighlightConsumed?: () => void
  workspaceId?: string
  workspaceName?: string
  canManageKnowledgeBase?: boolean
}

export default function BrowserPage({
  onOpenSidebar,
  sidebarOpen,
  onNavigate,
  highlightChunkId,
  onHighlightConsumed,
  workspaceId,
  workspaceName = '默认工作区',
  canManageKnowledgeBase = true,
}: BrowserPageProps) {
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
  } = useBrowserPage({
    highlightChunkId,
    onHighlightConsumed,
    workspaceId,
  })

  const contentStateKey = loading
    ? 'loading'
    : displayChunks.length === 0
      ? 'empty'
      : chunkView === 'slice' && selectedSource
        ? 'slice'
        : 'grid'

  const hasDocuments = (stats?.source_count ?? 0) > 0 || sources.length > 0
  const hasActiveFilters = Boolean(searchQuery || selectedSource)

  return (
    <div className="flex flex-col h-full">
      {canManageKnowledgeBase && (
        <input type="file" ref={fileInputRef} className="hidden" accept=".txt,.md,.pdf,.docx,.html"
          onChange={async (e) => { const f = e.target.files?.[0]; if (f) await startUpload(f) }} />
      )}

      <BrowserHeader
        stats={stats}
        onOpenSidebar={onOpenSidebar}
        sidebarOpen={sidebarOpen}
        onNavigate={onNavigate}
        workspaceName={workspaceName}
      />

      {canManageKnowledgeBase ? (
        <DocumentActions uploading={uploading} ingesting={ingesting} uploadPhase={uploadPhase} uploadPercent={uploadPercent}
          urlInput={urlInput} setUrlInput={setUrlInput} handleIngestUrl={() => { const u = urlInput.trim(); if (u) startUrlIngest(u) }}
          refreshData={refreshData} onUploadClick={() => fileInputRef.current?.click()} />
      ) : (
        <div className="border-b border-border bg-muted/20 px-5 py-3 text-xs text-muted-foreground">
          当前账号可浏览和问答，导入、替换、删除资料需要编辑者或管理员权限。
        </div>
      )}

      {canManageKnowledgeBase && versionPrompted && (
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

      <DebugSandbox key={workspaceId || ''} onRunSearch={runDebugSearch} />

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
            <AnimatePresence initial={false}>
              {canManageKnowledgeBase && showPostUploadGuide && (
                <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
                  className="mb-4 flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
                  <div>
                    <p className="text-xs font-medium text-foreground/85">资料已进入“{workspaceName}”</p>
                    <p className="mt-1 text-2xs text-muted-foreground">
                      {lastImportedSource
                        ? `已切到刚导入的来源“${lastImportedSource}”，你可以先核对原文、去提问，或继续导入更多资料。`
                        : '现在可以去提问、继续核对原文，或继续导入更多资料。'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button size="sm" onClick={() => onNavigate('chat')} className="gap-1"><Sparkles className="h-3 w-3" />去当前工作区提问</Button>
                    {lastImportedSource && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          void focusSource(lastImportedSource)
                          setShowPostUploadGuide(false)
                        }}
                        className="gap-1"
                      >
                        <BookOpen className="h-3 w-3" />查看当前来源
                      </Button>
                    )}
                    <Button size="sm" variant="outline" onClick={() => fileInputRef.current?.click()} className="gap-1">
                      <Upload className="h-3 w-3" />继续导入
                    </Button>
                    <button onClick={() => setShowPostUploadGuide(false)}
                      className="rounded-md p-1 text-muted-foreground/40 transition-colors hover:bg-muted/50 hover:text-foreground"
                      aria-label="关闭提示">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={contentStateKey}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
              >
                {loading ? <SkeletonGrid count={6} /> : displayChunks.length === 0 ? (
                  <BrowserEmptyState
                    workspaceName={workspaceName}
                    hasDocuments={hasDocuments}
                    hasActiveFilters={hasActiveFilters}
                    onPrimaryAction={
                      hasDocuments
                        ? () => { void resetBrowseFilters() }
                        : canManageKnowledgeBase
                          ? () => fileInputRef.current?.click()
                          : undefined
                    }
                    onSecondaryAction={hasDocuments ? () => onNavigate('chat') : undefined}
                    primaryLabel={hasDocuments ? '清空筛选' : canManageKnowledgeBase ? '上传文档' : undefined}
                    secondaryLabel={hasDocuments ? '去聊天页提问' : undefined}
                  />
                ) : chunkView === 'slice' && selectedSource ? (
                  <SliceView chunks={displayChunks} kbConfig={kbConfig} hotspotMode={hotspotMode} hotspotCount={hotspotCount}
                    findOverlap={findOverlap} onChunkClick={setSelectedChunk} bookmarkedChunks={bookmarkedChunks} onBookmark={handleChunkBookmark} />
                ) : (
                  <GridView chunks={displayChunks} hotspotMode={hotspotMode} hotspotCount={hotspotCount}
                    onChunkClick={setSelectedChunk} bookmarkedChunks={bookmarkedChunks} onBookmark={handleChunkBookmark} />
                )}
              </motion.div>
            </AnimatePresence>
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

interface BrowserEmptyStateProps {
  workspaceName: string
  hasDocuments: boolean
  hasActiveFilters: boolean
  onPrimaryAction?: () => void
  onSecondaryAction?: () => void
  primaryLabel?: string
  secondaryLabel?: string
}

function BrowserEmptyState({
  workspaceName,
  hasDocuments,
  hasActiveFilters,
  onPrimaryAction,
  onSecondaryAction,
  primaryLabel,
  secondaryLabel,
}: BrowserEmptyStateProps) {
  const title = hasDocuments ? '当前工作区没有匹配结果' : '当前工作区还没有资料'
  const description = hasDocuments
    ? hasActiveFilters
      ? '先清空筛选或切回全部来源，再决定是去提问还是继续补充资料。'
      : '当前工作区暂无可浏览的段落，可以继续导入更相关的资料。'
    : '先导入文档或网页内容，再回来提问和验证来源。'

  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <BookOpen className="mb-4 h-12 w-12 text-muted-foreground/20" />
      <p className="text-sm font-medium text-foreground/85">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground/70">{workspaceName}</p>
      <p className="mt-2 max-w-md text-xs text-muted-foreground/60">{description}</p>
      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        {primaryLabel && onPrimaryAction && (
          <Button size="sm" onClick={onPrimaryAction}>{primaryLabel}</Button>
        )}
        {secondaryLabel && onSecondaryAction && (
          <Button size="sm" variant="outline" onClick={onSecondaryAction}>{secondaryLabel}</Button>
        )}
      </div>
    </div>
  )
}
