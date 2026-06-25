import { useEffect, useRef, useState } from 'react'
import { Button, ScrollArea } from '@/components/ui'
import {
  MessageSquare, FileText,
  PanelRightClose, BookOpen, BarChart3,
} from 'lucide-react'
import * as api from '@/lib/api'
import { useConversations, useSources } from '@/hooks/useData'
import ConversationList from '@/components/sidebar/ConversationList'
import DocumentPanel from '@/components/sidebar/DocumentPanel'
import KBSummary from '@/components/sidebar/KBSummary'
import type { ChatMessage } from '@/hooks/useChat'
import type { Conversation, DebugInfo } from '@/lib/api'
import type { ViewType } from '@/App'

interface SidebarProps {
  chat: {
    messages: ChatMessage[]
    loadMessages: (msgs: ChatMessage[], threadId?: string) => void
    clearMessages: () => void
    sendMessage: (q: string, webSearchEnabled: boolean, searchStrategy: string) => void
  }
  activeView: ViewType
  onNavigate: (v: ViewType) => void
  onClose: () => void
  convRefreshKey: number
  activeThreadId: string | null
  onLoadingMessages?: (loading: boolean) => void
}

const NAV_ITEMS: { view: ViewType; icon: typeof MessageSquare; label: string }[] = [
  { view: 'chat', icon: MessageSquare, label: '对话' },
  { view: 'browser', icon: BookOpen, label: '知识库' },
  { view: 'dashboard', icon: BarChart3, label: '指标' },
]

export default function Sidebar({ chat, activeView, onNavigate, onClose, convRefreshKey, activeThreadId, onLoadingMessages }: SidebarProps) {
  const convs = useConversations()
  const srcs = useSources()
  const [tab, setTab] = useState<'conversations' | 'documents'>('conversations')
  const prevKey = useRef(convRefreshKey)

  // 新对话创建后刷新侧栏列表
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

  const switchConversation = async (conversation: Conversation) => {
    onNavigate('chat')
    onLoadingMessages?.(true)
    try {
      const msgs = await api.getMessages(conversation.id)
      convs.setActiveId(conversation.id)
      chat.loadMessages(
        msgs.map((m) => ({
          id: `${m.role}-${m.id}`,
          role: m.role,
          content: m.content,
          sources: m.sources,
          quality_reason: m.quality_reason,
          debugData: m.debug_info as DebugInfo | undefined,
          evidence_level: (m.debug_info as Record<string, string> | undefined)?.evidence_level,
          evidence_summary: (m.debug_info as Record<string, string> | undefined)?.evidence_summary,
          outcome_category: (m.debug_info as Record<string, string> | undefined)?.outcome_category,
          convId: conversation.id,
          assistantMsgId: m.role === 'assistant' ? m.id : undefined,
        })),
        conversation.thread_id,
      )
    } catch (e) {
      console.error('切换对话失败:', e)
    }
    onLoadingMessages?.(false)
  }

  const handleNewConversation = () => {
    onNavigate('chat')
    chat.clearMessages()
    convs.setActiveId(null)
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
            <span className="block text-[9px] text-muted-foreground/40 tracking-widest uppercase">RAG Assistant</span>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          <PanelRightClose className="h-4 w-4" />
        </Button>
      </div>

      {/* Nav */}
      <div className="flex gap-0.5 border-b border-border p-1.5">
        {NAV_ITEMS.map((item) => (
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
          ) : (
            <DocumentPanel sources={srcs.sources} onRefresh={srcs.refresh} onSendQuestion={(q) => { onNavigate('chat'); chat.sendMessage(q, false, 'balanced') }} />
          )
        ) : activeView === 'browser' ? (
          <KBSummary />
        ) : (
          <div className="px-3 py-4">
            <p className="text-xs text-muted-foreground/50 tracking-wide uppercase px-1 mb-2">快速统计</p>
            <div className="rounded-lg border border-border bg-surface/30 p-3">
              <p className="text-[10px] text-muted-foreground/50">打开指标面板查看详情</p>
            </div>
          </div>
        )}
      </ScrollArea>

      {/* Tab toggle */}
      {activeView === 'chat' && (
        <div className="border-t border-border px-3 py-2">
          <div className="flex rounded-md bg-muted/50 p-0.5">
            <button onClick={() => setTab('conversations')}
              className={`flex-1 py-1.5 text-[10px] font-medium rounded-sm transition-colors ${
                tab === 'conversations' ? 'bg-surface text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
              }`}>
              <MessageSquare className="inline h-3 w-3 mr-1" />对话
            </button>
            <button onClick={() => setTab('documents')}
              className={`flex-1 py-1.5 text-[10px] font-medium rounded-sm transition-colors ${
                tab === 'documents' ? 'bg-surface text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
              }`}>
              <FileText className="inline h-3 w-3 mr-1" />文档
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
