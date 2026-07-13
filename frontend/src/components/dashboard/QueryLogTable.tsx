import { ChevronDown, ChevronUp, Globe } from 'lucide-react'
import { motion } from 'framer-motion'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui'
import type { QueryLogEntry } from '@/shared/api'

interface QueryLogTableProps {
  logs: QueryLogEntry[]
  showAllLogs: boolean
  onShowAllLogsChange: (showAllLogs: boolean) => void
}

export default function QueryLogTable({ logs, showAllLogs, onShowAllLogsChange }: QueryLogTableProps) {
  const visibleLogs = showAllLogs ? logs : logs.slice(0, 15)

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.35, duration: 0.4 }}
      className="rounded-lg border border-border bg-surface/30 p-5"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-heading text-sm text-foreground tracking-tight">
          查询日志
          <span className="text-2xs text-muted-foreground/50 font-mono ml-2 font-normal">共 {logs.length} 条</span>
        </h3>
        {logs.length > 15 && (
          <button onClick={() => onShowAllLogsChange(!showAllLogs)}
            className="flex items-center gap-1 text-2xs text-primary/60 hover:text-primary transition-colors">
            {showAllLogs ? <><ChevronUp className="h-3 w-3" />收起</> : <><ChevronDown className="h-3 w-3" />全部加载</>}
          </button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-2 pr-4 text-muted-foreground font-medium">时间</th>
              <th className="text-left py-2 pr-4 text-muted-foreground font-medium">问题</th>
              <th className="text-right py-2 pr-4 text-muted-foreground font-medium">耗时</th>
              <th className="text-right py-2 pr-4 text-muted-foreground font-medium">检索</th>
              <th className="text-center py-2 text-muted-foreground font-medium">质量</th>
              <th className="text-right py-2 pr-4 text-muted-foreground font-medium">Token</th>
              <th className="text-right py-2 text-muted-foreground font-medium">费用</th>
            </tr>
          </thead>
          <tbody>
            {visibleLogs.map((log, index) => (
              <tr key={index} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                <td className="py-2 pr-4 text-muted-foreground font-mono whitespace-nowrap">
                  {new Date(log.timestamp).toLocaleString('zh-CN', {
                    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
                  })}
                </td>
                <td className="py-2 pr-4 text-foreground/80 truncate max-w-[200px]">{log.question}</td>
                <td className="py-2 pr-4 text-right text-muted-foreground font-mono">{log.elapsed_ms}ms</td>
                <td className="py-2 pr-4 text-right text-muted-foreground font-mono">{log.retrieval_count}</td>
                <td className="py-2 text-center">
                  <span className={`inline-flex items-center gap-1 text-2xs ${log.quality_ok ? 'text-emerald-400' : 'text-red-400'}`}>
                    {log.quality_ok ? '✓ 通过' : '✗ 失败'}
                    {log.used_web_search && <Globe className="h-2.5 w-2.5 inline" />}
                  </span>
                </td>
                <td className="py-2 pr-4 text-right text-muted-foreground font-mono">
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="cursor-default">{log.token_count?.toLocaleString() ?? '-'}</span>
                      </TooltipTrigger>
                      {log.llm_model && <TooltipContent><p className="text-2xs">{log.llm_model}</p></TooltipContent>}
                    </Tooltip>
                  </TooltipProvider>
                </td>
                <td className="py-2 text-right text-muted-foreground font-mono">
                  {log.estimated_cost ? `¥${log.estimated_cost.toFixed(4)}` : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}
