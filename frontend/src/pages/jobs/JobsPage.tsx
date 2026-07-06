import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, CheckCircle2, CircleDashed, Clock3, Loader2, PanelRightOpen, RefreshCw, XCircle } from 'lucide-react'

import type { ViewType } from '@/app/navigation'
import { Button, ScrollArea } from '@/components/ui'
import * as api from '@/shared/api'
import type { Job } from '@/shared/api'

interface JobsPageProps {
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
}

const STATUS_COPY: Record<string, { label: string; className: string; icon: typeof CircleDashed }> = {
  queued: { label: '排队中', className: 'text-sky-500 bg-sky-500/10 border-sky-500/20', icon: Clock3 },
  running: { label: '运行中', className: 'text-amber-500 bg-amber-500/10 border-amber-500/20', icon: Loader2 },
  succeeded: { label: '已完成', className: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20', icon: CheckCircle2 },
  failed: { label: '失败', className: 'text-red-500 bg-red-500/10 border-red-500/20', icon: XCircle },
  canceled: { label: '已取消', className: 'text-muted-foreground bg-muted/40 border-border', icon: CircleDashed },
}
const ACTIVE_JOBS_REFRESH_MS = 3000

export default function JobsPage({ onOpenSidebar, sidebarOpen, onNavigate }: JobsPageProps) {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cancelingJobId, setCancelingJobId] = useState<string | null>(null)
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null)
  const [jobErrors, setJobErrors] = useState<Record<string, string>>({})

  const activeCount = useMemo(
    () => jobs.filter((job) => !api.isTerminalJob(job)).length,
    [jobs],
  )

  const loadJobs = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    setError('')
    try {
      setJobs(await api.listJobs())
    } catch (err) {
      setError(err instanceof Error ? err.message : '任务列表加载失败')
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadJobs()
  }, [loadJobs])

  useEffect(() => {
    if (activeCount === 0 || loading || error) return
    const timer = window.setTimeout(() => {
      void loadJobs(false)
    }, ACTIVE_JOBS_REFRESH_MS)
    return () => window.clearTimeout(timer)
  }, [activeCount, error, loadJobs, loading])

  const handleCancelJob = async (jobId: string) => {
    setCancelingJobId(jobId)
    setJobErrors((current) => ({ ...current, [jobId]: '' }))
    try {
      const canceled = await api.cancelJob(jobId)
      setJobs((current) => current.map((job) => job.id === jobId ? canceled : job))
    } catch (err) {
      setJobErrors((current) => ({
        ...current,
        [jobId]: err instanceof Error ? err.message : '取消任务失败',
      }))
    } finally {
      setCancelingJobId(null)
    }
  }

  const handleRetryJob = async (jobId: string) => {
    setRetryingJobId(jobId)
    setJobErrors((current) => ({ ...current, [jobId]: '' }))
    try {
      const retried = await api.retryJob(jobId)
      setJobs((current) => current.map((job) => job.id === jobId ? retried : job))
    } catch (err) {
      setJobErrors((current) => ({
        ...current,
        [jobId]: err instanceof Error ? err.message : '重试任务失败',
      }))
    } finally {
      setRetryingJobId(null)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-border bg-background/80 px-5 py-3 backdrop-blur-sm">
        <div className="flex min-w-0 items-center gap-3">
          {!sidebarOpen && (
            <Button variant="ghost" size="sm" onClick={onOpenSidebar}>
              <PanelRightOpen className="h-4 w-4" />
            </Button>
          )}
          <button
            onClick={() => onNavigate('chat')}
            className="mr-1 flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />返回
          </button>
          <div className="h-4 w-px bg-border" />
          <CircleDashed className="h-4 w-4 text-primary" />
          <div className="min-w-0">
            <h1 className="font-heading text-lg tracking-tight text-foreground">任务中心</h1>
            <p className="text-2xs text-muted-foreground/60">
              {activeCount > 0 ? `${activeCount} 个任务仍在处理中` : '当前没有运行中的任务'}
            </p>
          </div>
        </div>
        <Button size="sm" variant="outline" onClick={() => void loadJobs()} disabled={loading} className="gap-1.5">
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </Button>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-5xl px-5 py-6">
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="h-24 animate-pulse rounded-lg border border-border bg-surface/30" />
              ))}
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <XCircle className="mb-4 h-12 w-12 text-destructive/40" />
              <p className="text-sm font-medium text-foreground/85">任务列表加载失败</p>
              <p className="mt-1 max-w-sm text-xs text-muted-foreground/60">{error}</p>
              <Button className="mt-4" size="sm" variant="outline" onClick={() => void loadJobs()}>重试</Button>
            </div>
          ) : jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <CircleDashed className="mb-4 h-12 w-12 text-muted-foreground/20" />
              <p className="text-sm font-medium text-foreground/85">暂无后台任务</p>
              <p className="mt-1 text-xs text-muted-foreground/60">导入文档或网页后，任务进度会显示在这里。</p>
            </div>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => (
                <JobRow
                  key={job.id}
                  job={job}
                  canceling={cancelingJobId === job.id}
                  retrying={retryingJobId === job.id}
                  cancelError={jobErrors[job.id] || ''}
                  onCancel={() => void handleCancelJob(job.id)}
                  onRetry={() => void handleRetryJob(job.id)}
                />
              ))}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

