import { useState } from 'react'
import { Toaster } from 'sonner'
import { LogOut, Upload } from 'lucide-react'

import { APP_NAV_ITEMS, type ViewType } from '@/app/navigation'
import AppViewRenderer from '@/app/AppViewRenderer'
import { useAppShell } from '@/app/useAppShell'
import Sidebar from '@/components/Sidebar'
import { UPLOAD_TRIGGER_EVENT } from '@/lib/ui-events'
import LoginPage from '@/pages/auth/LoginPage'
import { clearAuthSession, getStoredAccessToken, getStoredRefreshToken } from '@/shared/api/session'

export default function App() {
  const [authVersion, setAuthVersion] = useState(0)
  const {
    activeThreadId,
    activeView,
    activeWsId,
    chat,
    convRefreshKey,
    handleCitationClick,
    handleSendQuestion,
    highlightChunkId,
    isLoadingMessages,
    isMobile,
    setActiveView,
    setHighlightChunkId,
    setIsLoadingMessages,
    setSidebarOpen,
    setWorkspaceSummary,
    sidebarOpen,
    syncWorkspace,
    workspaceSummary,
  } = useAppShell()

  const hasJwtSession = Boolean(getStoredAccessToken())
  const hasLegacyApiKey = Boolean(localStorage.getItem('knowbase_api_key'))
  const isAuthenticated = hasJwtSession || hasLegacyApiKey

  const handleLogout = () => {
    clearAuthSession()
    setAuthVersion((version) => version + 1)
  }

  if (!isAuthenticated) {
    return (
      <>
        <LoginPage onAuthenticated={() => setAuthVersion((version) => version + 1)} />
        <Toaster
          position="top-center"
          toastOptions={{
            style: { background: 'hsl(var(--surface))', color: 'hsl(var(--foreground))', border: '1px solid hsl(var(--border))' },
          }}
        />
      </>
    )
  }

  return (
    <div key={authVersion} className="flex h-screen w-screen overflow-hidden bg-background noise-overlay">
      {isMobile && sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div
        className={`${
          isMobile
            ? `fixed inset-y-0 left-0 z-50 transition-transform duration-300 ${
                sidebarOpen ? 'translate-x-0' : '-translate-x-full'
              }`
            : `z-10 flex-shrink-0 border-r border-border transition-all duration-300 ${
                sidebarOpen ? 'w-72' : 'w-0 overflow-hidden'
              }`
        }`}
      >
        <Sidebar
          chat={chat}
          activeView={activeView}
          onNavigate={setActiveView}
          onClose={() => setSidebarOpen(false)}
          isMobile={isMobile}
          convRefreshKey={convRefreshKey}
          activeThreadId={activeThreadId}
          onLoadingMessages={setIsLoadingMessages}
          onWorkspaceChange={syncWorkspace}
          onWorkspaceSummaryChange={setWorkspaceSummary}
        />
      </div>

      <main className="relative flex min-w-0 flex-1 flex-col pb-safe">
        {hasJwtSession && getStoredRefreshToken() && (
          <button
            type="button"
            onClick={handleLogout}
            className="absolute right-4 top-4 z-30 flex h-9 items-center gap-2 rounded-md border border-border bg-surface/90 px-3 text-sm text-muted-foreground backdrop-blur transition-colors hover:border-primary/50 hover:text-foreground"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            退出登录
          </button>
        )}
        <AppViewRenderer
          activeView={activeView}
          activeWsId={activeWsId}
          chat={chat}
          handleCitationClick={handleCitationClick}
          handleSendQuestion={handleSendQuestion}
          highlightChunkId={highlightChunkId}
          isLoadingMessages={isLoadingMessages}
          isMobile={isMobile}
          setActiveView={setActiveView}
          setHighlightChunkId={setHighlightChunkId}
          setSidebarOpen={setSidebarOpen}
          sidebarOpen={sidebarOpen}
          workspaceSummary={workspaceSummary}
        />

        {isMobile && (
          <>
            {activeView === 'browser' && (
              <button
                onClick={() => {
                  sessionStorage.setItem('kb_trigger_upload', 'true')
                  setActiveView('browser')
                  window.dispatchEvent(new Event(UPLOAD_TRIGGER_EVENT))
                  setSidebarOpen(false)
                }}
                className="fixed bottom-20 right-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/30 transition-colors hover:bg-primary/90"
                title="上传文档"
              >
                <Upload className="h-5 w-5" />
              </button>
            )}
            <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/90 backdrop-blur-lg safe-area-bottom md:hidden">
              <div className="flex h-14 items-center justify-around">
                {APP_NAV_ITEMS.map(({ view, icon: Icon, label }) => (
                  <button
                    key={view}
                    onClick={() => {
                      setActiveView(view)
                      setSidebarOpen(false)
                    }}
                    className={`flex h-full flex-col items-center justify-center gap-0.5 px-6 text-2xs font-medium transition-colors ${
                      activeView === view
                        ? 'text-primary'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <Icon className={`h-5 w-5 ${activeView === view ? 'fill-primary/15' : ''}`} />
                    <span>{label}</span>
                  </button>
                ))}
              </div>
            </nav>
          </>
        )}
      </main>

      <Toaster
        position="top-center"
        toastOptions={{
          style: { background: 'hsl(var(--surface))', color: 'hsl(var(--foreground))', border: '1px solid hsl(var(--border))' },
        }}
      />
    </div>
  )
}
