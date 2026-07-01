import { useRef, useEffect, useState, useMemo } from 'react'
import { Button, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, ScrollArea, Switch, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger, Skeleton } from '@/components/ui'
import { useChat } from '@/hooks/useChat'
import type { PinnedSource } from '@/hooks/useChat'
import EmptyState from './EmptyState'
import type { Source } from '@/lib/api'
import MessageBubble from './MessageBubble'
import type { ViewType } from '@/App'
import { motion, AnimatePresence } from 'framer-motion'
import { PanelRightOpen, Square, Sparkles, BookOpen, BarChart3, Globe, SlidersHorizontal, Zap, Scale, FileSearch, Search } from 'lucide-react'
import type { WorkspaceSummary } from '@/types/workspace-summary'

interface ChatAreaProps {
  chat: ReturnType<typeof useChat>
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
  isLoadingMessages?: boolean
  onCitationClick?: (source: Source) => void
  onSendQuestion?: (q: string) => void
  workspaceSummary: WorkspaceSummary
  isMobile?: boolean
}

const STRATEGIES = [
  { key: 'fast', icon: Zap, label: '快速' },
  { key: 'balanced', icon: Scale, label: '标准' },
  { key: 'high_quality', icon: FileSearch, label: '严谨' },
  { key: 'deep', icon: Search, label: '深度' },
] as const

const DEFAULT_SEARCH_STRATEGY = 'balanced'

function isStrategyKey(value: string): value is typeof STRATEGIES[number]['key'] {
  return STRATEGIES.some(({ key }) => key === value)
}

const STRATEGY_DESC: Record<string, string> = {
  fast: '快速回答：不重排，最快响应。适合简单事实性问题',
  balanced: '标准模式：智能判断是否需要重排。适合大多数情况',
  high_quality: '严谨模式：强制重排+质量检查。质量优先，速度次之',
  deep: '深度检索：扩检索+综合回答。需要全面覆盖时使用',
}

