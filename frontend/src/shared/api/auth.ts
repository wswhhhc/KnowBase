import { req } from '@/shared/api/client'
import type { AuthSession, LoginRequest, RegisterRequest, User } from '@/shared/api/types'

export const login = (body: LoginRequest) =>
  req<AuthSession>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(body),
  })

export const register = (body: RegisterRequest) =>
  req<AuthSession>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(body),
  })

export const refreshSession = (refreshToken: string) =>
  req<AuthSession>('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
  })

export const logout = (refreshToken: string) =>
  req('/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
  })

export const getCurrentUser = (accessToken: string) =>
  req<User>('/auth/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