function JobRow({
  job,
  canceling,
  retrying,
  cancelError,
  onCancel,
  onRetry,
}: {
  job: Job
  canceling: boolean
  retrying: boolean
  cancelError: string
  onCancel: () => void
  onRetry: () => void
}) {
  const status = STATUS_COPY[job.status] ?? { label: job.status, className: 'text-muted-foreground bg-muted/40 border-border', icon: CircleDashed }
  const StatusIcon = status.icon
  const percent = clampPercent(job.progress?.percent)
  const phase = job.progress?.message || job.progress?.phase || '等待 worker 更新进度'
  const canCancel = job.status === 'queued' || job.status === 'running'
  const canRetry = job.status === 'failed'

  return (
    <article className="rounded-lg border border-border bg-surface/30 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1 flex items-center gap-2">
            <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-2xs font-medium ${status.className}`}>
              <StatusIcon className={`h-3 w-3 ${job.status === 'running' ? 'animate-spin' : ''}`} />
              {status.label}
            </span>
            <span className="truncate font-mono text-2xs text-muted-foreground/60">{job.id}</span>
          </div>
          <h2 className="text-sm font-medium text-foreground/90">{formatJobType(job.job_type)}</h2>
          <p className="mt-1 text-xs text-muted-foreground/65">{phase}</p>
        </div>
        <div className="text-right font-mono text-2xs text-muted-foreground/50">
          <p>{formatDate(job.created_at)}</p>
          <p className="mt-1">{job.workspace_id || '默认工作区'}</p>
          {canCancel && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onCancel}
              disabled={canceling}
              aria-label={`取消任务 ${job.id}`}
              className="mt-3 h-7 px-2 text-2xs font-sans"
            >
              {canceling ? '取消中' : '取消任务'}
            </Button>
          )}
          {canRetry && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onRetry}
              disabled={retrying}
              aria-label={`重试任务 ${job.id}`}
              className="mt-3 h-7 px-2 text-2xs font-sans"
            >
              {retrying ? '重试中' : '重试任务'}
            </Button>
          )}
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1 flex items-center justify-between text-2xs text-muted-foreground/60">
          <span>进度</span>
          <span className="font-mono">{percent}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${percent}%` }} />
        </div>
      </div>

      {job.error && (
        <p className="mt-3 rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {job.error}
        </p>
      )}
      {cancelError && (
        <p className="mt-3 rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {cancelError}
        </p>
      )}
    </article>
  )
}

function clampPercent(value: unknown): number {
  if (typeof value !== 'number' || Number.isNaN(value)) return 0
  return Math.max(0, Math.min(100, Math.round(value)))
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatJobType(value: string): string {
  const copy: Record<string, string> = {
    ingest_file: '文件导入',
    ingest_url: 'URL 导入',
    clear_workspace: '清空工作区',
    rebuild_index: '重建索引',
  }
  return copy[value] ?? value
}
