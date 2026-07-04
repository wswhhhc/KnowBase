import { useEffect, useRef, useState } from 'react'

import { useBrowserHighlight } from '@/features/knowledge-browser/hooks/useBrowserHighlight'
import { useBrowserCatalogState } from '@/features/knowledge-browser/hooks/useBrowserCatalogState'
import { useBrowserHotspots } from '@/features/knowledge-browser/hooks/useBrowserHotspots'
import { useBrowserImport } from '@/features/knowledge-browser/hooks/useBrowserImport'
import { useBrowserWorkspaceLifecycle } from '@/features/knowledge-browser/hooks/useBrowserWorkspaceLifecycle'

interface UseBrowserPageArgs {
  highlightChunkId?: string | null
  onHighlightConsumed?: () => void
  workspaceId?: string
}

export function useBrowserPage({
  highlightChunkId,
  onHighlightConsumed,
  workspaceId,
}: UseBrowserPageArgs) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)

  const browserWsId = workspaceId || ''
  const {
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
  } = useBrowserCatalogState({ browserWsId })
  const {
    hotspotMode,
    setHotspotMode,
    hotspots,
    setHotspots,
    toggleHotspotMode,
    hotspotCount,
  } = useBrowserHotspots(browserWsId, isScopeCurrent, getScopeToken)

  const {
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
    resetImportState,
    startUpload,
    startUrlIngest,
  } = useBrowserImport({
    browserWsId,
    fileInputRef,
    refreshData,
    focusSource,
    isScopeCurrent,
    getScopeToken,
  })

  useBrowserWorkspaceLifecycle({
    browserWsId,
    fileInputRef,
    isScopeCurrent,
    loadInitialCatalogData,
    nextScopeToken,
    resetCatalogState,
    resetImportState,
    setError,
    setHotspotMode,
    setHotspots,
    setLoading,
  })

  useBrowserHighlight({
    highlightChunkId,
    onHighlightConsumed,
    browserWsId,
    allChunksRef,
    setChunks,
    setSelectedChunk,
    dedupeChunksById,
  })

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