export default function ChatArea({ chat, onOpenSidebar, sidebarOpen, onNavigate, isLoadingMessages, onCitationClick, onSendQuestion, workspaceSummary, isMobile = false }: ChatAreaProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const strategyRefs = useRef<Array<HTMLButtonElement | null>>([])
  const [input, setInput] = useState('')
  const [webSearch, setWebSearch] = useState(() => localStorage.getItem('kb_web_search') === 'true')
  const [strategyDialogOpen, setStrategyDialogOpen] = useState(false)
  const [searchStrategy, setSearchStrategy] = useState(() => {
    const stored = localStorage.getItem('kb_search_strategy')
    return stored && isStrategyKey(stored) ? stored : DEFAULT_SEARCH_STRATEGY
  })

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [chat.messages, chat.streamingNodes, isLoadingMessages])

  const prevLoadingRef = useRef(isLoadingMessages)

  // Persist search preferences across sessions
  useEffect(() => { localStorage.setItem('kb_web_search', String(webSearch)) }, [webSearch])
  useEffect(() => { localStorage.setItem('kb_search_strategy', searchStrategy) }, [searchStrategy])
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

  const focusStrategyAtIndex = (index: number) => {
    const nextIndex = (index + STRATEGIES.length) % STRATEGIES.length
    const nextStrategy = STRATEGIES[nextIndex]
    setSearchStrategy(nextStrategy.key)
    strategyRefs.current[nextIndex]?.focus()
  }

  const handleStrategyKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        event.preventDefault()
        focusStrategyAtIndex(index + 1)
        break
      case 'ArrowLeft':
      case 'ArrowUp':
        event.preventDefault()
        focusStrategyAtIndex(index - 1)
        break
      case 'Home':
        event.preventDefault()
        focusStrategyAtIndex(0)
        break
      case 'End':
        event.preventDefault()
        focusStrategyAtIndex(STRATEGIES.length - 1)
        break
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const focusComposer = () => {
    requestAnimationFrame(() => inputRef.current?.focus())
  }

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px'
    }
  }, [input])

  const isEmpty = chat.messages.length === 0
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
      <header className="flex items-center justify-between border-b border-border px-5 py-3 bg-background/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          {!sidebarOpen && (
            <Button variant="ghost" size="sm" onClick={onOpenSidebar}>
              <PanelRightOpen className="h-4 w-4" />
            </Button>
          )}
          <h1 className={`font-heading text-lg text-foreground tracking-tight ${isMobile ? 'max-w-[11rem] truncate' : ''}`}>{activeTitle}</h1>
        </div>

        <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-0.5 rounded-md border border-border p-0.5">
              <button onClick={() => onNavigate('chat')}
                className="flex items-center gap-1 rounded-sm bg-primary/15 px-2.5 py-1 text-xs font-medium text-primary">
                <Sparkles className="h-3 w-3" />聊天
              </button>
              <button onClick={() => onNavigate('browser')}
                className="flex items-center gap-1 rounded-sm px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
                <BookOpen className="h-3 w-3" />知识库
              </button>
              <button onClick={() => onNavigate('dashboard')}
                className="flex items-center gap-1 rounded-sm px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
                <BarChart3 className="h-3 w-3" />指标
              </button>
            </div>

          <div className="h-4 w-px bg-border hidden md:block" />

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 flex-wrap justify-end">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
                      <Globe className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">搜索</span>
                      <Switch checked={webSearch} onCheckedChange={setWebSearch} />
                    </label>
                  </TooltipTrigger>
                  <TooltipContent>联网搜索开关</TooltipContent>
                </Tooltip>
              </TooltipProvider>

              {isMobile ? (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setStrategyDialogOpen(true)}
                    aria-label="检索与策略"
                    className="gap-1 px-2"
                  >
                    <SlidersHorizontal className="h-3.5 w-3.5" />
                    {STRATEGIES.find(({ key }) => key === searchStrategy)?.label}
                  </Button>
                  <Dialog open={strategyDialogOpen} onOpenChange={setStrategyDialogOpen}>
                    <DialogContent className="max-w-sm">
                      <DialogHeader>
                        <DialogTitle>检索与策略</DialogTitle>
                        <DialogDescription>按问题复杂度选择检索强度，移动端默认收起以保留主任务空间。</DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 pt-2">
                        <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
                          <div>
                            <p className="text-sm font-medium text-foreground">联网搜索</p>
                            <p className="text-xs text-muted-foreground">需要最新信息时开启</p>
                          </div>
                          <Switch checked={webSearch} onCheckedChange={setWebSearch} />
                        </div>
                        <div className="grid gap-2">
                          {STRATEGIES.map(({ key, icon: Icon, label }) => (
                            <button
                              key={key}
                              onClick={() => {
                                setSearchStrategy(key)
                                setStrategyDialogOpen(false)
                              }}
                              className={`rounded-lg border px-3 py-3 text-left transition-colors ${
                                searchStrategy === key
                                  ? 'border-primary/30 bg-primary/10 text-primary'
                                  : 'border-border text-foreground hover:bg-muted/40'
                              }`}
                            >
                              <div className="flex items-center gap-2 text-sm font-medium">
                                <Icon className="h-4 w-4" />
                                {label}
                              </div>
                              <p className="mt-1 text-xs text-muted-foreground">{STRATEGY_DESC[key]}</p>
                            </button>
                          ))}
                        </div>
                      </div>
                    </DialogContent>
                  </Dialog>
                </>
              ) : (
                <div className="flex items-center gap-0.5 rounded-md border border-border p-0.5" role="radiogroup" aria-label="检索策略">
                  {STRATEGIES.map(({ key, icon: Icon, label }, index) => (
                    <TooltipProvider key={key}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            ref={(node) => { strategyRefs.current[index] = node }}
                            role="radio"
                            aria-checked={searchStrategy === key}
                            tabIndex={searchStrategy === key ? 0 : -1}
                            onClick={() => setSearchStrategy(key)}
                            onKeyDown={(event) => handleStrategyKeyDown(event, index)}
                            className={`inline-flex items-center gap-1 rounded-sm px-2 py-1 text-xs font-medium transition-colors ${
                              searchStrategy === key ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground'
                            }`}>
                            <Icon className="h-3 w-3" />
                            {label}
                          </button>
                        </TooltipTrigger>
                        <TooltipContent>{STRATEGY_DESC[key]}</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  ))}
                </div>
              )}
            </div>
          </div>
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
              onPrimaryAction={emptyStateMode === 'onboarding' ? () => onNavigate('browser') : focusComposer}
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
              placeholder="输入你的问题…"
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
