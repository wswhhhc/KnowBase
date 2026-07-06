import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui'
import * as api from '@/shared/api'
import type { AppRole } from '@/shared/auth/permissions'
import type { User, Workspace, WorkspaceMemberRole } from '@/shared/api'

type WorkspaceMemberDraft = {
  user_id: string
  role: WorkspaceMemberRole
}

const ROLE_LABELS: Record<AppRole, string> = {
  admin: '管理员',
  editor: '编辑者',
  viewer: '浏览者',
}

const WORKSPACE_ROLES: WorkspaceMemberRole[] = ['editor', 'viewer']

export default function WorkspaceMembersPanel() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [workspaceId, setWorkspaceId] = useState('')
  const [members, setMembers] = useState<WorkspaceMemberDraft[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [addUserId, setAddUserId] = useState('')

  const memberUserIds = useMemo(() => new Set(members.map((member) => member.user_id)), [members])
  const availableUsers = useMemo(
    () => users.filter((user) => user.is_active && !memberUserIds.has(user.id)),
    [memberUserIds, users],
  )
  const workspaceOptions = workspaces.filter((workspace) => workspace.id)

  useEffect(() => {
    const loadBaseData = async () => {
      setLoading(true)
      try {
        const [workspaceList, userList] = await Promise.all([
          api.getWorkspaces(),
          api.listAdminUsers(),
        ])
        const explicitWorkspaces = workspaceList.filter((workspace) => workspace.id)
        setWorkspaces(workspaceList)
        setUsers(userList)
        setWorkspaceId((current) => current || explicitWorkspaces[0]?.id || '')
      } catch (error) {
        toast.error('工作区授权数据加载失败', { description: String(error) })
      } finally {
        setLoading(false)
      }
    }
    void loadBaseData()
  }, [])

  useEffect(() => {
    if (!workspaceId) {
      setMembers([])
      return
    }
    const loadMembers = async () => {
      setLoading(true)
      try {
        const loaded = await api.getWorkspaceMembers(undefined, workspaceId)
        setMembers(loaded.map((member) => ({
          user_id: member.user_id,
          role: member.role === 'editor' ? 'editor' : 'viewer',
        })))
      } catch (error) {
        toast.error('工作区成员加载失败', { description: String(error) })
      } finally {
        setLoading(false)
      }
    }
    void loadMembers()
  }, [workspaceId])

  useEffect(() => {
    setAddUserId((current) => {
      if (current && availableUsers.some((user) => user.id === current)) return current
      return availableUsers[0]?.id || ''
    })
  }, [availableUsers])

  const userNameById = useMemo(
    () => new Map(users.map((user) => [user.id, user.username])),
    [users],
  )

  const addMember = () => {
    if (!addUserId || memberUserIds.has(addUserId)) return
    setMembers((current) => [...current, { user_id: addUserId, role: 'viewer' }])
  }

  const saveMembers = async () => {
    if (!workspaceId) return
    setSaving(true)
    try {
      const saved = await api.replaceWorkspaceMembers(undefined, workspaceId, { members })
      setMembers(saved.map((member) => ({
        user_id: member.user_id,
        role: member.role === 'editor' ? 'editor' : 'viewer',
      })))
      toast.success('工作区授权已保存')
    } catch (error) {
      toast.error('保存工作区授权失败', { description: String(error) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="rounded-lg border border-border/60 bg-surface/20 p-3">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">工作区授权</h2>
          <p className="mt-1 text-2xs text-muted-foreground/60">为具体工作区配置 editor / viewer 成员。</p>
        </div>
        <Button size="sm" onClick={saveMembers} disabled={saving || !workspaceId}>
          {saving ? '保存中' : '保存授权'}
        </Button>
      </div>

      {workspaceOptions.length === 0 ? (
        <p className="rounded-md border border-dashed border-border/60 px-3 py-4 text-center text-xs text-muted-foreground">
          还没有可授权的自定义工作区。
        </p>
      ) : (
        <div className="space-y-3">
          <select
            aria-label="选择授权工作区"
            value={workspaceId}
            onChange={(event) => setWorkspaceId(event.target.value)}
            className="h-9 w-full rounded-md border border-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50"
          >
            {workspaceOptions.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
            ))}
          </select>

          <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <select
              aria-label="添加工作区成员"
              value={addUserId}
              onChange={(event) => setAddUserId(event.target.value)}
              disabled={availableUsers.length === 0}
              className="h-9 rounded-md border border-border bg-background px-2 text-xs text-foreground outline-none disabled:opacity-60"
            >
              {availableUsers.length === 0 ? (
                <option value="">没有可添加用户</option>
              ) : availableUsers.map((user) => (
                <option key={user.id} value={user.id}>{user.username}</option>
              ))}
            </select>
            <Button size="sm" variant="outline" onClick={addMember} disabled={!addUserId || loading}>
              添加成员
            </Button>
          </div>

          <div className="overflow-hidden rounded-md border border-border/60">
            <div className="grid grid-cols-[1fr_7rem_4rem] gap-2 border-b border-border/60 bg-muted/30 px-3 py-2 text-2xs font-medium text-muted-foreground">
              <span>成员</span>
              <span>角色</span>
              <span className="text-right">操作</span>
            </div>
            {loading ? (
              <p className="px-3 py-4 text-center text-xs text-muted-foreground">正在加载授权...</p>
            ) : members.length === 0 ? (
              <p className="px-3 py-4 text-center text-xs text-muted-foreground">当前工作区暂无授权成员</p>
            ) : members.map((member) => (
              <div key={member.user_id} className="grid grid-cols-[1fr_7rem_4rem] items-center gap-2 border-b border-border/40 px-3 py-2 last:border-b-0">
                <span className="truncate text-xs font-medium text-foreground/85">
                  {userNameById.get(member.user_id) || member.user_id}
                </span>
                <select
                  aria-label={`${userNameById.get(member.user_id) || member.user_id} 工作区角色`}
                  value={member.role}
                  onChange={(event) => {
                    const nextRole = event.target.value as WorkspaceMemberRole
                    setMembers((current) => current.map((item) => item.user_id === member.user_id ? { ...item, role: nextRole } : item))
                  }}
                  className="h-8 rounded-md border border-border bg-background px-2 text-xs text-foreground outline-none"
                >
                  {WORKSPACE_ROLES.map((role) => (
                    <option key={role} value={role}>{ROLE_LABELS[role]}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => setMembers((current) => current.filter((item) => item.user_id !== member.user_id))}
                  className="text-right text-2xs text-destructive/70 transition-colors hover:text-destructive"
                >
                  移除
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
