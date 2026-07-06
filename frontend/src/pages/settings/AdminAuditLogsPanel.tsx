import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui'
import * as api from '@/shared/api'
import type { AuditLog, User } from '@/shared/api'

const LOG_LIMIT = 50

const ACTION_LABELS: Record<string, string> = {
  'auth.login_succeeded': '登录成功',
  'auth.login_failed': '登录失败',
  'job.queued': '任务入队',
  'job.failed': '任务失败',
  'job.succeeded': '任务完成',
  'url_import.rejected': 'URL 导入被拒绝',
}

export default function AdminAuditLogsPanel() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [actorUserId, setActorUserId] = useState('')
  const [loading, setLoading] = useState(true)

  const userNameById = useMemo(
    () => new Map(users.map((user) => [user.id, user.username])),
    [users],
  )

  const loadLogs = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    try {
      setLogs(await api.listAdminAuditLogs(undefined, {
        actorUserId: actorUserId || undefined,
        limit: LOG_LIMIT,
      }))
    } catch (error) {
      toast.error('审计日志加载失败', { description: String(error) })
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [actorUserId])

  useEffect(() => {
    api.listAdminUsers()
      .then(setUsers)
      .catch(() => setUsers([]))
  }, [])

  useEffect(() => {
    void loadLogs()
  }, [loadLogs])

  return (
    <section className="rounded-lg border border-border/60 bg-surface/20 p-3">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">审计日志</h2>
          <p className="mt-1 text-2xs text-muted-foreground/60">查看最近的登录、导入和后台任务安全事件。</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            aria-label="审计日志用户过滤"
            value={actorUserId}
            onChange={(event) => setActorUserId(event.target.value)}
            className="h-8 rounded-md border border-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50"
          >
            <option value="">全部用户</option>
            {users.map((user) => (
              <option key={user.id} value={user.id}>{user.username}</option>
            ))}
          </select>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void loadLogs()}
            disabled={loading}
            className="h-8 gap-1.5 px-2 text-2xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>
      </div>

      <div className="overflow-hidden rounded-md border border-border/60">
        <div className="grid grid-cols-[7rem_1fr_8rem] gap-2 border-b border-border/60 bg-muted/30 px-3 py-2 text-2xs font-medium text-muted-foreground">
          <span>时间</span>
          <span>事件</span>
          <span>操作者</span>
        </div>
        {loading ? (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">正在加载审计日志...</p>
        ) : logs.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">暂无审计日志</p>
        ) : logs.map((log) => (
          <article key={log.id} className="grid grid-cols-[7rem_1fr_8rem] gap-2 border-b border-border/40 px-3 py-2 last:border-b-0">
            <time className="font-mono text-2xs text-muted-foreground/60" dateTime={log.created_at}>
              {formatDate(log.created_at)}
            </time>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <p className="text-xs font-medium text-foreground/85">{ACTION_LABELS[log.action] ?? log.action}</p>
                <span className="rounded border border-border bg-muted/30 px-1.5 py-0.5 font-mono text-2xs text-muted-foreground/60">
                  {log.action}
                </span>
              </div>
              <p className="mt-1 truncate font-mono text-2xs text-muted-foreground/50">
                {formatTarget(log)}
              </p>
              {hasMetadata(log.metadata) && (
                <p className="mt-1 break-all font-mono text-2xs text-muted-foreground/60">
                  {JSON.stringify(log.metadata)}
                </p>
              )}
            </div>
            <div className="min-w-0 text-right">
              <p className="truncate text-xs text-foreground/80">{formatActor(log, userNameById)}</p>
              {log.actor_user_id && (
                <p className="truncate font-mono text-2xs text-muted-foreground/45">{log.actor_user_id}</p>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatTarget(log: AuditLog): string {
  const target = [log.target_type, log.target_id].filter(Boolean).join(':')
  return target || '无目标对象'
}

function formatActor(log: AuditLog, userNameById: Map<string, string>): string {
  if (!log.actor_user_id) return '系统'
  return userNameById.get(log.actor_user_id) ?? log.actor_user_id
}

function hasMetadata(metadata: AuditLog['metadata']): boolean {
  return !!metadata && Object.keys(metadata).length > 0
}
