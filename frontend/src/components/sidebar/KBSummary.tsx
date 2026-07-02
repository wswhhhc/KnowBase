import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import * as api from '@/lib/api'

interface KBSummaryProps {
  workspaceId?: string
}

export default function KBSummary({ workspaceId }: KBSummaryProps) {
  const [stats, setStats] = useState<{ chunk_count: number; source_count: number } | null>(null)
  useEffect(() => {
    let cancelled = false
    setStats(null)
    api.getKBStats(workspaceId)
      .then((nextStats) => {
        if (!cancelled) setStats(nextStats)
      })
      .catch((e: unknown) => {
        if (!cancelled) toast.error('加载工作区统计失败', { description: String(e) })
      })
    return () => { cancelled = true }
  }, [workspaceId])
  return (
    <div className="px-3 py-4">
      <p className="text-xs text-muted-foreground/50 tracking-wide uppercase px-1 mb-2">工作区</p>
      <div className="rounded-lg border border-border bg-surface/30 p-3 space-y-1.5">
        {stats ? (
          <>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">段落</span>
              <span className="font-mono text-foreground/70">{stats.chunk_count}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">引用文档</span>
              <span className="font-mono text-foreground/70">{stats.source_count}</span>
            </div>
          </>
        ) : (
          <p className="text-xs text-muted-foreground/50">加载中…</p>
        )}
      </div>
    </div>
  )
}
