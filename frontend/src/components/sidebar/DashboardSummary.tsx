import { useEffect, useState } from 'react'
import * as api from '@/lib/api'

export default function DashboardSummary() {
  const [total, setTotal] = useState<number | null>(null)
  const [lastQuery, setLastQuery] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api.queryLogs(7, 100)
      .then((logs) => {
        if (cancelled) return
        setTotal(logs.length)
        if (logs.length > 0) {
          const recent = logs.reduce((a, b) =>
            new Date(a.timestamp) > new Date(b.timestamp) ? a : b,
          )
          setLastQuery(recent.question.slice(0, 24))
        }
      })
      .catch(() => { /* silent */ })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  return (
    <div className="px-3 py-4">
      <p className="text-xs text-muted-foreground/50 tracking-wide uppercase px-1 mb-2">快速统计</p>
      <div className="rounded-lg border border-border bg-surface/30 p-3 space-y-2">
        {loading ? (
          <div className="space-y-2">
            <div className="h-3 bg-muted rounded w-2/3 animate-pulse" />
            <div className="h-3 bg-muted rounded w-1/2 animate-pulse" />
          </div>
        ) : total !== null ? (
          <>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">总查询</span>
              <span className="font-mono text-foreground/80">{total} 次</span>
            </div>
            {lastQuery && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">最近</span>
                <span className="font-mono text-foreground/60 truncate max-w-[8rem]">{lastQuery}</span>
              </div>
            )}
          </>
        ) : (
          <p className="text-2xs text-muted-foreground/50">暂无数据</p>
        )}
      </div>
    </div>
  )
}
