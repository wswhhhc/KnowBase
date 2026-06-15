import { useRef, useEffect, useState } from 'react'
import { Button, ScrollArea, Switch, Dialog, DialogContent, DialogHeader, DialogTitle, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui'
import { useChat, type ChatMessage } from '@/hooks/useChat'
import { evidenceColor, evidenceLabel } from '@/lib/utils'
import DebugPanel from './DebugPanel'
import * as api from '@/lib/api'
import { motion, AnimatePresence } from 'framer-motion'
import {
  PanelRightOpen, Square, Sparkles, Search, Globe, Zap,
  RotateCcw, Download, ThumbsUp, ThumbsDown, BookOpen, BarChart3,
  FileDown, Sun, Moon,
} from 'lucide-react'
import type { ViewType } from '@/App'

interface ChatAreaProps {
  chat: ReturnType<typeof useChat>
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
  theme: { theme: 'dark' | 'light'; toggle: () => void }
}

export default function ChatArea({ chat, onOpenSidebar, sidebarOpen, onNavigate, theme }: ChatAreaProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [input, setInput] = useState('')
  const [webSearch, setWebSearch] = useState(false)
  const [searchStrategy, setSearchStrategy] = useState('balanced')

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [chat.messages, chat.streamingNodes])

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
          {/* Nav pills */}
          <div className="hidden md:flex items-center gap-0.5 rounded-md border border-border p-0.5">
            <button onClick={() => onNavigate('chat')}
              className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-sm bg-primary/15 text-primary">
              <Sparkles className="h-3 w-3" />聊天
            </button>
            <button onClick={() => onNavigate('browser')}
              className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
              <BookOpen className="h-3 w-3" />浏览
            </button>
            <button onClick={() => onNavigate('dashboard')}
              className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
              <BarChart3 className="h-3 w-3" />指标
            </button>
          </div>

          <div className="h-4 w-px bg-border hidden md:block" />

          {/* Theme toggle */}
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
                      {s === 'fast' ? '快' : s === 'balanced' ? '均' : s === 'high_quality' ? '深' : '全'}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>{s === 'fast' ? '快速' : s === 'balanced' ? '均衡' : s === 'high_quality' ? '深度' : '全文'}检索</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ))}
          </div>
        </div>
      </header>

      {/* Messages */}
      <ScrollArea ref={scrollRef} className="flex-1">
        <div className="mx-auto max-w-3xl px-5 py-8">
          {isEmpty ? <EmptyState /> : (
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
                  />
                </motion.div>
              ))}

              {/* Streaming nodes indicator */}
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

