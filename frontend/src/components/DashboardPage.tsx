import { useEffect, useState } from 'react'
import { Button, ScrollArea } from '@/components/ui'
import { BarChart3, PanelRightOpen, ArrowLeft, TrendingUp, Clock, CheckCircle2, XCircle, HelpCircle, AlertTriangle, Sun, Moon, Globe, ChevronDown, ChevronUp } from 'lucide-react'
import * as api from '@/lib/api'
import type { QueryLogEntry } from '@/lib/api'
import { motion } from 'framer-motion'
import type { ViewType } from '@/App'
import { useTheme } from '@/hooks/useTheme'
import { Progress, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger, Separator } from '@/components/ui'

interface DashboardPageProps {
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
}

interface AggregatedStats {
  total: number
  answeredTotal: number
  qualityPassed: number
  qualityFailed: number
  webSearchCount: number
  avgElapsed: number
  qualityRate: number
  webSearchRate: number
  errorCount: number
  avgRetrieval: number
  last24h: number
}

export default function DashboardPage({ onOpenSidebar, sidebarOpen, onNavigate }: DashboardPageProps) {
  const theme = useTheme()
  const [logs, setLogs] = useState<QueryLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(7)
  const [showAllLogs, setShowAllLogs] = useState(false)

  const hasError = (log: QueryLogEntry) => Boolean(log.error?.trim())
  const answeredLogs = logs.filter((log) => !hasError(log))
  const qualityPassed = answeredLogs.filter((log) => log.quality_ok).length
  const qualityFailed = answeredLogs.filter((log) => !log.quality_ok).length
  const webSearchCount = answeredLogs.filter((log) => log.used_web_search).length

  useEffect(() => {
    setLoading(true)
    api.queryLogs(days, 1000)
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [days])

  const stats: AggregatedStats = logs.length > 0 ? {
    total: logs.length,
    answeredTotal: answeredLogs.length,
    qualityPassed,
    qualityFailed,
    webSearchCount,
    avgElapsed: Math.round(logs.reduce((a, b) => a + b.elapsed_ms, 0) / logs.length),
    qualityRate: answeredLogs.length > 0 ? qualityPassed / answeredLogs.length : 0,
    webSearchRate: answeredLogs.length > 0 ? webSearchCount / answeredLogs.length : 0,
    errorCount: logs.filter((l) => hasError(l)).length,
    avgRetrieval: Math.round(logs.reduce((a, b) => a + (b.retrieval_count || 0), 0) / logs.length),
    last24h: logs.filter((l) => Date.now() - new Date(l.timestamp).getTime() < 86400000).length,
  } : {
    total: 0,
    answeredTotal: 0,
    qualityPassed: 0,
    qualityFailed: 0,
    webSearchCount: 0,
    avgElapsed: 0,
    qualityRate: 0,
    webSearchRate: 0,
    errorCount: 0,
    avgRetrieval: 0,
    last24h: 0,
  }

  // Time distribution (hourly buckets)
  const hourlyData = Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    count: logs.filter((l) => new Date(l.timestamp).getHours() === h).length,
    avgMs: (() => {
      const hLogs = logs.filter((l) => new Date(l.timestamp).getHours() === h)
      return hLogs.length ? Math.round(hLogs.reduce((a, b) => a + b.elapsed_ms, 0) / hLogs.length) : 0
    })(),
  }))

  const maxHourlyCount = Math.max(...hourlyData.map((h) => h.count), 1)

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border px-5 py-3 bg-background/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          {!sidebarOpen && (
            <Button variant="ghost" size="sm" onClick={onOpenSidebar}>
              <PanelRightOpen className="h-4 w-4" />
            </Button>
          )}
          <button onClick={() => onNavigate('chat')}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mr-1">
            <ArrowLeft className="h-3.5 w-3.5" />返回
          </button>
          <div className="h-4 w-px bg-border" />
          <BarChart3 className="h-4 w-4 text-primary" />
          <h1 className="font-heading text-lg text-foreground tracking-tight">指标面板</h1>
        </div>

        <div className="flex items-center gap-2">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button onClick={theme.toggle}
                  className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
                  {theme.theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
                </button>
              </TooltipTrigger>
              <TooltipContent>{theme.theme === 'dark' ? '切换浅色模式' : '切换深色模式'}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          {/* Time range selector */}
          <div className="flex gap-1 rounded-md border border-border p-0.5">
          {[1, 7, 30].map((d) => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-3 py-1 text-[10px] font-medium rounded-sm transition-colors ${
                days === d ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground'
              }`}>
              近{d}天
            </button>
          ))}
        </div>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-5xl px-5 py-6">
          {loading ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="rounded-lg border border-border bg-surface/30 p-4 animate-pulse">
                  <div className="h-3 bg-muted rounded w-1/2 mb-2" />
                  <div className="h-6 bg-muted rounded w-2/3" />
                </div>
              ))}
            </div>
          ) : logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <BarChart3 className="h-12 w-12 text-muted-foreground/20 mb-4" />
              <p className="text-sm text-muted-foreground">暂无查询数据</p>
              <p className="text-xs text-muted-foreground/50 mt-1">发送消息后，指标数据将在此处展示</p>
            </div>
          ) : (
            <>
              {/* Hero stats row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                <StatCard icon={TrendingUp} label="总查询" value={stats.total.toString()} sub={`近24h ${stats.last24h} 次`} delay={0} />
                <StatCard icon={Clock} label="平均耗时" value={`${stats.avgElapsed}ms`} sub={`检索 ${stats.avgRetrieval} 条`} delay={0.05} />
                <StatCard icon={CheckCircle2} label="质量通过率" value={`${(stats.qualityRate * 100).toFixed(0)}%`}
                  sub={`${stats.qualityPassed}/${stats.answeredTotal || 0}`} delay={0.1} color="emerald" />
                <StatCard icon={stats.webSearchRate > 0.3 ? AlertTriangle : HelpCircle} label="联网搜索率" value={`${(stats.webSearchRate * 100).toFixed(0)}%`}
                  sub={stats.errorCount > 0 ? `${stats.errorCount} 次错误` : `${stats.webSearchCount}/${stats.answeredTotal || 0}`} delay={0.15} color={stats.webSearchRate > 0.3 ? 'amber' : 'violet'} />
              </div>

              {/* Hourly distribution — editorial bar chart */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.4 }}
                className="rounded-lg border border-border bg-surface/30 p-5 mb-6"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-heading text-sm text-foreground tracking-tight">小时分布</h3>
                  <span className="text-[10px] text-muted-foreground/50 font-mono">avg {stats.avgElapsed}ms</span>
                </div>
                <div className="flex items-end gap-1 h-40 pt-5">
                  {hourlyData.map((h) => (
                    <TooltipProvider key={h.hour}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="flex-1 flex flex-col items-center gap-1">
                            <span className="text-[8px] text-muted-foreground/50 font-mono h-3">
                              {h.count > 0 ? h.count : ''}
                            </span>
                            <div
                              className="w-full rounded-t-sm bg-primary/60 hover:bg-primary/80 transition-colors cursor-pointer"
                              style={{ height: h.count > 0 ? `${Math.max((h.count / maxHourlyCount) * 104, 10)}px` : '0px' }}
                            />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>
                          {h.hour}:00 — {h.count} 次查询 · avg {h.avgMs}ms
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  ))}
                </div>
                <div className="flex justify-between mt-2 text-[8px] text-muted-foreground/40 font-mono">
                  {[0, 6, 12, 18, 23].map((h) => <span key={h}>{h}:00</span>)}
                </div>
              </motion.div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                {/* Quality breakdown */}
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.25, duration: 0.4 }}
                  className="rounded-lg border border-border bg-surface/30 p-5"
                >
                  <h3 className="font-heading text-sm text-foreground tracking-tight mb-4">质量分布</h3>
                  <div className="space-y-3">
                    {[
                      { label: '通过', key: 'quality_ok' as const, color: 'emerald' as const },
                      { label: '未通过', key: 'failed' as const, color: 'red' as const },
                      { label: '错误', key: 'error' as const, color: 'violet' as const },
                    ].map((item) => {
                      let count = 0
                      if (item.key === 'quality_ok') count = stats.qualityPassed
                      else if (item.key === 'failed') count = stats.qualityFailed
                      else count = stats.errorCount
                      const pct = (count / stats.total) * 100
                      return (
                        <div key={item.label}>
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="text-muted-foreground">{item.label}</span>
                            <span className="font-mono text-foreground/70">{count} / {pct.toFixed(0)}%</span>
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
                      <p className="text-[10px] text-muted-foreground/50 mt-1">单独统计联网补充，不再和质量等级混算。</p>
                    </div>
                  </div>
                </motion.div>

                {/* Recent queries */}
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3, duration: 0.4 }}
                  className="rounded-lg border border-border bg-surface/30 p-5"
                >
                  <h3 className="font-heading text-sm text-foreground tracking-tight mb-4">最近查询</h3>
                  <div className="space-y-2">
                    {logs.slice(0, 6).map((log, i) => (
                      <div key={i} className="flex items-center justify-between gap-2 text-xs">
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

              {/* Detailed logs table */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.35, duration: 0.4 }}
                className="rounded-lg border border-border bg-surface/30 p-5"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-heading text-sm text-foreground tracking-tight">
                    查询日志
                    <span className="text-[10px] text-muted-foreground/50 font-mono ml-2 font-normal">共 {logs.length} 条</span>
                  </h3>
                  {logs.length > 15 && (
                    <button onClick={() => setShowAllLogs(!showAllLogs)}
                      className="flex items-center gap-1 text-[10px] text-primary/60 hover:text-primary transition-colors">
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
                      </tr>
                    </thead>
                    <tbody>
                      {(showAllLogs ? logs : logs.slice(0, 15)).map((log, i) => (
                        <tr key={i} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                          <td className="py-2 pr-4 text-muted-foreground font-mono whitespace-nowrap">
                            {new Date(log.timestamp).toLocaleString('zh-CN', {
                              month: '2-digit', day: '2-digit',
                              hour: '2-digit', minute: '2-digit',
                            })}
                          </td>
                          <td className="py-2 pr-4 text-foreground/80 truncate max-w-[200px]">
                            {log.question}
                          </td>
                          <td className="py-2 pr-4 text-right text-muted-foreground font-mono">
                            {log.elapsed_ms}ms
                          </td>
                          <td className="py-2 pr-4 text-right text-muted-foreground font-mono">
                            {log.retrieval_count}
                          </td>
                          <td className="py-2 text-center">
                            <span className={`inline-flex items-center gap-1 text-[10px] ${
                              log.quality_ok ? 'text-emerald-400' : 'text-red-400'
                            }`}>
                              {log.quality_ok ? '✓ 通过' : '✗ 失败'}
                              {log.used_web_search && <Globe className="h-2.5 w-2.5 inline" />}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

/* ─── Stat Card ─── */

function StatCard({ icon: Icon, label, value, sub, delay = 0, color = 'primary' }: {
  icon: typeof TrendingUp
  label: string
  value: string
  sub: string
  delay?: number
  color?: 'primary' | 'emerald' | 'amber' | 'violet'
}) {
  const accentMap = {
    primary: 'from-primary/20 to-transparent',
    emerald: 'from-emerald-500/20 to-transparent',
    amber: 'from-amber-500/20 to-transparent',
    violet: 'from-violet-500/20 to-transparent',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="stat-glow rounded-lg border border-border bg-surface/30 p-4"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-muted-foreground font-medium tracking-wide uppercase">{label}</span>
        <Icon className="h-4 w-4 text-muted-foreground/40" />
      </div>
      <div className="font-heading text-2xl text-foreground tracking-tight">{value}</div>
      <p className="text-[10px] text-muted-foreground/50 mt-1">{sub}</p>
      <div className={`absolute inset-0 rounded-lg bg-gradient-to-br ${accentMap[color]} pointer-events-none`} />
    </motion.div>
  )
}
