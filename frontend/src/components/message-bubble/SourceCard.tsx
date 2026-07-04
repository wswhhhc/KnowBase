import { ExternalLink, MessageSquare, Pin, X } from 'lucide-react'
import type { Source } from '@/shared/api'
import type { PinnedSource } from '@/hooks/useChat'
import { useChatContext } from './ChatContext'

interface SourceCardProps {
  source: Source
  pinnedState?: PinnedSource
}

export default function SourceCard({
  source,
  pinnedState,
}: SourceCardProps) {
  const { onCitationClick, onSendQuestion, onPinToggle } = useChatContext()
  const isExcluded = pinnedState?.excluded
  const isPinned = pinnedState?.pinned

  return (
    <div
      className={`source-card rounded-lg border px-3.5 py-2.5 transition-all ${
        isExcluded ? 'border-destructive/20 bg-destructive/5 opacity-50' : isPinned ? 'border-primary/30 bg-primary/5' : 'border-border bg-surface/50'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium text-foreground/80 truncate flex items-center gap-1">
          <span className="text-2xs text-muted-foreground/40 font-mono">#{source.index}</span>
          {source.source}
          {source.chunk_index !== undefined ? ` #${source.chunk_index}` : ''}
          {source.page ? ` · p.${source.page}` : ''}
        </span>
        {source.score != null && (
          <span className={`text-2xs flex-shrink-0 font-mono ${source.score < 0.1 ? 'text-muted-foreground/30' : 'text-muted-foreground'}`}>
            {source.score < 0.1 && '相关性较低 '}
            {source.score.toFixed(4)}
          </span>
        )}
      </div>

      {source.url && <p className="text-2xs text-primary/50 truncate mt-0.5">{source.url}</p>}
      <p className="text-xs text-muted-foreground mt-1.5 line-clamp-3 leading-relaxed">{source.content}</p>

      <div className="mt-1.5 flex items-center gap-2">
        {onCitationClick && !isExcluded && (
          <button
            onClick={() => onCitationClick(source)}
            className="inline-flex items-center gap-1 text-2xs text-primary/50 hover:text-primary transition-colors"
          >
            <ExternalLink className="h-2.5 w-2.5" />
            在当前工作区查看原文
          </button>
        )}
        {onSendQuestion && !isExcluded && (
          <button
            onClick={() => onSendQuestion(`关于「${source.source}」中的内容，请详细解释`)}
            className="inline-flex items-center gap-1 text-2xs text-muted-foreground/50 hover:text-muted-foreground transition-colors"
          >
            <MessageSquare className="h-2.5 w-2.5" />
            追问
          </button>
        )}
        {onPinToggle && (
          <button
            onClick={() => onPinToggle(source.chunk_id || '', isPinned ? 'unpin' : 'pin')}
            className={`ml-auto inline-flex items-center gap-1 text-2xs transition-colors ${
              isPinned ? 'text-primary/70' : 'text-muted-foreground/30 hover:text-muted-foreground'
            }`}
          >
            <Pin className={`h-3 w-3 ${isPinned ? 'fill-current' : ''}`} />
            {isPinned ? '已固定' : '固定'}
          </button>
        )}
        {onPinToggle && (
          <button
            onClick={() => onPinToggle(source.chunk_id || '', isExcluded ? 'unexclude' : 'exclude')}
            className={`inline-flex items-center gap-1 text-2xs transition-colors ${
              isExcluded ? 'text-destructive/70' : 'text-muted-foreground/30 hover:text-muted-foreground'
            }`}
          >
            <X className="h-3 w-3" />
            {isExcluded ? '已排除' : '排除'}
          </button>
        )}
      </div>
    </div>
  )
}