function EmptyState() {
  const suggestions = [
    { icon: Search, text: '上传一份文档，然后问一个关于它的问题' },
    { icon: Globe, text: '导入一个公开网页的内容' },
    { icon: Zap, text: '开启联网搜索获取最新信息' },
  ]

  return (
    <div className="flex flex-col items-center justify-center min-h-[55vh] text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      >
        <div className="mb-6">
          <span className="font-heading text-[140px] leading-none gradient-text select-none">K</span>
        </div>
        <h2 className="font-heading text-3xl text-foreground mb-2 tracking-tight">知识库问答助手</h2>
        <p className="text-sm text-muted-foreground mb-10 max-w-md mx-auto">
          上传文档或导入网页，让 AI 基于你的知识库回答问题
        </p>
      </motion.div>

      <div className="grid gap-3 w-full max-w-sm">
        {suggestions.map((s, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 + i * 0.12, duration: 0.4 }}
            className="flex items-center gap-3 rounded-lg border border-border px-4 py-3 text-sm text-muted-foreground hover:border-primary/20 hover:bg-muted/30 transition-colors cursor-default"
          >
            <s.icon className="h-4 w-4 text-primary/60 flex-shrink-0" />
            <span>{s.text}</span>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────
 * MessageBubble
 * ───────────────────────────────────────────── */

function MessageBubble({ message, prevMessage, threadId }: {
  message: ChatMessage
  prevMessage?: ChatMessage
  threadId?: string | null
}) {
  const isUser = message.role === 'user'
  const [sourceOpen, setSourceOpen] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const isFirstAssistant = !isUser && prevMessage?.role === 'user'

  const handleExport = async () => {
    if (!threadId) return
    setExporting(true)
    try {
      const result = await api.exportConversation(threadId)
      const blob = new Blob([result.markdown], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `knowbase-${threadId.slice(0, 8)}.md`
      a.click(); URL.revokeObjectURL(url)
    } catch { /* ignore */ }
    setExporting(false)
  }

  return (
    <div className={isUser ? 'flex justify-end' : 'flex gap-3'}>
      {/* Assistant avatar */}
      {!isUser && (
        <div className="flex-shrink-0 mt-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-primary font-heading text-sm border border-primary/10">
            K
          </div>
        </div>
      )}

      <div className={isUser ? 'max-w-[75%]' : 'flex-1 min-w-0'}>
        {isUser ? (
          <div className="rounded-2xl bg-primary/10 px-4 py-2.5 border border-primary/5">
            <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{message.content}</p>
          </div>
        ) : (
          <>
            {/* Answer */}
            <div className="prose-chat text-sm text-foreground">
              {message.content ? (
                <span>{message.content}</span>
              ) : (
                <span className="text-muted-foreground animate-pulse-soft italic">思考中…</span>
              )}
              {message.streaming && message.content && <span className="cursor-blink" />}
            </div>

            {/* Evidence & actions */}
            {!message.streaming && (
              <>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {/* Evidence badge */}
                  {message.evidence_level && message.outcome_category === 'success' && (
                    <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${
                      message.evidence_level === 'strong' ? 'bg-emerald-500/10 text-emerald-400' :
                      message.evidence_level === 'moderate' ? 'bg-yellow-500/10 text-yellow-400' :
                      message.evidence_level === 'weak' ? 'bg-orange-500/10 text-orange-400' :
                      'bg-red-500/10 text-red-400'
                    }`}>
                      ● {evidenceLabel(message.evidence_level)}
                    </span>
                  )}
                  {message.outcome_category === 'no_docs' && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-red-500/10 text-red-400">● 知识库中未找到</span>
                  )}
                  {message.outcome_category === 'web_empty' && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-red-500/10 text-red-400">● 无法回答</span>
                  )}
                  {message.outcome_category === 'weak_evidence' && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400">● 证据不足</span>
                  )}

                  {/* Feedback */}
                  {(message.sources && message.sources.length > 0) && (
                    <div className="flex items-center gap-0.5 ml-auto">
                      <button onClick={() => setFeedback('helpful')}
                        className={`p-1 rounded transition-colors ${feedback === 'helpful' ? 'text-emerald-400' : 'text-muted-foreground/40 hover:text-emerald-400'}`}>
                        <ThumbsUp className="h-3 w-3" />
                      </button>
                      <button onClick={() => setFeedback('unhelpful')}
                        className={`p-1 rounded transition-colors ${feedback === 'unhelpful' ? 'text-red-400' : 'text-muted-foreground/40 hover:text-red-400'}`}>
                        <ThumbsDown className="h-3 w-3" />
                      </button>
                    </div>
                  )}
                </div>

                {/* Sources toggle */}
                {message.sources && message.sources.length > 0 && (
                  <button
                    onClick={() => setSourceOpen(!sourceOpen)}
                    className="mt-2 inline-flex items-center gap-1 text-[11px] text-primary/70 hover:text-primary transition-colors"
                  >
                    📎 {sourceOpen ? '收起来源' : `${message.sources.length} 个来源`}
                  </button>
                )}

                {/* Source cards */}
                <AnimatePresence>
                  {sourceOpen && message.sources && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="mt-2 space-y-2 overflow-hidden"
                    >
                      {message.sources.map((s, i) => (
                        <div key={i} className="source-card rounded-lg border border-border bg-surface/50 px-3.5 py-2.5">
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-xs font-medium text-foreground/80 truncate">
                              {s.source}{s.chunk_index !== undefined ? ` #${s.chunk_index}` : ''}{s.page ? ` · p.${s.page}` : ''}
                            </span>
                            {s.score !== undefined && <span className="text-[10px] text-muted-foreground flex-shrink-0 font-mono">{s.score.toFixed(3)}</span>}
                          </div>
                          {s.url && <p className="text-[10px] text-primary/50 truncate mt-0.5">{s.url}</p>}
                          <p className="text-xs text-muted-foreground mt-1.5 line-clamp-3 leading-relaxed">{s.content}</p>
                        </div>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Export (first assistant message) */}
                {isFirstAssistant && (
                  <button onClick={handleExport} disabled={exporting}
                    className="mt-2 inline-flex items-center gap-1 text-[10px] text-muted-foreground/50 hover:text-muted-foreground transition-colors">
                    <FileDown className="h-3 w-3" />
                    {exporting ? '导出中…' : '导出对话'}
                  </button>
                )}

                {/* Debug panel */}
                {message.debugData && (
                  <DebugPanel debugData={message.debugData} />
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}
