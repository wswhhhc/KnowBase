import { toast } from 'sonner'
import { useEffect, useRef, useState } from 'react'
import { Button, Input, Separator, ScrollArea } from '@/components/ui'
import {
  MessageSquare, Plus, Trash2, FileText, Globe, Upload,
  PanelRightClose, BookOpen, BarChart3, Pencil, Check, X,
} from 'lucide-react'
import { formatTime, truncate } from '@/lib/utils'
import * as api from '@/lib/api'
import { useConversations, useSources } from '@/hooks/useData'
import type { ChatMessage } from '@/hooks/useChat'
import type { Conversation } from '@/lib/api'
import type { ViewType } from '@/App'

interface SidebarProps {
  chat: {
    messages: ChatMessage[]
    loadMessages: (msgs: ChatMessage[], threadId?: string) => void
    clearMessages: () => void
  }
  activeView: ViewType
  onNavigate: (v: ViewType) => void
  onClose: () => void
  convRefreshKey: number
  activeThreadId: string | null
  onLoadingMessages?: (loading: boolean) => void
}

function KBSummary() {
  const [stats, setStats] = useState<{ chunk_count: number; source_count: number } | null>(null)
  useEffect(() => { api.getKBStats().then(setStats).catch((e: unknown) => toast.error('加载知识库统计失败', { description: String(e) })) }, [])
  return (
    <div className="px-3 py-4">
      <p className="text-xs text-muted-foreground/50 tracking-wide uppercase px-1 mb-2">知识库</p>
      <div className="rounded-lg border border-border bg-surface/30 p-3 space-y-1.5">
        {stats ? (
          <>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">片段</span>
              <span className="font-mono text-foreground/70">{stats.chunk_count}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">来源</span>
              <span className="font-mono text-foreground/70">{stats.source_count}</span>
            </div>
          </>
        ) : (
          <p className="text-xs text-muted-foreground/50">加载中…</p>
        )}
      </div>
    </div>
  )
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
  const [urlInput, setUrlInput] = useState('')
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
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
    convs.setActiveId(conversation.id)
    onLoadingMessages?.(true)
    try {
      const msgs = await api.getMessages(conversation.id)
      chat.loadMessages(
        msgs.map((m) => ({
          id: `${m.role}-${m.id}`,
          role: m.role,
          content: m.content,
          sources: m.sources,
          quality_reason: m.quality_reason,
        })),
        conversation.thread_id,
      )
    } catch { /* ignore */ }
    onLoadingMessages?.(false)
  }

  const handleNewConversation = () => {
    onNavigate('chat')
    chat.clearMessages()
    convs.setActiveId(null)
  }

  const handleRename = async (id: string) => {
    if (renameValue.trim()) {
      await convs.rename(id, renameValue.trim())
    }
    setRenamingId(null)
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await api.uploadDocument(file)
      await srcs.refresh()
      toast.success('文档已上传', { description: file.name })
    } catch (err) { toast.error('上传失败', { description: String(err) }) }
    e.target.value = ''
  }

  const handleIngestUrl = async () => {
    if (!urlInput.trim()) return
    try {
      await api.ingestUrl(urlInput.trim())
      setUrlInput('')
      await srcs.refresh()
      toast.success('网页已导入')
    } catch (err) { toast.error('导入失败', { description: String(err) }) }
  }

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return
    const ids = Array.from(selectedIds)
    try {
      await api.deleteConversations(ids)
      // 请求成功后再清理 UI 状态
      if (convs.activeId && selectedIds.has(convs.activeId)) {
        chat.clearMessages()
        convs.setActiveId(null)
      }
      setSelectedIds(new Set())
      await convs.refresh()
      toast.success(`已删除 ${ids.length} 个对话`)
    } catch (err) {
      toast.error('批量删除失败', { description: String(err) })
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
            <div className="space-y-1">
              <div className="flex items-center gap-1 mb-3">
                <Button variant="secondary" size="sm" className="flex-1 justify-start gap-2" onClick={handleNewConversation}>
                  <Plus className="h-4 w-4" />新对话
                </Button>
                {convs.conversations.length > 0 && (
                  <label className="flex items-center gap-1 cursor-pointer text-xs text-muted-foreground hover:text-foreground transition-colors px-1">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === convs.conversations.length && convs.conversations.length > 0}
                      onChange={() =>
                        setSelectedIds(
                          selectedIds.size === convs.conversations.length
                            ? new Set()
                            : new Set(convs.conversations.map((c) => c.id)),
                        )
                      }
                      className="h-3.5 w-3.5 accent-primary shrink-0 cursor-pointer"
                    />
                    全选
                  </label>
                )}
                {selectedIds.size > 0 && (
                  <Button variant="destructive" size="sm" className="gap-1" onClick={handleBatchDelete}>
                    <Trash2 className="h-3.5 w-3.5" />{selectedIds.size}
                  </Button>
                )}
              </div>
              {convs.conversations.map((c) => (
                <div
                  key={c.id}
                  className={`group flex items-center rounded-md px-3 py-2 text-sm transition-all ${
                    convs.activeId === c.id
                      ? 'bg-primary/10 text-primary'
                      : 'text-foreground/70 hover:bg-muted hover:text-foreground'
                  }`}
                >
                  {renamingId === c.id ? (
                    <div className="flex items-center gap-1 flex-1" onClick={(e) => e.stopPropagation()}>
                      <Input
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        className="h-7 text-xs flex-1"
                        autoFocus
                        onKeyDown={(e) => { if (e.key === 'Enter') handleRename(c.id); if (e.key === 'Escape') setRenamingId(null) }}
                      />
                      <button onClick={() => handleRename(c.id)}><Check className="h-3 w-3 text-emerald-400" /></button>
                      <button onClick={() => setRenamingId(null)}><X className="h-3 w-3 text-muted-foreground" /></button>
                    </div>
                  ) : (
                    <>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(c.id)}
                        onChange={() => toggleSelect(c.id)}
                        className="mr-2 h-3.5 w-3.5 accent-primary shrink-0 cursor-pointer"
                        onClick={(e) => e.stopPropagation()}
                      />
                      <span className="truncate flex-1 cursor-pointer" onClick={() => switchConversation(c)}>{truncate(c.title, 24)}</span>
                      <span className="text-[10px] text-muted-foreground opacity-0 group-hover:opacity-60 transition-opacity flex-shrink-0 mr-1">{formatTime(c.updated_at)}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); setRenamingId(c.id); setRenameValue(c.title) }}
                        className="opacity-0 group-hover:opacity-60 text-muted-foreground hover:text-foreground transition-all mr-0.5"
                      >
                        <Pencil className="h-3 w-3" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); convs.remove(c.id) }}
                        className="opacity-0 group-hover:opacity-60 text-muted-foreground hover:text-destructive transition-all"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </>
                  )}
                </div>
              ))}
              {convs.conversations.length === 0 && !convs.loading && (
                <p className="text-xs text-muted-foreground text-center py-6">暂无对话</p>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5 tracking-wide uppercase">上传文档</label>
                <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-border px-3 py-2.5 text-sm text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors">
                  <Upload className="h-4 w-4" />选择文件
                  <input type="file" className="hidden" accept=".txt,.md,.pdf,.docx,.html" onChange={handleUpload} />
                </label>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5 tracking-wide uppercase">导入公开网页</label>
                <div className="flex gap-2">
                  <Input placeholder="https://…" value={urlInput} onChange={(e) => setUrlInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleIngestUrl() }} className="flex-1" />
                  <Button size="sm" onClick={handleIngestUrl}><Globe className="h-3.5 w-3.5" /></Button>
                </div>
              </div>
              <Separator />
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-muted-foreground tracking-wide uppercase">文档来源</span>
                  {srcs.sources.length > 0 && (
                    <button onClick={async () => { await api.clearKnowledgeBase(); await srcs.refresh(); toast.success('知识库已清空') }}
                      className="text-[10px] text-destructive/50 hover:text-destructive transition-colors">清空</button>
                  )}
                </div>
                <div className="space-y-0.5">
                  {srcs.sources.map((s) => (
                    <div key={s.source} className="group flex items-center justify-between rounded-md px-2.5 py-1.5 text-sm text-foreground/70 hover:bg-muted transition-colors">
                      <span className="truncate flex-1">{s.source}</span>
                      <span className="text-[10px] text-muted-foreground mr-2 font-mono">{s.count}</span>
                      <button onClick={() => { api.deleteSource(s.source); srcs.refresh(); toast.success('已删除来源') }}
                        className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-all">
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                  {srcs.sources.length === 0 && (
                    <p className="text-xs text-muted-foreground/60 text-center py-6 italic">知识库为空</p>
                  )}
                </div>
              </div>
            </div>
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
