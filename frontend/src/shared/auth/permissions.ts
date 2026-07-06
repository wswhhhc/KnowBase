import type { User } from '@/shared/api/types'

export type AppRole = 'admin' | 'editor' | 'viewer'

export interface RoleCapabilities {
  canManageApp: boolean
  canManageKnowledgeBase: boolean
  canManageWorkspaces: boolean
}

export function normalizeRole(role?: string | null): AppRole {
  if (role === 'admin' || role === 'editor' || role === 'viewer') return role
  return 'viewer'
}

export function getRoleCapabilities(role: AppRole): RoleCapabilities {
  return {
    canManageApp: role === 'admin',
    canManageKnowledgeBase: role === 'admin' || role === 'editor',
    canManageWorkspaces: role === 'admin',
  }
}

export function getUserRole(user: User | null, hasLegacyApiKey = false): AppRole {
  if (user) return normalizeRole(user.role)
  return hasLegacyApiKey ? 'admin' : 'viewer'
}
