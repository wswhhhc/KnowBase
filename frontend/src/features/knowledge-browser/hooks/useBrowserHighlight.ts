import type { MutableRefObject } from 'react'
import { useEffect } from 'react'
import { toast } from 'sonner'

import * as api from '@/lib/api'
import type { KBChunk } from '@/lib/api'

interface BrowserHighlightOptions {
  highlightChunkId?: string | null
  onHighlightConsumed?: () => void
  browserWsId: string
  allChunksRef: MutableRefObject<KBChunk[]>
  setChunks: (chunks: KBChunk[]) => void
  setSelectedChunk: (chunk: KBChunk | null) => void
  dedupeChunksById: (items: KBChunk[]) => KBChunk[]
}

export function useBrowserHighlight({
  highlightChunkId,
  onHighlightConsumed,
  browserWsId,
  allChunksRef,
  setChunks,
  setSelectedChunk,
  dedupeChunksById,
}: BrowserHighlightOptions) {
  useEffect(() => {
    if (!highlightChunkId) return
    const existing = allChunksRef.current.find((chunk) => chunk.chunk_id === highlightChunkId)
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
  }, [allChunksRef, browserWsId, dedupeChunksById, highlightChunkId, onHighlightConsumed, setChunks, setSelectedChunk])
}
