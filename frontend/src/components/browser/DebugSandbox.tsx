import { useState } from 'react'
import { Button, Input } from '@/components/ui'
import { Bug, Loader2 } from 'lucide-react'
import type { DebugSearchResponse, DebugSearchHit } from '@/lib/api'
import * as api from '@/lib/api'

interface DebugSandboxProps {
  onRunSearch: (query: string, strategy: string) => Promise<DebugSearchResponse | null>
}

export default function DebugSandbox({ onRunSearch }: DebugSandboxProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [strategy, setStrategy] = useState<'fast' | 'balanced' | 'high_quality' | 'deep'>('balanced')
  const [results, setResults] = useState<DebugSearchResponse | null>(null)
  const [searching, setSearching] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    setSearching(true)
    try {
      const res = await onRunSearch(query, strategy)
      setResults(res)
    } catch { /* error handled by caller */ }
    setSearching(false)
  }

  const renderSection = (title: string, hits: DebugSearchHit[], scoreMode: 'vector' | 'bm25' | 'rrf') => (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <h4 className="text-2xs font-medium text-foreground/80">{title}</h4>
        <span className="text-2xs text-muted-foreground/40">{hits.length} 条</span>
      </div>
      {hits.length === 0 ? (
        <div className="rounded border border-dashed border-border/60 px-2 py-3 text-2xs text-muted-foreground/50">没有命中结果</div>
      ) : (
        <div className="space-y-1 max-h-52 overflow-y-auto">
          {hits.map((hit) => (
            <div key={`${title}-${hit.chunk_id}`} className="rounded border border-border/50 p-2 text-xs">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-2xs font-mono text-primary/60">
                  #{scoreMode === 'vector' ? hit.vector_rank : scoreMode === 'bm25' ? hit.bm25_rank : hit.rrf_rank}
                </span>
                <span className="text-2xs font-mono text-muted-foreground/40 truncate">{hit.chunk_id}</span>
              </div>
              <p className="text-2xs text-muted-foreground/50 truncate mb-1">{hit.source}</p>
              <p className="text-2xs text-foreground/70 line-clamp-3 mb-1">{hit.content}</p>
              <div className="flex flex-wrap gap-3 text-2xs text-muted-foreground/40 font-mono">
                {scoreMode === 'vector' && <span>向量: {hit.vector_score?.toFixed(4) ?? '-'}</span>}
                {scoreMode === 'bm25' && <span>BM25: {hit.bm25_score?.toFixed(4) ?? '-'}</span>}
                {scoreMode === 'rrf' && <span>RRF: {hit.rrf_score?.toFixed(4) ?? '-'}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )

  return (
    <div className="border-b border-border">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-5 py-2 w-full text-left text-2xs text-muted-foreground/50 hover:text-muted-foreground transition-colors"
      >
        <Bug className="h-3 w-3" />
        检索测试沙盒
        <span className="text-2xs text-muted-foreground/30 mr-1">高级功能</span>
        <span className="ml-auto">{open ? '收起' : '展开'}</span>
      </button>
      {open && (
        <div className="px-5 pb-3 space-y-3">
          <div className="flex flex-wrap gap-1">
            {(['fast', 'balanced', 'high_quality', 'deep'] as const).map((opt) => (
              <button key={opt}
                onClick={() => { setStrategy(opt); if (query.trim()) onRunSearch(query, opt) }}
                className={`rounded-md px-2 py-1 text-2xs transition-colors ${strategy === opt ? 'bg-primary/15 text-primary' : 'bg-muted/50 text-muted-foreground hover:text-foreground'}`}>
                {{ fast: '快速', balanced: '标准', high_quality: '严谨', deep: '深度' }[opt]}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <Input placeholder="输入测试查询…" value={query} onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSearch() }} className="flex-1 h-8 text-xs" />
            <Button size="sm" onClick={handleSearch} disabled={searching}>
              {searching ? <Loader2 className="h-3 w-3 animate-spin" /> : '检索'}
            </Button>
          </div>
          {results && (
            <div className="grid gap-3 md:grid-cols-3">
              {renderSection('向量 Top-5', results.vector_results, 'vector')}
              {renderSection('BM25 Top-5', results.bm25_results, 'bm25')}
              {renderSection('RRF 融合', results.fused_results, 'rrf')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
