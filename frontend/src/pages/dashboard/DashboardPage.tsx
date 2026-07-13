import { useState } from 'react'
import { Button, ScrollArea } from '@/components/ui'
import { ArrowLeft, BarChart3, CheckCircle2, Clock, DollarSign, PanelRightOpen, TrendingUp } from 'lucide-react'
import { motion } from 'framer-motion'
import type { ViewType } from '@/app/navigation'
import DashboardCharts from '@/components/dashboard/DashboardCharts'
import QueryLogTable from '@/components/dashboard/QueryLogTable'
import { useDashboardData } from '@/features/dashboard/hooks/useDashboardData'
import { buildDashboardMetrics } from '@/features/dashboard/model/dashboardMetrics'

interface DashboardPageProps {
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (view: ViewType) => void
}

export default function DashboardPage({ onOpenSidebar, sidebarOpen, onNavigate }: DashboardPageProps) {
  const [showAllLogs, setShowAllLogs] = useState(false)
  const { logs, loading, days, setDays, totalCostSummary } = useDashboardData()
  const metrics = buildDashboardMetrics(logs, { now: new Date(), totalCostSummary })

  return (
    <div className="flex flex-col h-full">
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
          <div className="flex gap-1 rounded-md border border-border p-0.5">
            {[1, 7, 30].map((day) => (
              <button key={day} onClick={() => setDays(day)}
                className={`px-3 py-1 text-2xs font-medium rounded-sm transition-colors ${
                  days === day ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground'
                }`}>
                近{day}天
              </button>
            ))}
          </div>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-5xl px-5 py-6">
          {loading ? (
            <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-8">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="rounded-lg border border-border bg-surface/30 p-4 animate-pulse">
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
              <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-8">
                <StatCard icon={BarChart3} label="首 token (avg)" value={metrics.avgFirstToken ? `${metrics.avgFirstToken}ms` : '-'} sub={metrics.avgTtfb ? `TTFB avg ${metrics.avgTtfb}ms` : '等待数据'} delay={0} />
                <StatCard icon={TrendingUp} label="总查询" value={metrics.stats.total.toString()} sub={`近24h ${metrics.stats.last24h} 次`} delay={0.05} />
                <StatCard icon={Clock} label="平均耗时" value={`${metrics.stats.avgElapsed}ms`} sub={`检索 ${metrics.stats.avgRetrieval} 条`} delay={0.1} />
                <StatCard icon={CheckCircle2} label="质量通过率" value={`${(metrics.stats.qualityRate * 100).toFixed(0)}%`}
                  sub={`${metrics.stats.qualityPassed}/${metrics.stats.answeredTotal || 0}`} delay={0.1} color="emerald" />
                <StatCard icon={BarChart3} label="总 Token 消耗" value={metrics.totalTokens.toLocaleString()}
                  sub={`输入 ${metrics.totalPromptTokens.toLocaleString()} / 输出 ${metrics.totalCompletionTokens.toLocaleString()}`} delay={0.12} color="violet" />
                <StatCard icon={DollarSign} label="Token 估算" value={metrics.totalTokenCost}
                  sub={`${metrics.usesBackendTotalCost ? '合计' : '估算'} ${metrics.totalTokenCost}`} delay={0.15} color="amber" />
              </div>

              <DashboardCharts logs={logs} metrics={metrics} />
              <QueryLogTable logs={logs} showAllLogs={showAllLogs} onShowAllLogsChange={setShowAllLogs} />
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

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
        <span className="text-2xs text-muted-foreground font-medium tracking-wide uppercase">{label}</span>
        <Icon className="h-4 w-4 text-muted-foreground/40" />
      </div>
      <div className="font-heading text-2xl text-foreground tracking-tight">{value}</div>
      <p className="text-2xs text-muted-foreground/50 mt-1">{sub}</p>
      <div className={`absolute inset-0 rounded-lg bg-gradient-to-br ${accentMap[color]} pointer-events-none`} />
    </motion.div>
  )
}
