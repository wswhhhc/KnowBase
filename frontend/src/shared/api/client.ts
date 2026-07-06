import { getStoredAccessToken } from '@/shared/api/session'

export class ApiError extends Error {
  status: number
  retryAfter?: number

  constructor(status: number, message: string, retryAfter?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.retryAfter = retryAfter
  }
}

const BASE = '/api'

export function authHeaders(): Record<string, string> {
  const accessToken = getStoredAccessToken()
  if (accessToken) return { Authorization: `Bearer ${accessToken}` }
  const key = localStorage.getItem('knowbase_api_key')
  return key ? { Authorization: `Bearer ${key}` } : {}
}

export function withQuery(path: string, params: URLSearchParams): string {
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

export function withWorkspaceScope(path: string, workspaceId?: string, params?: URLSearchParams): string {
  const scopedParams = params ? new URLSearchParams(params) : new URLSearchParams()
  if (workspaceId !== undefined) {
    scopedParams.set('workspace_id', workspaceId)
  }
  return withQuery(path, scopedParams)
}

export async function createApiErrorFromResponse(res: Response): Promise<ApiError> {
  const retryAfter = Number(res.headers.get('Retry-After') || '') || undefined
  const text = await res.text()
  let message = text.trim()

  if (message) {
    try {
      const parsed = JSON.parse(message)
      if (typeof parsed === 'string') {
        message = parsed
      } else if (typeof parsed?.detail === 'string') {
        message = parsed.detail
      } else if (typeof parsed?.message === 'string') {
        message = parsed.message
      }
    } catch {
      // Keep plain-text responses unchanged.
    }
  }

  if (!message) {
    message = res.status === 429 && retryAfter
      ? `请求过于频繁，请在 ${retryAfter} 秒后重试。`
      : `HTTP ${res.status}`
  }

  return new ApiError(res.status, message, retryAfter)
}

export function isPermissionError(value: unknown): boolean {
  if (value instanceof ApiError) return value.status === 401 || value.status === 403
  const message = String(value).toLowerCase()
  return (
    message.includes('401') ||
    message.includes('403') ||
    message.includes('forbidden') ||
    message.includes('unauthorized') ||
    message.includes('无权') ||
    message.includes('权限')
  )
}

export async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    throw await createApiErrorFromResponse(res)
  }
  return res.json()
}

export function apiUrl(path: string): string {
  return `${BASE}${path}`
}
