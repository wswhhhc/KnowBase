import { req } from '@/shared/api/client'
import type { Workspace } from '@/shared/api/types'

export const getWorkspaces = () => req<Workspace[]>('/workspaces')

export const createWorkspace = (name = '新工作区', description = '') =>
  req<Workspace>('/workspaces', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  })

export const renameWorkspace = (id: string, name: string) =>
  req<Workspace>(`/workspaces/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })

export const deleteWorkspace = (id: string) =>
  req(`/workspaces/${id}`, { method: 'DELETE' })
