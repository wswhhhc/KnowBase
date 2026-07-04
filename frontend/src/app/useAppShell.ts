import { useCallback, useEffect, useState } from 'react'

import type { ViewType } from '@/app/navigation'
import { useChat } from '@/hooks/useChat'
import type { Source } from '@/shared/api'
import type { WorkspaceSummary } from '@/types/workspace-summary'

export function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)

  useEffect(() => {
    const mql = window.matchMedia(query)
    const handler = (event: MediaQueryListEvent) => setMatches(event.matches)
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [query])

  return matches
}

export function useAppShell() {
  const isMobile = useMediaQuery('(max-width: 767px)')
  const [sidebarOpen, setSidebarOpen] = useState(!isMobile)
  const [activeView, setActiveView] = useState<ViewType>('chat')
  const [convRefreshKey, setConvRefreshKey] = useState(0)
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [highlightChunkId, setHighlightChunkId] = useState<string | null>(null)
  const [activeWsId, setActiveWsId] = useState<string>('')
  const [workspaceSummary, setWorkspaceSummary] = useState<WorkspaceSummary>({
    workspaceName: '默认工作区',
    documentCount: 0,
    conversationCount: 0,
  })

  const chat = useChat((threadId) => {
    setActiveThreadId(threadId)
    setConvRefreshKey((key) => key + 1)
  })

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

  const handleSendQuestion = useCallback((question: string) => {
    setActiveView('chat')
    setTimeout(() => chat.sendMessage(question, false, 'balanced'), 100)
  }, [chat])

  const syncWorkspace = useCallback((workspaceId: string) => {
    if (workspaceId === activeWsId) {
      chat.setWorkspaceId(workspaceId)
      return
    }
    sessionStorage.removeItem('highlightChunkId')
    setHighlightChunkId(null)
    setActiveThreadId(null)
    setIsLoadingMessages(false)
    chat.clearMessages()
    setActiveWsId(workspaceId)
    chat.setWorkspaceId(workspaceId)
  }, [activeWsId, chat])

  return {
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
  }
}
