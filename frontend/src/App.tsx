import { useState } from 'react'
import { useChat } from '@/hooks/useChat'
import { useTheme } from '@/hooks/useTheme'
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
  const chat = useChat((threadId) => {
    setActiveThreadId(threadId)
    setConvRefreshKey((k) => k + 1)
  })
  const theme = useTheme()

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
        />
      </div>

      <main className="relative flex flex-1 flex-col min-w-0">
        {activeView === 'chat' && (
          <ChatArea
            chat={chat}
            onOpenSidebar={() => setSidebarOpen(true)}
            sidebarOpen={sidebarOpen}
            onNavigate={setActiveView}
            theme={theme}
          />
        )}
        {activeView === 'browser' && (
          <BrowserPage
            onOpenSidebar={() => setSidebarOpen(true)}
            sidebarOpen={sidebarOpen}
            onNavigate={setActiveView}
            theme={theme}
          />
        )}
        {activeView === 'dashboard' && (
          <DashboardPage
            onOpenSidebar={() => setSidebarOpen(true)}
            sidebarOpen={sidebarOpen}
            onNavigate={setActiveView}
            theme={theme}
          />
        )}
      </main>
    </div>
  )
}

export default App
