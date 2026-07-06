import { FormEvent, useState } from 'react'
import { LockKeyhole, LogIn } from 'lucide-react'

import { login } from '@/shared/api/auth'
import { ApiError } from '@/shared/api/client'
import { saveAuthSession } from '@/shared/api/session'
import type { AuthSession } from '@/shared/api/types'

interface LoginPageProps {
  onAuthenticated: (session: AuthSession) => void
}

export default function LoginPage({ onAuthenticated }: LoginPageProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (isSubmitting) return
    setError('')
    setIsSubmitting(true)
    try {
      const session = await login({ username: username.trim(), password })
      saveAuthSession(session)
      onAuthenticated(session)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '登录失败，请稍后重试')
    } finally {
      setIsSubmitting(false)
    }
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
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"
              required
            />
          </div>

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
            <LogIn className="h-4 w-4" aria-hidden="true" />
            {isSubmitting ? '登录中' : '登录'}
          </button>
        </form>
      </main>
    </div>
  )
}
