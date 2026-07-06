import { lazy, Suspense, useEffect } from 'react'

import type { ViewType } from '@/app/navigation'
import ErrorBoundary from '@/components/ErrorBoundary'
import type { useChat } from '@/hooks/useChat'
import type { Source } from '@/shared/api'
import type { WorkspaceSummary } from '@/types/workspace-summary'

const loadChatPage = () => import('@/pages/chat/ChatPage')
const loadBrowserPage = () => import('@/pages/browser/BrowserPage')
const loadJobsPage = () => import('@/pages/jobs/JobsPage')
const loadDashboardPage = () => import('@/pages/dashboard/DashboardPage')
const loadSettingsPage = () => import('@/pages/settings/SettingsPage')

const ChatPage = lazy(loadChatPage)
const BrowserPage = lazy(loadBrowserPage)
const JobsPage = lazy(loadJobsPage)
const DashboardPage = lazy(loadDashboardPage)
const SettingsPage = lazy(loadSettingsPage)

const PAGE_COPY: Record<ViewType, { loading: string; error: string }> = {
  chat: {
    loading: '正在加载聊天页面…',
    error: '聊天组件异常，请刷新页面',
  },
  browser: {
    loading: '正在加载知识库页面…',
    error: '知识库组件异常，请刷新页面',
  },
  jobs: {
    loading: '正在加载任务中心…',
    error: '任务中心异常，请刷新页面',
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

interface AppViewRendererProps {
  activeView: ViewType
  activeWsId: string
  chat: ReturnType<typeof useChat>
  handleCitationClick: (source: Source) => void
  handleSendQuestion: (question: string) => void
  highlightChunkId: string | null
  isLoadingMessages: boolean
  isMobile: boolean
  setActiveView: (view: ViewType) => void
  setHighlightChunkId: (chunkId: string | null) => void
  setSidebarOpen: (open: boolean) => void
  sidebarOpen: boolean
  workspaceSummary: WorkspaceSummary
  canManageKnowledgeBase?: boolean
}

function renderStatus(message: string) {
  return (
    <div className="flex flex-1 items-center justify-center p-8 text-center text-sm text-muted-foreground">
      {message}
    </div>
  )
}

export default function AppViewRenderer({
  activeView,
  activeWsId,
  chat,
  handleCitationClick,
  handleSendQuestion,
  highlightChunkId,
  isLoadingMessages,
  isMobile,
  setActiveView,
  setHighlightChunkId,
  setSidebarOpen,
  sidebarOpen,
  workspaceSummary,
  canManageKnowledgeBase = true,
}: AppViewRendererProps) {
  useEffect(() => {
    if (import.meta.env.MODE === 'test') return

    const preloadViews = () => {
      void loadBrowserPage()
      void loadJobsPage()
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
              canManageKnowledgeBase={canManageKnowledgeBase}
            />
          </Suspense>
        </ErrorBoundary>
      )
    case 'jobs':
      return (
        <ErrorBoundary key="jobs" fallback={renderStatus(PAGE_COPY.jobs.error)}>
          <Suspense fallback={renderStatus(PAGE_COPY.jobs.loading)}>
            <JobsPage
              onOpenSidebar={() => setSidebarOpen(true)}
              sidebarOpen={sidebarOpen}
              onNavigate={setActiveView}
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
