import { Toaster } from 'sonner'
import { lazy, Suspense, useEffect } from 'react'
import { Upload } from 'lucide-react'

import { APP_NAV_ITEMS, type ViewType } from '@/app/navigation'
import { useAppShell } from '@/app/useAppShell'
import ErrorBoundary from '@/components/ErrorBoundary'
import Sidebar from '@/components/Sidebar'
import { UPLOAD_TRIGGER_EVENT } from '@/lib/ui-events'

const loadChatPage = () => import('@/pages/chat/ChatPage')
const loadBrowserPage = () => import('@/pages/browser/BrowserPage')
const loadDashboardPage = () => import('@/pages/dashboard/DashboardPage')
const loadSettingsPage = () => import('@/pages/settings/SettingsPage')

const ChatPage = lazy(loadChatPage)
const BrowserPage = lazy(loadBrowserPage)
const DashboardPage = lazy(loadDashboardPage)
const SettingsPage = lazy(loadSettingsPage)

const PAGE_COPY: Record<ViewType, { loading: string, error: string }> = {
  chat: {
    loading: '正在加载聊天页面…',
    error: '聊天组件异常，请刷新页面',
  },
  browser: {
    loading: '正在加载知识库页面…',
    error: '知识库组件异常，请刷新页面',
  },
  dashboard: {
    loading: '正在加载指标页面…',
    error: '指标面板异常，请刷新页面',
  },
  settings: {
    loading: '正在加载设置页面…',
    error: '设置面板异常，请刷新页面',
  },
}

export default function App() {
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

  useEffect(() => {
    if (import.meta.env.MODE === 'test') return

    const preloadViews = () => {
      void loadBrowserPage()
      void loadDashboardPage()
      void loadSettingsPage()
    }

    if ('requestIdleCallback' in window) {
      const idleId = window.requestIdleCallback(preloadViews)
      return () => window.cancelIdleCallback(idleId)
    }

    const timeoutId = globalThis.setTimeout(preloadViews, 800)
    return () => globalThis.clearTimeout(timeoutId)
  }, [])

  const renderStatus = (message: string) => (
    <div className="flex flex-1 items-center justify-center p-8 text-center text-sm text-muted-foreground">
      {message}
    </div>
  )

  const renderActiveView = () => {
    switch (activeView) {
      case 'chat':
        return (
          <ErrorBoundary key="chat" fallback={renderStatus(PAGE_COPY.chat.error)}>
            <Suspense fallback={renderStatus(PAGE_COPY.chat.loading)}>
              <ChatPage
                key={`chat-${activeWsId || 'default'}`}
                chat={chat}
                onOpenSidebar={() => setSidebarOpen(true)}
                sidebarOpen={sidebarOpen}
                onNavigate={setActiveView}
                isLoadingMessages={isLoadingMessages}
                onCitationClick={handleCitationClick}
                onSendQuestion={handleSendQuestion}
                workspaceSummary={workspaceSummary}
                isMobile={isMobile}
              />
            </Suspense>
          </ErrorBoundary>
        )
      case 'browser':
        return (
          <ErrorBoundary key="browser" fallback={renderStatus(PAGE_COPY.browser.error)}>
            <Suspense fallback={renderStatus(PAGE_COPY.browser.loading)}>
              <BrowserPage
                key={`browser-${activeWsId || 'default'}`}
                onOpenSidebar={() => setSidebarOpen(true)}
                sidebarOpen={sidebarOpen}
                onNavigate={setActiveView}
                highlightChunkId={highlightChunkId}
                onHighlightConsumed={() => setHighlightChunkId(null)}
                workspaceId={activeWsId}
                workspaceName={workspaceSummary.workspaceName}
              />
            </Suspense>
          </ErrorBoundary>
        )
      case 'dashboard':
        return (
          <ErrorBoundary key="dashboard" fallback={renderStatus(PAGE_COPY.dashboard.error)}>
            <Suspense fallback={renderStatus(PAGE_COPY.dashboard.loading)}>
              <DashboardPage
                onOpenSidebar={() => setSidebarOpen(true)}
                sidebarOpen={sidebarOpen}
                onNavigate={setActiveView}
              />
            </Suspense>
          </ErrorBoundary>
        )
      case 'settings':
        return (
          <ErrorBoundary key="settings" fallback={renderStatus(PAGE_COPY.settings.error)}>
            <Suspense fallback={renderStatus(PAGE_COPY.settings.loading)}>
              <SettingsPage
                onOpenSidebar={() => setSidebarOpen(true)}
                sidebarOpen={sidebarOpen}
                onNavigate={setActiveView}
              />
            </Suspense>
          </ErrorBoundary>
        )
    }
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background noise-overlay">
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
        {renderActiveView()}

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
