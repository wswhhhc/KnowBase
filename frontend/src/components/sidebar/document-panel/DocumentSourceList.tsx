import { Trash2 } from 'lucide-react'
import type { DocSource } from '@/shared/api'

interface DocumentSourceListProps {
  sources: DocSource[]
  canManageKnowledgeBase: boolean
  onClear: () => void
  onDelete: (sourceName: string) => void
}

export default function DocumentSourceList({ sources, canManageKnowledgeBase, onClear, onDelete }: DocumentSourceListProps) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">引用文档</span>
        {canManageKnowledgeBase && sources.length > 0 && (
          <button onClick={onClear} className="text-2xs text-destructive/50 transition-colors hover:text-destructive">清空</button>
        )}
      </div>
      <div className="space-y-0.5">
        {sources.map((source) => (
          <div key={source.source} className="group flex items-center justify-between rounded-md px-2.5 py-1.5 text-sm text-foreground/70 transition-colors hover:bg-muted">
            <span className="flex-1 truncate">{source.source}</span>
            <span className="mr-2 font-mono text-2xs text-muted-foreground">{source.count} 段落</span>
            {canManageKnowledgeBase && (
              <button onClick={() => onDelete(source.source)} className="text-muted-foreground opacity-0 transition-all hover:text-destructive group-hover:opacity-100">
                <Trash2 className="h-3 w-3" />
              </button>
            )}
          </div>
        ))}
        {sources.length === 0 && <p className="py-6 text-center text-xs italic text-muted-foreground/60">知识库为空</p>}
      </div>
    </div>
  )
}
