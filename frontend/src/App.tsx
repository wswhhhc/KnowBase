import { Toaster } from 'sonner'
import { useState, useCallback, useEffect } from 'react'
import { useChat } from '@/hooks/useChat'
import type { Source } from '@/lib/api'
import Sidebar from '@/components/Sidebar'
import ChatArea from '@/components/ChatArea'
import BrowserPage from '@/components/BrowserPage'
import DashboardPage from '@/components/DashboardPage'
import SettingsPage from '@/components/SettingsPage'
import ErrorBoundary from '@/components/ErrorBoundary'
import { Sparkles, BookOpen, BarChart3, Settings, Upload } from 'lucide-react'

export type ViewType = 'chat' | 'browser' | 'dashboard' | 'settings'
const UPLOAD_TRIGGER_EVENT = 'kb-trigger-upload'

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mql = window.matchMedia(query)
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches)
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [query])
  return matches
}

function App() {
  const isMobile = useMediaQuery('(max-width: 767px)')
  const [sidebarOpen, setSidebarOpen] = useState(!isMobile)
  const [activeView, setActiveView] = useState<ViewType>('chat')
  const [convRefreshKey, setConvRefreshKey] = useState(0)
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [highlightChunkId, setHighlightChunkId] = useState<string | null>(null)
  const [activeWsId, setActiveWsId] = useState<string>('')
  const chat = useChat((threadId) => {
    setActiveThreadId(threadId)
    setConvRefreshKey((k) => k + 1)
  })

  // Auto-close sidebar on mobile when switching views
  useEffect(() => {
    if (isMobile) setSidebarOpen(false)
  }, [activeView, isMobile])

  useEffect(() => {
    if (activeView !== 'browser') return
    const storedChunkId = sessionStorage.getItem('highlightChunkId')
    if (!storedChunkId) return
    setHighlightChunkId(storedChunkId)
    sessionStorage.removeItem('highlightChunkId')
  }, [activeView])

  const handleCitationClick = useCallback((source: Source) => {
    if (source.chunk_id) setHighlightChunkId(source.chunk_id)
    setActiveView('browser')
    if (isMobile) setSidebarOpen(false)
  }, [isMobile])

  const handleSendQuestion = useCallback((q: string) => {
    setActiveView('chat')
    setTimeout(() => chat.sendMessage(q, false, 'balanced'), 100)
  }, [chat])

  const syncWsId = useCallback((wsId: string) => {
    setActiveWsId(wsId)
    chat.setWorkspaceId(wsId)
  }, [chat])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background noise-overlay">
      {/* Mobile backdrop */}
      {isMobile && sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`${
          isMobile
            ? `fixed inset-y-0 left-0 z-50 transition-transform duration-300 ${
                sidebarOpen ? 'translate-x-0' : '-translate-x-full'
              }`
            : `flex-shrink-0 border-r border-border transition-all duration-300 z-10 ${
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
          onWorkspaceChange={syncWsId}
        />
      </div>

      <main className="relative flex flex-1 flex-col min-w-0 pb-safe">
        {activeView === 'chat' && (
          <ErrorBoundary fallback={<div className="flex items-center justify-center flex-1 p-8 text-center text-muted-foreground text-sm">聊天组件异常，请刷新页面</div>}>
          <ChatArea
            chat={chat}
            onOpenSidebar={() => setSidebarOpen(true)}
            sidebarOpen={sidebarOpen}
            onNavigate={setActiveView}
            isLoadingMessages={isLoadingMessages}
            onCitationClick={handleCitationClick}
            onSendQuestion={handleSendQuestion}
          />
          </ErrorBoundary>
        )}
        {activeView === 'browser' && (
          <ErrorBoundary fallback={<div className="flex items-center justify-center flex-1 p-8 text-center text-muted-foreground text-sm">知识库组件异常，请刷新页面</div>}>
          <BrowserPage
            onOpenSidebar={() => setSidebarOpen(true)}
            sidebarOpen={sidebarOpen}
            onNavigate={setActiveView}
            highlightChunkId={highlightChunkId}
            onHighlightConsumed={() => setHighlightChunkId(null)}
            workspaceId={activeWsId}
          />
          </ErrorBoundary>
        )}
        {activeView === 'dashboard' && (
          <ErrorBoundary fallback={<div className="flex items-center justify-center flex-1 p-8 text-center text-muted-foreground text-sm">指标面板异常，请刷新页面</div>}>
          <DashboardPage
            onOpenSidebar={() => setSidebarOpen(true)}
            sidebarOpen={sidebarOpen}
            onNavigate={setActiveView}
          />
          </ErrorBoundary>
        )}
        {activeView === 'settings' && (
          <ErrorBoundary fallback={<div className="flex items-center justify-center flex-1 p-8 text-center text-muted-foreground text-sm">设置面板异常，请刷新页面</div>}>
          <SettingsPage
            onOpenSidebar={() => setSidebarOpen(true)}
            sidebarOpen={sidebarOpen}
            onNavigate={setActiveView}
          />
          </ErrorBoundary>
        )}

        {/* Mobile bottom tab bar */}
        {isMobile && (
          <>
          {/* Upload FAB */}
          <button
            onClick={() => {
              sessionStorage.setItem('kb_trigger_upload', 'true')
              setActiveView('browser')
              window.dispatchEvent(new Event(UPLOAD_TRIGGER_EVENT))
              if (isMobile) setSidebarOpen(false)
            }}
            className="fixed bottom-20 right-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/30 hover:bg-primary/90 transition-colors"
            title="上传文档"
          >
            <Upload className="h-5 w-5" />
          </button>
          <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 border-t border-border bg-surface/90 backdrop-blur-lg safe-area-bottom">
            <div className="flex items-center justify-around h-14">
              {([
                { view: 'chat' as ViewType, icon: Sparkles, label: '聊天' },
                { view: 'browser' as ViewType, icon: BookOpen, label: '知识库' },
                { view: 'dashboard' as ViewType, icon: BarChart3, label: '指标' },
                { view: 'settings' as ViewType, icon: Settings, label: '设置' },
              ]).map(({ view, icon: Icon, label }) => (
                <button
                  key={view}
                  onClick={() => { setActiveView(view); setSidebarOpen(false) }}
                  className={`flex flex-col items-center justify-center gap-0.5 h-full px-6 text-2xs font-medium transition-colors ${
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

export default App
