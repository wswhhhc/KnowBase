import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Button, ConfirmDialog, Input } from '@/components/ui'
import * as api from '@/shared/api'
import type { AppRole } from '@/shared/auth/permissions'
import type { User } from '@/shared/api'

const ROLE_LABELS: Record<AppRole, string> = {
  admin: '管理员',
  editor: '编辑者',
  viewer: '浏览者',
}

const ROLES: AppRole[] = ['admin', 'editor', 'viewer']

interface CreateUserForm {
  username: string
  password: string
  role: AppRole
}

const initialForm: CreateUserForm = {
  username: '',
  password: '',
  role: 'viewer',
}

export default function AdminUsersPanel() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [savingUserId, setSavingUserId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null)
  const [form, setForm] = useState<CreateUserForm>(initialForm)

  const loadUsers = async () => {
    setLoading(true)
    try {
      setUsers(await api.listAdminUsers())
    } catch (error) {
      toast.error('用户列表加载失败', { description: String(error) })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadUsers()
  }, [])

  const createUser = async () => {
    const username = form.username.trim()
    if (!username || !form.password) return
    setCreating(true)
    try {
      const user = await api.createAdminUser(undefined, {
        username,
        password: form.password,
        role: form.role,
        is_active: true,
      })
      setUsers((current) => [...current, user].sort((a, b) => a.username.localeCompare(b.username)))
      setForm(initialForm)
      toast.success('用户已创建', { description: username })
    } catch (error) {
      toast.error('创建用户失败', { description: String(error) })
    } finally {
      setCreating(false)
    }
  }

  const updateUser = async (user: User, patch: { role?: AppRole; is_active?: boolean }) => {
    setSavingUserId(user.id)
    try {
      const updated = await api.updateAdminUser(undefined, user.id, patch)
      setUsers((current) => current.map((item) => item.id === user.id ? updated : item))
      toast.success('用户已更新', { description: user.username })
    } catch (error) {
      toast.error('更新用户失败', { description: String(error) })
    } finally {
      setSavingUserId((current) => current === user.id ? null : current)
    }
  }

  const deleteUser = async () => {
    if (!deleteTarget) return
    const user = deleteTarget
    setSavingUserId(user.id)
    try {
      await api.deleteAdminUser(undefined, user.id)
      setUsers((current) => current.filter((item) => item.id !== user.id))
      toast.success('用户已删除', { description: user.username })
    } catch (error) {
      toast.error('删除用户失败', { description: String(error) })
    } finally {
      setSavingUserId(null)
      setDeleteTarget(null)
    }
  }

  return (
    <section className="rounded-lg border border-border/60 bg-surface/20 p-3">
      <div className="mb-3">
        <h2 className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">用户管理</h2>
        <p className="mt-1 text-2xs text-muted-foreground/60">管理团队版账号、全局角色和启用状态。</p>
      </div>

      <div className="grid gap-2 sm:grid-cols-[1fr_1fr_8rem_auto]">
        <Input
          aria-label="新用户用户名"
          placeholder="用户名"
          value={form.username}
          onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
        />
        <Input
          aria-label="新用户密码"
          type="password"
          placeholder="初始密码"
          value={form.password}
          onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
        />
        <select
          aria-label="新用户角色"
          value={form.role}
          onChange={(event) => setForm((current) => ({ ...current, role: event.target.value as AppRole }))}
          className="h-9 rounded-md border border-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50"
        >
          {ROLES.map((role) => (
            <option key={role} value={role}>{ROLE_LABELS[role]}</option>
          ))}
        </select>
        <Button size="sm" onClick={createUser} disabled={creating || !form.username.trim() || !form.password}>
          {creating ? '创建中' : '创建用户'}
        </Button>
      </div>

      <div className="mt-3 overflow-hidden rounded-md border border-border/60">
        <div className="grid grid-cols-[1fr_7rem_6rem_4rem] gap-2 border-b border-border/60 bg-muted/30 px-3 py-2 text-2xs font-medium text-muted-foreground">
          <span>用户名</span>
          <span>角色</span>
          <span>状态</span>
          <span className="text-right">操作</span>
        </div>
        {loading ? (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">正在加载用户...</p>
        ) : users.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">暂无用户</p>
        ) : users.map((user) => {
          const disabled = savingUserId === user.id
          return (
            <div key={user.id} className="grid grid-cols-[1fr_7rem_6rem_4rem] items-center gap-2 border-b border-border/40 px-3 py-2 last:border-b-0">
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-foreground/85">{user.username}</p>
                <p className="truncate text-2xs text-muted-foreground/50">{user.id}</p>
              </div>
              <select
                aria-label={`${user.username} 角色`}
                value={user.role}
                disabled={disabled}
                onChange={(event) => void updateUser(user, { role: event.target.value as AppRole })}
                className="h-8 rounded-md border border-border bg-background px-2 text-xs text-foreground outline-none disabled:opacity-60"
              >
                {ROLES.map((role) => (
                  <option key={role} value={role}>{ROLE_LABELS[role]}</option>
                ))}
              </select>
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={user.is_active}
                  disabled={disabled}
                  onChange={(event) => void updateUser(user, { is_active: event.target.checked })}
                  aria-label={`${user.username} 启用状态`}
                  className="rounded border-border text-primary focus:ring-primary/30"
                />
                启用
              </label>
              <button
                type="button"
                disabled={disabled}
                onClick={() => setDeleteTarget(user)}
                className="text-right text-2xs text-destructive/70 transition-colors hover:text-destructive disabled:opacity-50"
              >
                删除
              </button>
            </div>
          )
        })}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
        title="删除用户"
        description={`确定要删除用户“${deleteTarget?.username ?? ''}”吗？此操作不可撤销。`}
        onConfirm={deleteUser}
      />
    </section>
  )
}
