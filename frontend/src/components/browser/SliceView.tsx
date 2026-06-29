import { motion } from 'framer-motion'
import { Bookmark, BookmarkCheck, Flame } from 'lucide-react'
import type { KBChunk } from '@/lib/api'

interface SliceViewProps {
  chunks: KBChunk[]
  kbConfig: { chunk_size: number } | null
  hotspotMode: boolean
  hotspotCount: (chunkId: string) => number
  findOverlap: (prev: string, curr: string) => number
  onChunkClick: (chunk: KBChunk) => void
  bookmarkedChunks: Set<string>
  onBookmark: (chunk: KBChunk) => void | Promise<void>
}

function hotspotColor(count: number): string {
  if (count <= 0) return 'text-muted-foreground/20'
  if (count <= 2) return 'text-muted-foreground/50'
  if (count <= 5) return 'text-orange-400/70'
  return 'text-red-400/80'
}

export default function SliceView({ chunks, kbConfig, hotspotMode, hotspotCount, findOverlap, onChunkClick, bookmarkedChunks, onBookmark }: SliceViewProps) {
  return (
    <div className="max-w-2xl mx-auto space-y-3">
      {chunks.map((chunk, i) => {
        const overlapLen = i > 0 ? findOverlap(chunks[i - 1].content, chunk.content) : 0
        const content = chunk.original_content || chunk.content
        const hc = hotspotCount(chunk.chunk_id)
        return (
          <motion.div
            key={chunk.chunk_id}
            id={`chunk-${chunk.chunk_id}`}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.03, duration: 0.25 }}
            onClick={() => onChunkClick(chunk)}
            className="group cursor-pointer rounded-lg border border-border bg-surface/30 p-3.5 hover:border-primary/20 transition-all"
          >
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
            <p className="text-xs text-foreground/70 leading-relaxed font-body">
              {overlapLen > 0 ? (
                <>
                  <mark className="bg-yellow-500/15 text-foreground/80 rounded-sm px-0.5">{content.slice(0, overlapLen)}</mark>
                  {content.slice(overlapLen)}
                </>
              ) : content}
            </p>
            <div className="mt-2 h-0.5 w-full rounded-full bg-muted/30">
              <div className="h-full rounded-full bg-primary/20" style={{ width: `${(chunk.content.length / (kbConfig?.chunk_size || 1000)) * 100}%` }} />
            </div>
            <div className="mt-1.5 flex items-center justify-end">
              <button onClick={(e) => { e.stopPropagation(); onBookmark(chunk) }}
                className={`${bookmarkedChunks.has(chunk.chunk_id) ? 'text-amber-400' : 'text-muted-foreground/20 hover:text-amber-400'} transition-colors`}
                title={bookmarkedChunks.has(chunk.chunk_id) ? '已收藏' : '收藏此段落'}>
                {bookmarkedChunks.has(chunk.chunk_id) ? <BookmarkCheck className="h-3 w-3" /> : <Bookmark className="h-3 w-3" />}
              </button>
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}
