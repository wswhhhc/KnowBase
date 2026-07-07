import { FormEvent, useState } from 'react'
import { Eye, EyeOff, Layers3, Loader2, LockKeyhole, LogIn, ShieldCheck, UserPlus } from 'lucide-react'

import { cn } from '@/lib/utils'
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
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
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
    setShowPassword(false)
    setShowConfirmPassword(false)
  }

  return (
    <div className="auth-grid noise-overlay min-h-screen overflow-hidden bg-background text-foreground">
      <main className="mx-auto grid min-h-screen w-full max-w-6xl items-center gap-10 px-4 py-8 sm:px-6 lg:grid-cols-[1fr_26rem] lg:px-8">
        <section className="auth-enter hidden min-h-[32rem] flex-col justify-between lg:flex">
          <div className="max-w-xl">
            <div className="mb-9 inline-flex items-center gap-2 rounded-md border border-border/80 bg-surface/60 px-3 py-2 text-sm text-muted-foreground backdrop-blur">
              <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
              私有知识库访问入口
            </div>
            <div className="max-w-lg font-heading text-5xl font-semibold leading-tight tracking-normal text-foreground">
              KnowBase
            </div>
            <p className="mt-5 max-w-md text-base leading-7 text-muted-foreground">
              进入团队知识库工作台，检索、整理并追踪可信资料。
            </p>
          </div>

          <div className="relative h-64 max-w-xl overflow-hidden rounded-lg border border-border/70 bg-surface/35 p-5 shadow-2xl shadow-black/20">
            <div className="auth-scanline absolute inset-0 opacity-70" aria-hidden="true" />
            <div className="relative grid h-full grid-cols-[0.9fr_1.1fr] gap-4">
              <div className="space-y-3">
                {['源文档', '切片索引', '回答证据'].map((label, index) => (
                  <div
                    key={label}
                    className="rounded-md border border-border/70 bg-background/55 p-3"
                    style={{ animationDelay: `${index * 90}ms` }}
                  >
                    <div className="mb-3 flex items-center gap-2">
                      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                      <span className="text-xs font-medium text-surface-foreground">{label}</span>
                    </div>
                    <div className="space-y-2">
                      <span className="block h-1.5 w-3/4 rounded-full bg-muted" />
                      <span className="block h-1.5 w-1/2 rounded-full bg-muted/70" />
                    </div>
                  </div>
                ))}
              </div>
              <div className="relative rounded-md border border-primary/20 bg-background/60 p-4">
                <Layers3 className="mb-8 h-5 w-5 text-primary" aria-hidden="true" />
                <div className="space-y-3">
                  <span className="block h-2 w-2/3 rounded-full bg-primary/40" />
                  <span className="block h-2 w-full rounded-full bg-muted" />
                  <span className="block h-2 w-4/5 rounded-full bg-muted/80" />
                  <span className="block h-2 w-3/5 rounded-full bg-muted/60" />
                </div>
                <div className="absolute bottom-4 right-4 rounded border border-border/70 px-2 py-1 text-xs text-muted-foreground">
                  3 条证据已同步
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="auth-enter mx-auto w-full max-w-md lg:mx-0">
          <div className="mb-7 flex items-center gap-3 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface text-primary">
              <LockKeyhole className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-normal">KnowBase</h1>
              <p className="mt-1 text-sm text-muted-foreground">团队知识库工作台</p>
            </div>
          </div>

          <form
            onSubmit={handleSubmit}
            className="space-y-5 rounded-lg border border-border/80 bg-surface/85 p-5 shadow-2xl shadow-black/25 backdrop-blur sm:p-6"
          >
            <div className="hidden items-start justify-between gap-4 lg:flex">
              <div>
                <p className="text-sm text-muted-foreground">欢迎回来</p>
                <h2 className="mt-1 text-2xl font-semibold text-surface-foreground">
                  {mode === 'login' ? '登录工作台' : '创建工作账号'}
                </h2>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background text-primary">
                <LockKeyhole className="h-5 w-5" aria-hidden="true" />
              </div>
            </div>

            <div className="relative grid grid-cols-2 gap-1 rounded-md border border-border bg-background p-1" aria-label="认证模式">
              <span
                className={cn(
                  'pointer-events-none absolute bottom-1 top-1 w-[calc(50%-0.25rem)] rounded bg-surface shadow-sm transition-transform duration-200',
                  mode === 'register' && 'translate-x-[calc(100%+0.25rem)]',
                )}
                aria-hidden="true"
              />
              <button
                type="button"
                aria-label="切换到登录模式"
                onClick={() => switchMode('login')}
                className={`relative h-9 rounded px-3 text-sm font-medium transition-colors ${
                  mode === 'login'
                    ? 'text-surface-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                登录
              </button>
              <button
                type="button"
                aria-label="切换到注册模式"
                onClick={() => switchMode('register')}
                className={`relative h-9 rounded px-3 text-sm font-medium transition-colors ${
                  mode === 'register'
                    ? 'text-surface-foreground'
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
                className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-all placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/25"
                required
              />
            </div>

          <div className="space-y-2">
            <label htmlFor="login-password" className="text-sm font-medium text-surface-foreground">
              密码
            </label>
            <div className="relative">
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="h-11 w-full rounded-md border border-input bg-background px-3 pr-11 text-sm outline-none transition-all placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/25"
                minLength={mode === 'register' ? 8 : undefined}
                required
              />
              <button
                type="button"
                aria-label={showPassword ? '隐藏输入内容' : '显示输入内容'}
                onClick={() => setShowPassword((visible) => !visible)}
                className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {showPassword ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
              </button>
            </div>
          </div>

          {mode === 'register' && (
            <div className="auth-reveal space-y-2">
              <label htmlFor="register-confirm-password" className="text-sm font-medium text-surface-foreground">
                确认密码
              </label>
              <div className="relative">
                <input
                  id="register-confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  className="h-11 w-full rounded-md border border-input bg-background px-3 pr-11 text-sm outline-none transition-all placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/25"
                  minLength={8}
                  required
                />
                <button
                  type="button"
                  aria-label={showConfirmPassword ? '隐藏确认输入' : '显示确认输入'}
                  onClick={() => setShowConfirmPassword((visible) => !visible)}
                  className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                </button>
              </div>
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
            className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/15 transition-all hover:-translate-y-0.5 hover:bg-primary/90 hover:shadow-primary/25 active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : mode === 'login' ? (
              <LogIn className="h-4 w-4" aria-hidden="true" />
            ) : (
              <UserPlus className="h-4 w-4" aria-hidden="true" />
            )}
            {isSubmitting ? (mode === 'login' ? '登录中' : '注册中') : mode === 'login' ? '登录' : '注册并进入'}
          </button>
        </form>
        </section>
      </main>
    </div>
  )
}
