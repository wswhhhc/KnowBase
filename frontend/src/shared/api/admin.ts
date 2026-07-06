import { req } from '@/shared/api/client'
import type { AdminUserCreate, AdminUserUpdate, User } from '@/shared/api/types'

const authHeader = (accessToken: string) => ({ Authorization: `Bearer ${accessToken}` })

export const listAdminUsers = (accessToken: string) =>
  req<User[]>('/admin/users', {
    headers: authHeader(accessToken),
  })

export const createAdminUser = (accessToken: string, body: AdminUserCreate) =>
  req<User>('/admin/users', {
    method: 'POST',
    headers: authHeader(accessToken),
    body: JSON.stringify(body),
  })

export const updateAdminUser = (accessToken: string, userId: string, body: AdminUserUpdate) =>
  req<User>(`/admin/users/${userId}`, {
    method: 'PATCH',
    headers: authHeader(accessToken),
    body: JSON.stringify(body),
  })

export const deleteAdminUser = (accessToken: string, userId: string) =>
  req(`/admin/users/${userId}`, {
    method: 'DELETE',
    headers: authHeader(accessToken),
  })
