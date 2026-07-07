import { FormEvent, useState } from 'react'
import { LockKeyhole, LogIn, UserPlus } from 'lucide-react'

import { login, register } from '@/shared/api/auth'
import { ApiError } from '@/shared/api/client'
import { saveAuthSession } from '@/shared/api/session'
import type { AuthSession } from '@/shared/api/types'

interface LoginPageProps {
  onAuthenticated: (session: AuthSession) => void
}

export default function LoginPage({ onAuthenticated }: LoginPageProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (isSubmitting) return
    setError('')
    if (mode === 'register' && password !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }
    setIsSubmitting(true)
    try {
      const credentials = { username: username.trim(), password }
      const session = mode === 'login' ? await login(credentials) : await register(credentials)
      saveAuthSession(session)
      onAuthenticated(session)
    } catch (err) {
      const fallback = mode === 'login' ? '登录失败，请稍后重试' : '注册失败，请稍后重试'
      setError(err instanceof ApiError ? err.message : fallback)
    } finally {
      setIsSubmitting(false)
    }
  }

  const switchMode = (nextMode: 'login' | 'register') => {
    setMode(nextMode)
    setError('')
    setPassword('')
    setConfirmPassword('')
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10 text-foreground noise-overlay">
      <main className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface text-primary">
            <LockKeyhole className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-normal">KnowBase</h1>
            <p className="mt-1 text-sm text-muted-foreground">团队知识库工作台</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5 rounded-lg border border-border bg-surface p-6 shadow-sm">
          <div className="grid grid-cols-2 gap-2 rounded-md border border-border bg-background p-1" aria-label="认证模式">
            <button
              type="button"
              aria-label="切换到登录模式"
              onClick={() => switchMode('login')}
              className={`h-9 rounded px-3 text-sm font-medium transition-colors ${
                mode === 'login'
                  ? 'bg-surface text-surface-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              登录
            </button>
            <button
              type="button"
              aria-label="切换到注册模式"
              onClick={() => switchMode('register')}
              className={`h-9 rounded px-3 text-sm font-medium transition-colors ${
                mode === 'register'
                  ? 'bg-surface text-surface-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              创建账号
            </button>
          </div>

          <div className="space-y-2">
            <label htmlFor="login-username" className="text-sm font-medium text-surface-foreground">
              用户名
            </label>
            <input
              id="login-username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"
              required
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="login-password" className="text-sm font-medium text-surface-foreground">
              密码
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"
              minLength={mode === 'register' ? 8 : undefined}
              required
            />
          </div>

          {mode === 'register' && (
            <div className="space-y-2">
              <label htmlFor="register-confirm-password" className="text-sm font-medium text-surface-foreground">
                确认密码
              </label>
              <input
                id="register-confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"
                minLength={8}
                required
              />
            </div>
          )}

          {error && (
            <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {mode === 'login' ? (
              <LogIn className="h-4 w-4" aria-hidden="true" />
            ) : (
              <UserPlus className="h-4 w-4" aria-hidden="true" />
            )}
            {isSubmitting ? (mode === 'login' ? '登录中' : '注册中') : mode === 'login' ? '登录' : '注册并进入'}
          </button>
        </form>
      </main>
    </div>
  )
}
