import { req, withQuery } from '@/shared/api/client'
import type { AdminUserCreate, AdminUserUpdate, AuditLog, User } from '@/shared/api/types'

const authHeader = (accessToken?: string) => accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined

export const listAdminUsers = (accessToken?: string) =>
  req<User[]>('/admin/users', {
    headers: authHeader(accessToken),
  })

export const listAdminAuditLogs = (
  accessToken?: string,
  options: { actorUserId?: string; limit?: number } = {},
) => {
  const params = new URLSearchParams()
  if (options.actorUserId) params.set('actor_user_id', options.actorUserId)
  if (options.limit !== undefined) params.set('limit', String(options.limit))
  return req<AuditLog[]>(withQuery('/admin/audit-logs', params), {
    headers: authHeader(accessToken),
  })
}

export const createAdminUser = (accessToken: string | undefined, body: AdminUserCreate) =>
  req<User>('/admin/users', {
    method: 'POST',
    headers: authHeader(accessToken),
    body: JSON.stringify(body),
  })

export const updateAdminUser = (accessToken: string | undefined, userId: string, body: AdminUserUpdate) =>
  req<User>(`/admin/users/${userId}`, {
    method: 'PATCH',
    headers: authHeader(accessToken),
    body: JSON.stringify(body),
  })

export const deleteAdminUser = (accessToken: string | undefined, userId: string) =>
  req(`/admin/users/${userId}`, {
    method: 'DELETE',
    headers: authHeader(accessToken),
  })
