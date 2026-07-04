import { useEffect, useRef, useState } from 'react'
import React from 'react'
import { Button, ScrollArea, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, Input, ConfirmDialog } from '@/components/ui'
import {
  MessageSquare, FileText, Bookmark,
  PanelRightClose, BookOpen, BarChart3, Settings, Plus, Trash2, Sun, Moon,
} from 'lucide-react'
import * as api from '@/lib/api'
import { useConversations, useSources, useWorkspaces } from '@/hooks/useData'
import { useTheme } from '@/hooks/useTheme'
import ConversationList from '@/components/sidebar/ConversationList'
import DocumentPanel from '@/components/sidebar/DocumentPanel'
import BookmarkPanel from '@/components/sidebar/BookmarkPanel'
import KBSummary from '@/components/sidebar/KBSummary'
import DashboardSummary from '@/components/sidebar/DashboardSummary'
import type { ChatMessage } from '@/hooks/useChat'
import type { Conversation, DebugInfo, PinStateResponse } from '@/lib/api'
import { OPEN_DOCUMENTS_PANEL_EVENT } from '@/lib/ui-events'
import { APP_NAV_ITEMS, type ViewType } from '@/app/navigation'
import type { WorkspaceSummary } from '@/types/workspace-summary'

interface SidebarProps {
  chat: {
    messages: ChatMessage[]
    loadMessages: (msgs: ChatMessage[], threadId?: string, pinState?: PinStateResponse) => void
    clearMessages: () => void
    sendMessage: (q: string, webSearchEnabled: boolean, searchStrategy: string) => void
    threadId: string | null
    workspaceId: string
  }
  activeView: ViewType
  onNavigate: (v: ViewType) => void
  onClose: () => void
  convRefreshKey: number
  activeThreadId: string | null
  onLoadingMessages?: (loading: boolean) => void
  onWorkspaceChange?: (wsId: string) => void
  onWorkspaceSummaryChange?: (summary: WorkspaceSummary) => void
  isMobile?: boolean
}

const DEFAULT_WORKSPACE_SELECT_VALUE = '__default_workspace__'

