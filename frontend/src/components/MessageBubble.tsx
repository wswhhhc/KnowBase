import { useState } from 'react'
import { Button, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui'
import { evidenceLabel } from '@/lib/utils'
import DebugPanel from './DebugPanel'
import * as api from '@/lib/api'
import type { Source } from '@/lib/api'
import type { ChatMessage, PinnedSource } from '@/hooks/useChat'
import { motion, AnimatePresence } from 'framer-motion'
import { ThumbsUp, ThumbsDown, FileDown, Copy, CheckCircle, MessageSquare, ExternalLink, Upload, Bookmark, BookmarkCheck } from 'lucide-react'

interface CitationTextProps {
  text: string
  sources?: Source[]
  onCitationClick?: (source: Source) => void
}

function CitationText({ text, sources, onCitationClick }: CitationTextProps) {
  const parts = text.split(/(\[\d+(?:,\d+)*\])/g)
  const sourceMap = new Map(sources?.map((s) => [s.index, s]) ?? [])
  return (
    <span>
      {parts.map((part, i) => {
        const match = part.match(/\[(\d+(?:,\d+)*)\]/)
        if (match) {
          const indices = match[1].split(',').map(Number)
          const firstIdx = indices[0]
          const firstSrc = sourceMap.get(firstIdx)
          return (
            <sup
              key={i}
              onClick={() => firstSrc && onCitationClick?.(firstSrc)}
              className={`inline-flex items-center justify-center min-w-[1.1em] h-3.5 px-0.5 rounded text-[10px] font-medium bg-primary/15 text-primary transition-colors ${
                onCitationClick ? 'cursor-pointer hover:bg-primary/30' : 'cursor-help hover:bg-primary/25'
              }`}
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
  onCitationClick?: (source: Source) => void
  onSendQuestion?: (q: string) => void
  onNavigateBrowser?: () => void
  pinnedSources?: PinnedSource[]
  onPinToggle?: (chunkId: string, action: 'pin' | 'unpin' | 'exclude' | 'unexclude') => void
}

export default function MessageBubble({ message, prevMessage, threadId, onCitationClick, onSendQuestion, onNavigateBrowser, pinnedSources, onPinToggle }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const [sourceOpen, setSourceOpen] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [feedbackCategory, setFeedbackCategory] = useState<string | null>(null)
  const [feedbackDetail, setFeedbackDetail] = useState('')
  const [exporting, setExporting] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const [exportFormat, setExportFormat] = useState<'markdown' | 'json'>('markdown')
  const [exportSources, setExportSources] = useState(true)
  const [exportDebug, setExportDebug] = useState(false)
  const [bookmarked, setBookmarked] = useState(false)
  const [bookmarkNote, setBookmarkNote] = useState('')
  const [bookmarkOpen, setBookmarkOpen] = useState(false)

  const isFirstAssistant = !isUser && prevMessage?.role === 'user'

  const handleBookmarkToggle = () => {
    if (bookmarked) return
    setBookmarkOpen(true)
  }

  const handleBookmarkConfirm = async () => {
    const convId = message.convId || threadId
    try {
      await api.createBookmark({
        conversation_id: convId || '',
        message_id: message.assistantMsgId || 0,
        content: message.content.slice(0, 500),
        source: message.sources?.[0]?.source || '',
        note: bookmarkNote || undefined,
      })
      setBookmarked(true)
      setBookmarkOpen(false)
    } catch (e) { console.error('收藏失败', e) }
  }

  const handleExport = async () => {
    const convId = message.convId || threadId
    if (!convId) return
    setExporting(true)
    setExportOpen(false)
    try {
      const result = await api.exportConversation(convId, exportFormat, exportSources, exportDebug)
      if (exportFormat === 'json') {
        const blob = new Blob([JSON.stringify(result.json, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `knowbase-${convId.slice(0, 8)}.json`
        a.click(); URL.revokeObjectURL(url)
      } else {
        const blob = new Blob([result.markdown || ''], { type: 'text/markdown' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `knowbase-${convId.slice(0, 8)}.md`
        a.click(); URL.revokeObjectURL(url)
      }
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
                <CitationText text={message.content} sources={message.sources} onCitationClick={onCitationClick} />
              ) : (
                <span className="text-muted-foreground animate-pulse-soft italic">思考中…</span>
              )}
              {message.streaming && message.content && <span className="cursor-blink" />}
            </div>

            {!message.streaming && (
              <>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {message.evidence_level && message.outcome_category === 'success' && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full cursor-help ${
                            message.evidence_level === 'strong' ? 'bg-emerald-500/10 text-emerald-400' :
                            message.evidence_level === 'moderate' ? 'bg-yellow-500/10 text-yellow-400' :
                            message.evidence_level === 'weak' ? 'bg-orange-500/10 text-orange-400' :
                            'bg-red-500/10 text-red-400'
                          }`}>
                            ● {evidenceLabel(message.evidence_level)}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="max-w-xs text-xs">
                          {message.evidence_summary || (
                            message.evidence_level === 'strong' ? '多个相关文档片段支持该回答，可信度较高' :
                            message.evidence_level === 'moderate' ? '少量相关文档片段支持该回答' :
                            message.evidence_level === 'weak' ? '仅少数文档片段触及问题，证据不够充分' :
                            '没有找到直接相关的文档证据'
                          )}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
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
                      <button onClick={handleBookmarkToggle}
                        className={`p-1 rounded transition-colors ${bookmarked ? 'text-amber-400' : 'text-muted-foreground/40 hover:text-amber-400'}`}
                        title={bookmarked ? '已收藏' : '收藏'}>
                        {bookmarked ? <BookmarkCheck className="h-3 w-3" /> : <Bookmark className="h-3 w-3" />}
                      </button>
                      {bookmarkOpen && (
                        <div className="absolute top-full right-0 mt-1 w-56 rounded-lg border border-border bg-surface shadow-xl p-2.5 z-50">
                          <p className="text-[10px] font-medium text-muted-foreground mb-2">添加备注（可选）</p>
                          <input
                            value={bookmarkNote}
                            onChange={(e) => setBookmarkNote(e.target.value)}
                            placeholder="为什么收藏这条回答？"
                            className="w-full text-[10px] px-2 py-1 rounded border border-border bg-background outline-none placeholder:text-muted-foreground/30 mb-2"
                            autoFocus
                          />
                          <div className="flex gap-2">
                            <button onClick={() => setBookmarkOpen(false)}
                              className="flex-1 text-[10px] py-1 rounded text-muted-foreground hover:text-foreground bg-muted/50 transition-colors">取消</button>
                            <button onClick={handleBookmarkConfirm}
                              className="flex-1 text-[10px] py-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors">保存</button>
                          </div>
                        </div>
                      )}
                      <button onClick={async () => {
                        setFeedback('helpful')
                        if (message.convId && message.assistantMsgId) {
                          try { await api.updateFeedback(message.convId, message.assistantMsgId, 'helpful') } catch (e) { console.error('反馈提交失败', e) }
                        }
                      }}
                        className={`p-1 rounded transition-colors ${feedback === 'helpful' ? 'text-emerald-400' : 'text-muted-foreground/40 hover:text-emerald-400'}`}>
                        <ThumbsUp className="h-3 w-3" />
                      </button>
                      <div className="relative">
                        <button onClick={() => setFeedbackOpen(!feedbackOpen)}
                          className={`p-1 rounded transition-colors ${feedback === 'unhelpful' ? 'text-red-400' : 'text-muted-foreground/40 hover:text-red-400'}`}>
                          <ThumbsDown className="h-3 w-3" />
                        </button>
                        {feedbackOpen && (
                          <div className="absolute bottom-full right-0 mb-2 w-56 rounded-lg border border-border bg-surface shadow-xl p-2.5 z-50">
                            <p className="text-[10px] font-medium text-muted-foreground mb-2">请选择原因</p>
                            <div className="space-y-1">
                              {[
                                { key: 'off_topic', label: '答非所问' },
                                { key: 'insufficient_evidence', label: '证据不足' },
                                { key: 'too_long', label: '回答太长' },
                                { key: 'factual_error', label: '事实错误' },
                                { key: 'other', label: '其他' },
                              ].map((opt) => (
                                <button
                                  key={opt.key}
                                  onClick={async () => {
                                    setFeedbackCategory(opt.key)
                                    setFeedback('unhelpful')
                                    if (message.convId && message.assistantMsgId) {
                                      try {
                                        await api.updateFeedback(message.convId, message.assistantMsgId, 'unhelpful', opt.key, feedbackDetail || undefined)
                                      } catch (e) { console.error('反馈提交失败', e) }
                                    }
                                    setFeedbackOpen(false)
                                  }}
                                  className={`block w-full text-left text-[11px] px-2 py-1.5 rounded transition-colors ${
                                    feedbackCategory === opt.key ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                                  }`}
                                >
                                  {opt.label}
                                </button>
                              ))}
                            </div>
                            <input
                              value={feedbackDetail}
                              onChange={(e) => setFeedbackDetail(e.target.value)}
                              placeholder="补充说明（可选）"
                              className="mt-2 w-full text-[10px] px-2 py-1 rounded border border-border bg-background outline-none placeholder:text-muted-foreground/30"
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* No-answer guidance panel */}
                {(message.outcome_category === 'no_docs' || message.outcome_category === 'web_empty' || message.outcome_category === 'weak_evidence' || message.outcome_category === 'vague_question') && (
                  <div className="mt-3 rounded-lg border border-border/60 bg-surface/30 px-3.5 py-3">
                    <p className="text-[11px] text-muted-foreground/80 leading-relaxed">
                      {message.outcome_category === 'no_docs' && '知识库中没有找到相关内容。你可以上传相关文档后再问一次。'}
                      {message.outcome_category === 'web_empty' && '联网搜索也没有找到相关信息。建议换一种问法或上传相关资料。'}
                      {message.outcome_category === 'weak_evidence' && `检索到的信息不足以支撑可靠回答。尝试更具体的问题或上传更详细的资料。${message.evidence_summary ? `（${message.evidence_summary}）` : ''}`}
                      {message.outcome_category === 'vague_question' && '问题比较模糊，建议补充更多细节。'}
                    </p>
                    {onNavigateBrowser && (message.outcome_category === 'no_docs' || message.outcome_category === 'weak_evidence') && (
                      <button onClick={onNavigateBrowser}
                        className="mt-2 inline-flex items-center gap-1 text-[10px] font-medium text-primary/70 hover:text-primary transition-colors">
                        <Upload className="h-3 w-3" />上传文档
                      </button>
                    )}
                  </div>
                )}

                {/* Reroll / concise / follow-up */}
                {message.outcome_category === 'success' && !message.streaming && message.content && (
                  <div className="mt-2 flex items-center gap-2">
                    <button
                      onClick={() => onSendQuestion?.(message.originalQuestion || message.content.slice(0, 60))}
                      className="inline-flex items-center gap-1 text-[10px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                    >
                      🔄 重新回答
                    </button>
                    <button
                      onClick={() => onSendQuestion?.(`用一句话简洁回答：${message.originalQuestion || message.content.slice(0, 60)}`)}
                      className="inline-flex items-center gap-1 text-[10px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                    >
                      📝 更简洁
                    </button>
                    <button
                      onClick={() => onSendQuestion?.(`关于上面的回答，请详细解释「${message.content.slice(0, 60)}」`)}
                      className="inline-flex items-center gap-1 text-[10px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                    >
                      <MessageSquare className="h-3 w-3" />继续追问
                    </button>
                  </div>
                )}

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
                      {[...message.sources].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).map((s, i) => {
                        const ps = pinnedSources?.find((p) => p.chunk_id === s.chunk_id)
                        const isExcluded = ps?.excluded
                        const isPinned = ps?.pinned
                        return (
                        <div key={i} className={`source-card rounded-lg border px-3.5 py-2.5 transition-all ${
                          isExcluded ? 'border-destructive/20 bg-destructive/5 opacity-50' : isPinned ? 'border-primary/30 bg-primary/5' : 'border-border bg-surface/50'
                        }`}>
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-xs font-medium text-foreground/80 truncate flex items-center gap-1">
                              <span className="text-[9px] text-muted-foreground/40 font-mono">#{s.index}</span>
                              {s.source}{s.chunk_index !== undefined ? ` #${s.chunk_index}` : ''}{s.page ? ` · p.${s.page}` : ''}
                            </span>
                            {s.score != null && (
                              <span className={`text-[10px] flex-shrink-0 font-mono ${
                                s.score < 0.1 ? 'text-muted-foreground/30' : 'text-muted-foreground'
                              }`}>
                                {s.score < 0.1 && '相关性较低 '}{s.score.toFixed(4)}
                              </span>
                            )}
                          </div>
                          {s.url && <p className="text-[10px] text-primary/50 truncate mt-0.5">{s.url}</p>}
                          <p className="text-xs text-muted-foreground mt-1.5 line-clamp-3 leading-relaxed">{s.content}</p>
                          <div className="mt-1.5 flex items-center gap-2">
                            {onCitationClick && !isExcluded && (
                              <button
                                onClick={() => onCitationClick?.(s)}
                                className="inline-flex items-center gap-1 text-[9px] text-primary/50 hover:text-primary transition-colors"
                              >
                                <ExternalLink className="h-2.5 w-2.5" />查看原文
                              </button>
                            )}
                            {onSendQuestion && !isExcluded && (
                              <button
                                onClick={() => onSendQuestion?.(`关于「${s.source}」中的内容，请详细解释`)}
                                className="inline-flex items-center gap-1 text-[9px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                              >
                                <MessageSquare className="h-2.5 w-2.5" />追问
                              </button>
                            )}
                            {onPinToggle && (
                              <button
                                onClick={() => onPinToggle?.(s.chunk_id || '', isPinned ? 'unpin' : 'pin')}
                                className={`ml-auto inline-flex items-center gap-1 text-[9px] transition-colors ${
                                  isPinned ? 'text-primary/70' : 'text-muted-foreground/30 hover:text-muted-foreground'
                                }`}
                              >
                                📌 {isPinned ? '已固定' : '固定'}
                              </button>
                            )}
                            {onPinToggle && (
                              <button
                                onClick={() => onPinToggle?.(s.chunk_id || '', isExcluded ? 'unexclude' : 'exclude')}
                                className={`inline-flex items-center gap-1 text-[9px] transition-colors ${
                                  isExcluded ? 'text-destructive/70' : 'text-muted-foreground/30 hover:text-muted-foreground'
                                }`}
                              >
                                ✕ {isExcluded ? '已排除' : '排除'}
                              </button>
                            )}
                          </div>
                        </div>
                      )})}
                    </motion.div>
                  )}
                </AnimatePresence>

                {isFirstAssistant && (
                  <div className="relative mt-2">
                    <button onClick={() => setExportOpen(!exportOpen)} disabled={exporting}
                      className="inline-flex items-center gap-1 text-[10px] text-muted-foreground/50 hover:text-muted-foreground transition-colors">
                      <FileDown className="h-3 w-3" />
                      {exporting ? '导出中…' : '导出对话'}
                    </button>
                    {exportOpen && (
                      <div className="mt-1.5 rounded-lg border border-border bg-surface shadow-lg p-2.5 w-56">
                        <div className="space-y-1.5">
                          <label className="flex items-center gap-2 text-[11px]">
                            <input type="radio" name="export-fmt" checked={exportFormat === 'markdown'} onChange={() => setExportFormat('markdown')} className="accent-primary" />
                            Markdown
                          </label>
                          <label className="flex items-center gap-2 text-[11px]">
                            <input type="radio" name="export-fmt" checked={exportFormat === 'json'} onChange={() => setExportFormat('json')} className="accent-primary" />
                            JSON（含结构化数据）
                          </label>
                          <div className="border-t border-border my-1" />
                          <label className="flex items-center gap-2 text-[11px]">
                            <input type="checkbox" checked={exportSources} onChange={(e) => setExportSources(e.target.checked)} className="accent-primary" />
                            包含来源
                          </label>
                          <label className="flex items-center gap-2 text-[11px]">
                            <input type="checkbox" checked={exportDebug} onChange={(e) => setExportDebug(e.target.checked)} className="accent-primary" />
                            包含调试信息
                          </label>
                          <button onClick={handleExport}
                            className="w-full mt-1 rounded bg-primary/10 text-primary text-[10px] font-medium py-1.5 hover:bg-primary/20 transition-colors">
                            确认导出
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
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
