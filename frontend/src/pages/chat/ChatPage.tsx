import { useRef, useEffect, useState, useMemo } from 'react'
import { Button, ScrollArea, Skeleton } from '@/components/ui'
import EmptyState from '@/components/EmptyState'
import MessageBubble from '@/components/MessageBubble'
import { useChat } from '@/hooks/useChat'
import type { PinnedSource } from '@/hooks/useChat'
import type { Source } from '@/shared/api'
import type { ViewType } from '@/app/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { PanelRightOpen, Square, Sparkles, BookOpen, BarChart3 } from 'lucide-react'
import { OPEN_DOCUMENTS_PANEL_EVENT } from '@/lib/ui-events'
import type { WorkspaceSummary } from '@/types/workspace-summary'
import SearchPreferencesPanel from '@/components/chat/SearchPreferencesPanel'
import { useSearchPreferences } from '@/features/chat/hooks/useSearchPreferences'

interface ChatPageProps {
  chat: ReturnType<typeof useChat>
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
  isLoadingMessages?: boolean
  onCitationClick?: (source: Source) => void
  onSendQuestion?: (q: string) => void
  workspaceSummary: WorkspaceSummary
  isMobile?: boolean
  canManageApp?: boolean
}

export default function ChatPage({ chat, onOpenSidebar, sidebarOpen, onNavigate, isLoadingMessages, onCitationClick, onSendQuestion, workspaceSummary, isMobile = false, canManageApp = true }: ChatPageProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [input, setInput] = useState('')
  const { webSearch, setWebSearch, searchStrategy, setSearchStrategy } = useSearchPreferences()

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [chat.messages, chat.streamingNodes, isLoadingMessages])

  const prevLoadingRef = useRef(isLoadingMessages)

  useEffect(() => {
    if (prevLoadingRef.current && !isLoadingMessages) {
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
      })
    }
    prevLoadingRef.current = isLoadingMessages
  }, [isLoadingMessages])

  const handleSend = () => {
    const q = input.trim()
    if (!q || chat.isStreaming) return
    setInput('')
    chat.sendMessage(q, webSearch, searchStrategy)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const focusComposer = () => {
    requestAnimationFrame(() => inputRef.current?.focus())
  }

  const openDocumentPanel = () => {
    onOpenSidebar()
    window.dispatchEvent(new Event(OPEN_DOCUMENTS_PANEL_EVENT))
  }

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px'
    }
  }, [input])

  const isEmpty = chat.messages.length === 0
  const composerPlaceholder = workspaceSummary.documentCount <= 0
    ? '先导入资料，或直接输入你想验证的问题…'
    : `基于“${workspaceSummary.workspaceName}”提问，例如：这份资料的重点是什么？`
  const emptyStateMode = useMemo(() => {
    if (workspaceSummary.documentCount <= 0) return 'onboarding' as const
    if (workspaceSummary.conversationCount > 0) return 'returning' as const
    return 'first-question' as const
  }, [workspaceSummary.conversationCount, workspaceSummary.documentCount])
  const activeTitle = !isEmpty && chat.messages[0]?.role === 'user'
    ? chat.messages[0].content.slice(0, 28)
    : 'KnowBase'

  return (
    <>
      {/* Top bar */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background/80 px-5 py-3 backdrop-blur-sm">
        <div className="flex min-w-0 items-center gap-3">
          {!sidebarOpen && (
            <Button variant="ghost" size="sm" onClick={onOpenSidebar}>
              <PanelRightOpen className="h-4 w-4" />
            </Button>
          )}
          <div className="min-w-0">
            <h1 className={`truncate font-heading text-lg text-foreground tracking-tight ${isMobile ? 'max-w-[11rem]' : 'max-w-[18rem]'}`}>{activeTitle}</h1>
            <p className="truncate text-2xs text-muted-foreground/60">
              当前工作区：{workspaceSummary.workspaceName} · {workspaceSummary.documentCount} 份资料
            </p>
          </div>
        </div>

        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
            <div className="hidden xl:flex items-center gap-0.5 rounded-md border border-border p-0.5">
              <button onClick={() => onNavigate('chat')}
                className="flex items-center gap-1 rounded-sm bg-primary/15 px-2.5 py-1 text-xs font-medium text-primary">
                <Sparkles className="h-3 w-3" />聊天
              </button>
              <button onClick={() => onNavigate('browser')}
                className="flex items-center gap-1 rounded-sm px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
                <BookOpen className="h-3 w-3" />知识库
              </button>
              {canManageApp && (
                <button onClick={() => onNavigate('dashboard')}
                  className="flex items-center gap-1 rounded-sm px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
                  <BarChart3 className="h-3 w-3" />指标
                </button>
              )}
            </div>

          <div className="hidden h-4 w-px bg-border xl:block" />

          <SearchPreferencesPanel
            variant={isMobile ? 'mobile' : 'desktop'}
            webSearch={webSearch}
            onWebSearchChange={setWebSearch}
            searchStrategy={searchStrategy}
            onSearchStrategyChange={setSearchStrategy}
          />
        </div>
      </header>

      {/* Messages */}
      <ScrollArea ref={scrollRef} className="flex-1">
        <div className="mx-auto max-w-3xl px-5 py-8">
          {isLoadingMessages ? <MessageSkeleton /> : isEmpty ? (
            <EmptyState
              mode={emptyStateMode}
              workspaceName={workspaceSummary.workspaceName}
              documentCount={workspaceSummary.documentCount}
              conversationCount={workspaceSummary.conversationCount}
              onPrimaryAction={emptyStateMode === 'onboarding' ? openDocumentPanel : focusComposer}
              onSecondaryAction={emptyStateMode === 'onboarding' ? undefined : () => onNavigate('browser')}
            />
          ) : (
            <div className="space-y-6">
              {chat.messages.map((msg, idx) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, ease: 'easeOut' }}
                >
                  <MessageBubble
                    message={msg}
                    prevMessage={idx > 0 ? chat.messages[idx - 1] : undefined}
                    threadId={chat.threadId}
                    onCitationClick={onCitationClick}
                    onSendQuestion={onSendQuestion}
                    onNavigateBrowser={() => onNavigate('browser')}
                    pinnedSources={chat.pinnedSources}
                    onPinToggle={(chunkId, action) => {
                      chat.setPinnedSources((prev: PinnedSource[]) =>
                        prev.map((ps) =>
                          ps.chunk_id === chunkId
                            ? { ...ps, pinned: action === 'pin', excluded: action === 'exclude' }
                            : ps,
                        ),
                      )
                    }}
                    workspaceId={chat.workspaceId}
                    workspaceSummary={workspaceSummary}
                  />
                </motion.div>
              ))}

              <AnimatePresence>
                {chat.isStreaming && chat.streamingNodes.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    className="flex items-center gap-2 text-xs text-muted-foreground"
                  >
                    <div className="flex items-center gap-1 flex-wrap">
                      {chat.streamingNodes.map((n, i) => (
                        <span key={n}
                          className={`px-2 py-0.5 rounded-full transition-all ${
                            i === chat.streamingNodes.length - 1
                              ? 'bg-primary/15 text-primary font-medium'
                              : 'bg-muted text-muted-foreground'
                          }`}>
                          {n}
                        </span>
                      ))}
                    </div>
                    <span className="animate-pulse-soft text-primary">●</span>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t border-border bg-surface/30 backdrop-blur-sm">
        <div className="mx-auto max-w-3xl px-5 py-4">
          <div className="relative flex items-end gap-2 rounded-xl border border-input bg-background px-4 py-2 shadow-lg shadow-black/5 focus-within:border-primary/50 focus-within:ring-1 focus-within:ring-primary/30 transition-all">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={composerPlaceholder}
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground/40 outline-none py-1.5 font-body leading-relaxed"
              disabled={chat.isStreaming}
            />
            {chat.isStreaming ? (
              <Button variant="secondary" size="sm" onClick={chat.stopStreaming}>
                <Square className="h-3.5 w-3.5 mr-1" />停止
              </Button>
            ) : (
              <Button size="sm" onClick={handleSend} disabled={!input.trim()}>
                <Sparkles className="h-3.5 w-3.5 mr-1" />发送
              </Button>
            )}
          </div>
          <p className="mt-1.5 text-2xs text-muted-foreground/30 text-center font-mono tracking-wider">
            KnowBase · RAG 问答 · 回答仅供参考
          </p>
        </div>
      </div>
    </>
  )
}

function MessageSkeleton() {
  const widths = [75, 85, 60, 90]
  return (
    <div className="space-y-6">
      {widths.map((w, i) => (
        <div key={i} className={`flex gap-3 ${i % 2 === 0 ? '' : 'flex-row-reverse'}`}>
          {i % 2 === 0 && (
            <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />
          )}
          <div className={`flex-1 ${i % 2 === 0 ? '' : 'max-w-[75%]'}`}>
            <Skeleton className="h-16 rounded-2xl" style={i % 2 === 0 ? { width: `${w}%` } : { width: `${w}%`, marginLeft: 'auto' }} />
          </div>
        </div>
      ))}
    </div>
  )
}
