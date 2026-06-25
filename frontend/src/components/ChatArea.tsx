import { useRef, useEffect, useState } from 'react'
import { Button, ScrollArea, Switch, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger, Skeleton } from '@/components/ui'
import { useChat } from '@/hooks/useChat'
import type { PinnedSource } from '@/hooks/useChat'
import { useTheme } from '@/hooks/useTheme'
import EmptyState from './EmptyState'
import type { Source } from '@/lib/api'
import MessageBubble from './MessageBubble'
import type { ViewType } from '@/App'
import { motion, AnimatePresence } from 'framer-motion'
import { PanelRightOpen, Square, Sparkles, BookOpen, BarChart3, Sun, Moon, Globe } from 'lucide-react'

interface ChatAreaProps {
  chat: ReturnType<typeof useChat>
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
  isLoadingMessages?: boolean
  onCitationClick?: (source: Source) => void
  onSendQuestion?: (q: string) => void
}

export default function ChatArea({ chat, onOpenSidebar, sidebarOpen, onNavigate, isLoadingMessages, onCitationClick, onSendQuestion }: ChatAreaProps) {
  const theme = useTheme()
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [input, setInput] = useState('')
  const [webSearch, setWebSearch] = useState(false)
  const [searchStrategy, setSearchStrategy] = useState('balanced')

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

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px'
    }
  }, [input])

  const isEmpty = chat.messages.length === 0
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
          <h1 className="font-heading text-lg text-foreground tracking-tight">{activeTitle}</h1>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center gap-0.5 rounded-md border border-border p-0.5">
            <button onClick={() => onNavigate('chat')}
              className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-sm bg-primary/15 text-primary">
              <Sparkles className="h-3 w-3" />聊天
            </button>
            <button onClick={() => onNavigate('browser')}
              className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
              <BookOpen className="h-3 w-3" />工作区
            </button>
            <button onClick={() => onNavigate('dashboard')}
              className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
              <BarChart3 className="h-3 w-3" />指标
            </button>
          </div>

          <div className="h-4 w-px bg-border hidden md:block" />

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

          <div className="flex items-center gap-0.5 rounded-md border border-border p-0.5">
            {(['fast', 'balanced', 'high_quality', 'deep'] as const).map((s) => (
              <TooltipProvider key={s}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button onClick={() => setSearchStrategy(s)}
                      className={`px-2 py-1 text-[10px] font-medium rounded-sm transition-colors ${
                        searchStrategy === s ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground'
                      }`}>
                      {s === 'fast' ? '⚡快速' : s === 'balanced' ? '⚖️标准' : s === 'high_quality' ? '🔬严谨' : '🔍深度'}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>{s === 'fast' ? '快速回答：不重排，最快响应。适合简单事实性问题' : s === 'balanced' ? '标准模式：智能判断是否需要重排。适合大多数情况' : s === 'high_quality' ? '严谨模式：强制重排+质量检查。质量优先，速度次之' : '深度检索：扩检索+综合回答。需要全面覆盖时使用'}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ))}
          </div>
        </div>
      </header>

      {/* Messages */}
      <ScrollArea ref={scrollRef} className="flex-1">
        <div className="mx-auto max-w-3xl px-5 py-8">
          {isLoadingMessages ? <MessageSkeleton /> : isEmpty ? <EmptyState /> : (
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
          <p className="mt-1.5 text-[10px] text-muted-foreground/30 text-center font-mono tracking-wider">
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
