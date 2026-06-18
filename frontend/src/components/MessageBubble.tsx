import { useState } from 'react'
import { Button, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger, Skeleton } from '@/components/ui'
import { evidenceLabel } from '@/lib/utils'
import DebugPanel from './DebugPanel'
import * as api from '@/lib/api'
import type { Source } from '@/lib/api'
import type { ChatMessage } from '@/hooks/useChat'
import { motion, AnimatePresence } from 'framer-motion'
import { ThumbsUp, ThumbsDown, FileDown, Copy, CheckCircle } from 'lucide-react'

function CitationText({ text, sources }: { text: string; sources?: Source[] }) {
  const parts = text.split(/(\[\d+(?:,\d+)*\])/g)
  const sourceMap = new Map(sources?.map((s) => [s.index, s]) ?? [])
  return (
    <span>
      {parts.map((part, i) => {
        const match = part.match(/\[(\d+(?:,\d+)*)\]/)
        if (match) {
          const indices = match[1].split(',').map(Number)
          return (
            <sup
              key={i}
              className="inline-flex items-center justify-center min-w-[1.1em] h-3.5 px-0.5 rounded text-[10px] font-medium bg-primary/15 text-primary cursor-help transition-colors hover:bg-primary/25"
              title={indices.map((idx) => {
                const s = sourceMap.get(idx)
                return s ? `${s.source}${s.chunk_index != null ? ` #${s.chunk_index}` : ''}` : `来源 ${idx}`
              }).join('、')}
            >
              {match[1]}
            </sup>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </span>
  )
}

function CopyButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (e) {
      console.error('复制失败', e)
    }
  }
  return (
    <button onClick={handleCopy}
      className={`p-1 rounded transition-colors ${copied ? 'text-emerald-400' : 'text-muted-foreground/40 hover:text-foreground'}`}
      title={copied ? '已复制' : '复制回答'}>
      {copied ? <CheckCircle className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
    </button>
  )
}

interface MessageBubbleProps {
  message: ChatMessage
  prevMessage?: ChatMessage
  threadId?: string | null
}

export default function MessageBubble({ message, prevMessage, threadId }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const [sourceOpen, setSourceOpen] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const isFirstAssistant = !isUser && prevMessage?.role === 'user'

  const handleExport = async () => {
    const convId = message.convId || threadId
    if (!convId) return
    setExporting(true)
    try {
      const result = await api.exportConversation(convId)
      const blob = new Blob([result.markdown], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `knowbase-${convId.slice(0, 8)}.md`
      a.click(); URL.revokeObjectURL(url)
    } catch (e) { console.error('导出失败', e) }
    setExporting(false)
  }

  return (
    <div className={isUser ? 'flex justify-end' : 'flex gap-3'}>
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
            <div className="prose-chat text-sm text-foreground">
              {message.content ? (
                <CitationText text={message.content} sources={message.sources} />
              ) : (
                <span className="text-muted-foreground animate-pulse-soft italic">思考中…</span>
              )}
              {message.streaming && message.content && <span className="cursor-blink" />}
            </div>

            {!message.streaming && (
              <>
                <div className="mt-3 flex flex-wrap items-center gap-2">
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

                  <CopyButton content={message.content} />

                  {(message.sources && message.sources.length > 0) && (
                    <div className="flex items-center gap-0.5 ml-auto">
                      <button onClick={async () => {
                        setFeedback('helpful')
                        if (message.convId && message.assistantMsgId) {
                          try { await api.updateFeedback(message.convId, message.assistantMsgId, 'helpful') } catch (e) { console.error('反馈提交失败', e) }
                        }
                      }}
                        className={`p-1 rounded transition-colors ${feedback === 'helpful' ? 'text-emerald-400' : 'text-muted-foreground/40 hover:text-emerald-400'}`}>
                        <ThumbsUp className="h-3 w-3" />
                      </button>
                      <button onClick={async () => {
                        setFeedback('unhelpful')
                        if (message.convId && message.assistantMsgId) {
                          try { await api.updateFeedback(message.convId, message.assistantMsgId, 'unhelpful') } catch (e) { console.error('反馈提交失败', e) }
                        }
                      }}
                        className={`p-1 rounded transition-colors ${feedback === 'unhelpful' ? 'text-red-400' : 'text-muted-foreground/40 hover:text-red-400'}`}>
                        <ThumbsDown className="h-3 w-3" />
                      </button>
                    </div>
                  )}
                </div>

                {message.sources && message.sources.length > 0 && (
                  <button
                    onClick={() => setSourceOpen(!sourceOpen)}
                    className="mt-2 inline-flex items-center gap-1 text-[11px] text-primary/70 hover:text-primary transition-colors"
                  >
                    📎 {sourceOpen ? '收起来源' : `${message.sources.length} 个来源`}
                  </button>
                )}

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

                {isFirstAssistant && (
                  <button onClick={handleExport} disabled={exporting}
                    className="mt-2 inline-flex items-center gap-1 text-[10px] text-muted-foreground/50 hover:text-muted-foreground transition-colors">
                    <FileDown className="h-3 w-3" />
                    {exporting ? '导出中…' : '导出对话'}
                  </button>
                )}

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
