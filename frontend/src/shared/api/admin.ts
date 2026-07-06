import { req } from '@/shared/api/client'
import type { AdminUserCreate, AdminUserUpdate, User } from '@/shared/api/types'

const authHeader = (accessToken?: string) => accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined

export const listAdminUsers = (accessToken?: string) =>
  req<User[]>('/admin/users', {
    headers: authHeader(accessToken),
  })

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
