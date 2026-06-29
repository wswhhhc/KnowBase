import { motion, AnimatePresence } from 'framer-motion'
import { Bookmark, BookmarkCheck, Flame } from 'lucide-react'
import type { KBChunk } from '@/lib/api'

interface GridViewProps {
  chunks: KBChunk[]
  hotspotMode: boolean
  hotspotCount: (chunkId: string) => number
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

export default function GridView({ chunks, hotspotMode, hotspotCount, onChunkClick, bookmarkedChunks, onBookmark }: GridViewProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <AnimatePresence>
        {chunks.map((chunk, i) => {
          const hc = hotspotCount(chunk.chunk_id)
          return (
            <motion.div
              key={chunk.chunk_id}
              id={`chunk-${chunk.chunk_id}`}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: (i % 12) * 0.04, duration: 0.3 }}
              onClick={() => onChunkClick(chunk)}
              className="group cursor-pointer rounded-lg border border-border bg-surface/30 p-4 hover:border-primary/20 hover:bg-surface/60 transition-all"
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="text-2xs font-mono text-muted-foreground/50 tracking-wider uppercase">{chunk.source}</span>
                <span className="flex items-center gap-1">
                  {hotspotMode && (
                    <span className={`text-2xs font-mono ${hotspotColor(hc)}`}>
                      <Flame className="inline h-2.5 w-2.5 mr-0.5" />{hc}
                    </span>
                  )}
                  <span className="text-2xs font-mono text-muted-foreground/30">#{chunk.chunk_index}</span>
                </span>
              </div>
              <div className="w-8 h-0.5 bg-primary/30 rounded-full mb-2.5" />
              {chunk.section && (
                <span className="inline-block px-1.5 py-0.5 text-2xs font-medium rounded bg-primary/8 text-primary/70 mb-2">{chunk.section}</span>
              )}
              <p className="text-xs text-foreground/70 leading-relaxed line-clamp-5 font-body">
                {chunk.original_content || chunk.content}
              </p>
              <div className="mt-3 flex items-center gap-2 text-2xs text-muted-foreground/40">
                <span>{chunk.content.length} 字</span>
                {chunk.page && <><span>·</span><span>第 {chunk.page} 页</span></>}
                <button onClick={(e) => { e.stopPropagation(); onBookmark(chunk) }}
                  className={`ml-auto ${bookmarkedChunks.has(chunk.chunk_id) ? 'text-amber-400' : 'text-muted-foreground/20 hover:text-amber-400'} transition-colors`}
                  title={bookmarkedChunks.has(chunk.chunk_id) ? '已收藏' : '收藏此段落'}>
                  {bookmarkedChunks.has(chunk.chunk_id) ? <BookmarkCheck className="h-3 w-3" /> : <Bookmark className="h-3 w-3" />}
                </button>
              </div>
              <div className="mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="text-2xs text-primary/60">点击查看全文 →</span>
              </div>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