export default function Sidebar({ chat, activeView, onNavigate, onClose, convRefreshKey, activeThreadId, onLoadingMessages, onWorkspaceChange, onWorkspaceSummaryChange, isMobile = false }: SidebarProps) {
  const theme = useTheme()
  const wss = useWorkspaces()
  const convs = useConversations(wss.activeWorkspaceId || undefined)
  const srcs = useSources(wss.activeWorkspaceId)
  const [tab, setTab] = useState<'conversations' | 'documents' | 'bookmarks'>('conversations')
  const [createOpen, setCreateOpen] = useState(false)
  const [createName, setCreateName] = useState('')
  const [deleteWsOpen, setDeleteWsOpen] = useState(false)
  const prevKey = useRef(convRefreshKey)
  const autoLoadedConversationKeyRef = useRef<string | null>(null)
  const workspaceSelectValue = wss.activeWorkspaceId || DEFAULT_WORKSPACE_SELECT_VALUE
  const workspaceScopeKey = wss.activeWorkspaceId || DEFAULT_WORKSPACE_SELECT_VALUE

  // Refresh conversation list when workspace changes or new conv created
  useEffect(() => {
    if (convRefreshKey !== prevKey.current) {
      prevKey.current = convRefreshKey
      convs.refresh().then((list) => {
        const matched = list.find((conv) => conv.thread_id === activeThreadId)
        if (matched) {
          convs.setActiveId(matched.id)
        }
      })
    }
  }, [activeThreadId, convRefreshKey])

  useEffect(() => {
    const activeWorkspace = wss.workspaces.find((ws) => ws.id === wss.activeWorkspaceId)
    onWorkspaceSummaryChange?.({
      workspaceName: activeWorkspace?.name || '默认工作区',
      documentCount: srcs.sources.length,
      conversationCount: convs.conversations.length,
    })
  }, [
    convs.conversations.length,
    onWorkspaceSummaryChange,
    srcs.sources.length,
    wss.activeWorkspaceId,
    wss.workspaces,
  ])

  useEffect(() => {
    onWorkspaceChange?.(wss.activeWorkspaceId)
  }, [onWorkspaceChange, wss.activeWorkspaceId])

  useEffect(() => {
    const openDocumentsPanel = () => {
      onNavigate('chat')
      setTab('documents')
    }
    window.addEventListener(OPEN_DOCUMENTS_PANEL_EVENT, openDocumentsPanel)
    return () => window.removeEventListener(OPEN_DOCUMENTS_PANEL_EVENT, openDocumentsPanel)
  }, [onNavigate])

  const loadConversation = async (conversation: Conversation, closeOnMobile = true) => {
    onNavigate('chat')
    onLoadingMessages?.(true)
    try {
      const [msgs, pinState] = await Promise.all([
        api.getMessages(conversation.id),
        api.getConversationPinState(conversation.id),
      ])
      convs.setActiveId(conversation.id)
      chat.loadMessages(
        msgs.map((m) => {
          const debugInfo = m.debug_info as DebugInfo | undefined
          const debugRecord = m.debug_info as Record<string, unknown> | undefined
          return {
            id: `${m.role}-${m.id}`,
            role: m.role,
            content: m.content,
            searchStrategy: typeof debugRecord?.search_strategy === 'string' ? debugRecord.search_strategy : undefined,
            webSearchEnabled: typeof debugRecord?.used_web_search === 'boolean' ? debugRecord.used_web_search : undefined,
            sources: m.sources,
            quality_reason: m.quality_reason,
            debugData: debugInfo,
            evidence_level: typeof debugRecord?.evidence_level === 'string' ? debugRecord.evidence_level : undefined,
            evidence_summary: typeof debugRecord?.evidence_summary === 'string' ? debugRecord.evidence_summary : undefined,
            outcome_category: typeof debugRecord?.outcome_category === 'string' ? debugRecord.outcome_category : undefined,
            usedRerank: typeof debugRecord?.used_rerank === 'boolean' ? debugRecord.used_rerank : undefined,
            convId: conversation.id,
            assistantMsgId: m.role === 'assistant' ? m.id : undefined,
          }
        }),
        conversation.thread_id,
        pinState,
      )
      if (closeOnMobile && isMobile) onClose()
    } catch (e) {
      console.error('切换对话失败:', e)
    }
    onLoadingMessages?.(false)
  }

  useEffect(() => {
    if (convs.loading || chat.workspaceId !== wss.activeWorkspaceId || !convs.activeId) return
    const activeConversation = convs.conversations.find((conversation) => conversation.id === convs.activeId)
    if (!activeConversation) return

    const conversationScopeKey = `${workspaceScopeKey}:${activeConversation.id}`
    if (chat.threadId === activeConversation.thread_id) {
      autoLoadedConversationKeyRef.current = conversationScopeKey
      return
    }
    if (autoLoadedConversationKeyRef.current === conversationScopeKey) return

    autoLoadedConversationKeyRef.current = conversationScopeKey
    void loadConversation(activeConversation, false)
  }, [
    chat.threadId,
    chat.workspaceId,
    convs.activeId,
    convs.conversations,
    convs.loading,
    workspaceScopeKey,
    wss.activeWorkspaceId,
  ])

  const switchConversation = async (conversation: Conversation) => {
    await loadConversation(conversation)
  }

  const handleNewConversation = () => {
    onNavigate('chat')
    chat.clearMessages()
    convs.setActiveId(null)
    if (isMobile) onClose()
  }

  const handleDelete = async (id: string) => {
    const isActive = convs.activeId === id
    await convs.remove(id)
    if (isActive) {
      chat.clearMessages()
    }
  }

  return (
    <div className="flex h-full flex-col bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="font-heading text-xl leading-none tracking-tight text-primary">K</span>
          <div>
            <span className="block text-sm font-medium text-foreground/70 leading-tight">KnowBase</span>
            <span className="block text-2xs text-muted-foreground/40 tracking-widest uppercase">RAG Assistant</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button onClick={theme.toggle}
                  className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
                  {theme.theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
                </button>
              </TooltipTrigger>
              <TooltipContent>{theme.theme === 'dark' ? '切换浅色模式' : '切换深色模式'}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <PanelRightClose className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Workspace selector */}
      <div className="border-b border-border px-3 py-2">
        <div className="flex items-center gap-1">
          <Select
            value={workspaceSelectValue}
            onValueChange={(value) => {
              const workspaceId = value === DEFAULT_WORKSPACE_SELECT_VALUE ? '' : value
              const nextWorkspace = wss.workspaces.find((ws) => ws.id === workspaceId)
              wss.setActiveWorkspaceId(workspaceId)
              onWorkspaceSummaryChange?.({
                workspaceName: nextWorkspace?.name || '默认工作区',
                documentCount: 0,
                conversationCount: 0,
              })
              onWorkspaceChange?.(workspaceId)
            }}
          >
            <SelectTrigger className="flex-1 h-7 text-xs px-2 py-1">
              <SelectValue placeholder="选择工作区" />
            </SelectTrigger>
            <SelectContent>
              {wss.workspaces.map((ws) => (
                <SelectItem
                  key={ws.id || DEFAULT_WORKSPACE_SELECT_VALUE}
                  value={ws.id || DEFAULT_WORKSPACE_SELECT_VALUE}
                  className="text-xs"
                >
                  {ws.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <button
            onClick={() => { setCreateName(''); setCreateOpen(true) }}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            title="创建工作区"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
          {wss.activeWorkspaceId && (
            <button
              onClick={() => setDeleteWsOpen(true)}
              className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
              title="删除工作区"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {/* Nav */}
      <div className="flex gap-0.5 border-b border-border p-1.5">
        {APP_NAV_ITEMS.map((item) => (
          <button
            key={item.view}
            onClick={() => onNavigate(item.view)}
            className={`flex-1 flex items-center justify-center gap-1.5 rounded-md py-2 text-xs font-medium tracking-wide transition-all ${
              activeView === item.view
                ? 'bg-primary/15 text-primary shadow-sm'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            }`}
          >
            <item.icon className="h-3.5 w-3.5" />
            {item.label}
          </button>
        ))}
      </div>

      <ScrollArea className="flex-1 px-3 py-3">
        {activeView === 'chat' ? (
          tab === 'conversations' ? (
            <ConversationList
              key={`conversations-${workspaceScopeKey}`}
              conversations={convs.conversations}
              activeId={convs.activeId}
              loading={convs.loading}
              onSwitch={switchConversation}
              onNew={handleNewConversation}
              onRename={(id, title) => convs.rename(id, title)}
              onDelete={handleDelete}
              onBatchDelete={(ids) => convs.refresh()}
              setActiveId={convs.setActiveId}
              clearMessages={chat.clearMessages}
            />
          ) : tab === 'documents' ? (
            <DocumentPanel
              key={`documents-${workspaceScopeKey}`}
              sources={srcs.sources}
              onRefresh={srcs.refresh}
              workspaceId={wss.activeWorkspaceId}
              workspaceName={wss.workspaces.find((ws) => ws.id === wss.activeWorkspaceId)?.name || '默认工作区'}
              onSendQuestion={(q) => { onNavigate('chat'); chat.sendMessage(q, false, 'balanced') }}
              onOpenKnowledgeBase={() => onNavigate('browser')}
            />
          ) : (
            <BookmarkPanel
              key={`bookmarks-${workspaceScopeKey}`}
              workspaceId={wss.activeWorkspaceId || undefined}
              onNavigate={onNavigate}
            />
          )
        ) : activeView === 'browser' ? (
          <KBSummary
            key={`kb-summary-${workspaceScopeKey}`}
            workspaceId={wss.activeWorkspaceId}
            workspaceName={wss.workspaces.find((ws) => ws.id === wss.activeWorkspaceId)?.name || '默认工作区'}
          />
        ) : activeView === 'dashboard' ? (
          <DashboardSummary key={`dashboard-summary-${workspaceScopeKey}`} />
        ) : (
          <div className="rounded-lg border border-dashed border-border/60 bg-surface/20 p-4 text-xs text-muted-foreground/70">
            <p className="font-medium text-foreground/80">设置项将在主面板中编辑</p>
            <p className="mt-1">这里保留导航、工作区切换和常用入口，避免误显示仪表板摘要。</p>
          </div>
        )}
      </ScrollArea>

      {/* Tab toggle */}
      {activeView === 'chat' && (
        <div className="border-t border-border px-3 py-2">
          <div className="flex rounded-md bg-muted/50 p-0.5">
            <button onClick={() => setTab('conversations')}
              className={`flex-1 py-1.5 text-2xs font-medium rounded-sm transition-colors ${
                tab === 'conversations' ? 'bg-surface text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
              }`}>
              <MessageSquare className="inline h-3 w-3 mr-1" />对话
            </button>
            <button onClick={() => setTab('documents')}
              className={`flex-1 py-1.5 text-2xs font-medium rounded-sm transition-colors ${
                tab === 'documents' ? 'bg-surface text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
              }`}>
              <FileText className="inline h-3 w-3 mr-1" />文档
            </button>
            <button onClick={() => setTab('bookmarks')}
              className={`flex-1 py-1.5 text-2xs font-medium rounded-sm transition-colors ${
                tab === 'bookmarks' ? 'bg-surface text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
              }`}>
              <Bookmark className="inline h-3 w-3 mr-1" />书签
            </button>
          </div>
        </div>
      )}

      {/* Create workspace dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>创建工作区</DialogTitle>
            <DialogDescription>输入新工作区的名称</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <Input
              placeholder="工作区名称"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && createName.trim()) {
                  wss.create(createName.trim())
                  setCreateOpen(false)
                }
              }}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreateOpen(false)}>取消</Button>
              <Button onClick={() => {
                if (createName.trim()) {
                  wss.create(createName.trim())
                  setCreateOpen(false)
                }
              }}>
                创建
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete workspace confirm */}
      <ConfirmDialog
        open={deleteWsOpen}
        onOpenChange={setDeleteWsOpen}
        title="删除工作区"
        description={`确定要删除工作区"${wss.workspaces.find(ws => ws.id === wss.activeWorkspaceId)?.name ?? ''}"吗？此操作不可撤销。`}
        onConfirm={() => wss.remove(wss.activeWorkspaceId)}
      />
    </div>
  )
}
