import { req } from '@/shared/api/client'
import type { Workspace, WorkspaceMember, WorkspaceMembersUpdate } from '@/shared/api/types'

const authHeader = (accessToken: string) => ({ Authorization: `Bearer ${accessToken}` })

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

export const getWorkspaceMembers = (accessToken: string, workspaceId: string) =>
  req<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`, {
    headers: authHeader(accessToken),
  })

export const replaceWorkspaceMembers = (
  accessToken: string,
  workspaceId: string,
  body: WorkspaceMembersUpdate,
) =>
  req<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`, {
    method: 'PUT',
    headers: authHeader(accessToken),
    body: JSON.stringify(body),
  })
