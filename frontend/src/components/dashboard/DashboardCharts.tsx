import { motion } from 'framer-motion'
import { Progress, Separator, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui'
import type { QueryLogEntry } from '@/shared/api'
import type { DashboardMetrics } from '@/features/dashboard/model/dashboardMetrics'

interface DashboardChartsProps {
  logs: QueryLogEntry[]
  metrics: DashboardMetrics
}

export default function DashboardCharts({ logs, metrics }: DashboardChartsProps) {
  const { stats, hourlyData, maxHourlyCount, maxHourlyTokens, tokenLinePoints } = metrics

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.4 }}
        className="rounded-lg border border-border bg-surface/30 p-5 mb-6"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-heading text-sm text-foreground tracking-tight">小时分布</h3>
          <span className="text-2xs text-muted-foreground/50 font-mono">
            avg {stats.avgElapsed}ms · 峰值 {maxHourlyTokens.toLocaleString()} tokens
          </span>
        </div>
        <div className="relative h-40 pt-5">
          <div className="absolute inset-0 flex items-end gap-1 pt-5">
            {hourlyData.map((hour) => (
              <TooltipProvider key={hour.hour}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="flex-1 flex flex-col items-center gap-1">
                      <span className="text-2xs text-muted-foreground/50 font-mono h-3">
                        {hour.count > 0 ? hour.count : ''}
                      </span>
                      <div
                        className="w-full rounded-t-sm bg-primary/60 hover:bg-primary/80 transition-colors cursor-pointer"
                        style={{ height: hour.count > 0 ? `${Math.max((hour.count / maxHourlyCount) * 104, 10)}px` : '0px' }}
                      />
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    {hour.hour}:00 — {hour.count} 次查询 · {hour.tokens.toLocaleString()} tokens · avg {hour.avgMs}ms
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ))}
          </div>
          <svg className="pointer-events-none absolute inset-0 h-full w-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 100">
            <polyline
              fill="none"
              points={tokenLinePoints}
              stroke="currentColor"
              strokeWidth="1.5"
              className="text-amber-400/90"
              vectorEffect="non-scaling-stroke"
            />
            {hourlyData.map((hour, index) => (
              <circle
                key={hour.hour}
                cx={(index / (hourlyData.length - 1)) * 100}
                cy={100 - (hour.tokens / maxHourlyTokens) * 100}
                r="1.2"
                className="fill-amber-400"
              />
            ))}
          </svg>
        </div>
        <div className="flex justify-between mt-2 text-2xs text-muted-foreground/40 font-mono">
          {[0, 6, 12, 18, 23].map((hour) => <span key={hour}>{hour}:00</span>)}
        </div>
        <div className="mt-2 flex items-center justify-between text-2xs text-muted-foreground/45">
          <span>柱状: 查询次数</span>
          <span>折线: Token /h</span>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.4 }}
          className="rounded-lg border border-border bg-surface/30 p-5"
        >
          <h3 className="font-heading text-sm text-foreground tracking-tight mb-4">质量分布</h3>
          <div className="space-y-3">
            {[
              { label: '通过', count: stats.qualityPassed, color: 'emerald' as const },
              { label: '未通过', count: stats.qualityFailed, color: 'red' as const },
              { label: '错误', count: stats.errorCount, color: 'violet' as const },
            ].map((item) => {
              const pct = (item.count / stats.total) * 100
              return (
                <div key={item.label}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-muted-foreground">{item.label}</span>
                    <span className="font-mono text-foreground/70">{item.count} / {pct.toFixed(0)}%</span>
                  </div>
                  <Progress value={pct} color={item.color} />
                </div>
              )
            })}
            <Separator className="my-4" />
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-muted-foreground">联网补充</span>
                <span className="font-mono text-foreground/70">{stats.webSearchCount} / {(stats.webSearchRate * 100).toFixed(0)}%</span>
              </div>
              <Progress value={stats.webSearchRate * 100} color="amber" />
              <p className="text-2xs text-muted-foreground/50 mt-1">单独统计联网补充，不再和质量等级混算。</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.4 }}
          className="rounded-lg border border-border bg-surface/30 p-5"
        >
          <h3 className="font-heading text-sm text-foreground tracking-tight mb-4">最近查询</h3>
          <div className="space-y-2">
            {logs.slice(0, 6).map((log, index) => (
              <div key={index} className="flex items-center justify-between gap-2 text-xs">
                <span className="truncate text-muted-foreground flex-1">{log.question}</span>
                <span className="text-muted-foreground/50 font-mono flex-shrink-0">{log.elapsed_ms}ms</span>
                <span className={`flex-shrink-0 ${log.quality_ok ? 'text-emerald-400' : 'text-red-400'}`}>
                  {log.quality_ok ? '✓' : '✗'}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </>
  )
}
