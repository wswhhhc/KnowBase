import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bug, ChevronDown, ChevronRight, Search, Globe, RotateCcw, Zap } from 'lucide-react'
import type { DebugInfo } from '@/lib/api'

interface DebugPanelProps {
  debugData: DebugInfo
}

export default function DebugPanel({ debugData }: DebugPanelProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1 text-[11px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
      >
        <Bug className="h-3 w-3" />
        {open ? '收起链路详情' : '链路详情'}
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-1.5 overflow-hidden"
          >
            <div className="rounded-lg border border-border/60 bg-surface/40 px-3 py-2.5 font-mono text-[11px] leading-relaxed">
              {/* Node timeline */}
              <div className="space-y-1">
                {debugData.nodes.map((node, i) => (
                  <div key={node.name} className="flex items-center gap-2">
                    <span className={`flex-shrink-0 w-1.5 h-1.5 rounded-full ${
                      node.elapsed_ms > 0 ? 'bg-emerald-500/60' : 'bg-muted-foreground/20'
                    }`} />
                    <span className="text-foreground/70 min-w-[64px]">{node.label}</span>
                    <span className="text-muted-foreground/40 w-12 text-right tabular-nums">
                      {node.elapsed_ms > 0 ? `${node.elapsed_ms}ms` : '-'}
                    </span>
                    <span className="text-muted-foreground/60 truncate">{node.summary}</span>
                  </div>
                ))}
              </div>

              {/* Divider */}
              <div className="my-2 border-t border-border/40" />

              {/* Summary fields */}
              <div className="space-y-1 text-muted-foreground/70">
                {debugData.used_rewrite && debugData.rewritten_question && (
                  <div className="flex items-start gap-2">
                    <Search className="h-3 w-3 mt-0.5 flex-shrink-0 text-primary/60" />
                    <span>改写后: <span className="text-foreground/80">{debugData.rewritten_question}</span></span>
                  </div>
                )}
                <div className="flex items-center gap-3 flex-wrap">
                  {debugData.used_web_search && (
                    <span className="flex items-center gap-1">
                      <Globe className="h-3 w-3 text-sky-500/60" />
                      联网 {debugData.web_results_count} 条
                    </span>
                  )}
                  {debugData.used_rerank && (
                    <span className="flex items-center gap-1">
                      <Zap className="h-3 w-3 text-amber-500/60" />
                      rerank {debugData.candidates_before}→{debugData.after_rerank}
                    </span>
                  )}
                  {debugData.retry_count > 0 && (
                    <span className="flex items-center gap-1">
                      <RotateCcw className="h-3 w-3 text-orange-500/60" />
                      重试 {debugData.retry_count} 次
                    </span>
                  )}
                </div>
                {!debugData.quality_passed && (
                  <div className="text-red-400/80 text-[10px] mt-1">
                    质量检查未通过: {debugData.quality_reason}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
