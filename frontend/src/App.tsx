import { Toaster } from 'sonner'
import { useState, useCallback } from 'react'
import { useChat } from '@/hooks/useChat'
import type { Source } from '@/lib/api'
import Sidebar from '@/components/Sidebar'
import ChatArea from '@/components/ChatArea'
import BrowserPage from '@/components/BrowserPage'
import DashboardPage from '@/components/DashboardPage'

export type ViewType = 'chat' | 'browser' | 'dashboard'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
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

  const handleCitationClick = useCallback((source: Source) => {
    if (source.chunk_id) {
      setHighlightChunkId(source.chunk_id)
    }
    setActiveView('browser')
  }, [])

  const handleSendQuestion = useCallback((q: string) => {
    setActiveView('chat')
    setTimeout(() => chat.sendMessage(q, false, 'balanced'), 100)
  }, [chat])

  // Sync workspaceId to chat hook
  const syncWsId = useCallback((wsId: string) => {
    setActiveWsId(wsId)
    chat.setWorkspaceId(wsId)
  }, [chat])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background noise-overlay">
      <div
        className={`flex-shrink-0 border-r border-border transition-all duration-300 z-10 ${
          sidebarOpen ? 'w-72' : 'w-0 overflow-hidden'
        }`}
      >
        <Sidebar
          chat={chat}
          activeView={activeView}
          onNavigate={setActiveView}
          onClose={() => setSidebarOpen(false)}
          convRefreshKey={convRefreshKey}
          activeThreadId={activeThreadId}
          onLoadingMessages={setIsLoadingMessages}
          onWorkspaceChange={syncWsId}
        />
      </div>

      <main className="relative flex flex-1 flex-col min-w-0">
        {activeView === 'chat' && (
          <ChatArea
            chat={chat}
            onOpenSidebar={() => setSidebarOpen(true)}
            sidebarOpen={sidebarOpen}
            onNavigate={setActiveView}
            isLoadingMessages={isLoadingMessages}
            onCitationClick={handleCitationClick}
            onSendQuestion={handleSendQuestion}
          />
        )}
        {activeView === 'browser' && (
          <BrowserPage
            onOpenSidebar={() => setSidebarOpen(true)}
            sidebarOpen={sidebarOpen}
            onNavigate={setActiveView}
            highlightChunkId={highlightChunkId}
            onHighlightConsumed={() => setHighlightChunkId(null)}
            workspaceId={activeWsId}
          />
        )}
        {activeView === 'dashboard' && (
          <DashboardPage
            onOpenSidebar={() => setSidebarOpen(true)}
            sidebarOpen={sidebarOpen}
            onNavigate={setActiveView}
          />
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
