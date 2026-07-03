import { useState } from 'react'
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItemButton,
  DropdownMenuSeparatorLine,
  DropdownMenuTrigger,
  Input,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui'
import { evidenceLabel } from '@/lib/utils'
import DebugPanel from './DebugPanel'
import * as api from '@/lib/api'
import type { Source } from '@/lib/api'
import type { ChatMessage, PinnedSource } from '@/hooks/useChat'
import { motion, AnimatePresence } from 'framer-motion'
import { ThumbsUp, ThumbsDown, FileDown, Copy, CheckCircle, MessageSquare, ExternalLink, Upload, Bookmark, BookmarkCheck, RefreshCw, AlignLeft, Paperclip, Pin, X, MoreHorizontal } from 'lucide-react'
import type { WorkspaceSummary } from '@/types/workspace-summary'

const FEEDBACK_OPTIONS = [
  { key: 'off_topic', label: '答非所问' },
  { key: 'insufficient_evidence', label: '证据不足' },
  { key: 'too_long', label: '回答太长' },
  { key: 'factual_error', label: '事实错误' },
  { key: 'other', label: '其他' },
] as const

const STRATEGY_LABELS: Record<string, string> = {
  fast: '快速',
  balanced: '标准',
  high_quality: '严谨',
  deep: '深度',
}

function formatElapsed(elapsedMs?: number, nodeElapsedMs?: number) {
  const total = elapsedMs ?? nodeElapsedMs
  if (!total || total <= 0) return '未知'
  if (total < 1000) return `${total}ms`
  return `${(total / 1000).toFixed(1)}s`
}

function formatBooleanEcho(value?: boolean) {
  if (value == null) return '未知'
  return value ? '是' : '否'
}

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
              className={`inline-flex items-center justify-center min-w-[1.1em] h-3.5 px-0.5 rounded text-2xs font-medium bg-primary/15 text-primary transition-colors ${
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

interface OutcomeGuidance {
  badge: string
  badgeClass: string
  title: string
  description: string
  primaryLabel?: string
  secondaryLabel?: string
  followUpPrompt?: string
}

function getOutcomeGuidance(
  message: ChatMessage,
  workspaceSummary: WorkspaceSummary | undefined,
  questionContext: string,
): OutcomeGuidance | null {
  const documentCount = workspaceSummary?.documentCount ?? 0
  const workspaceName = workspaceSummary?.workspaceName || '当前工作区'

  switch (message.outcome_category) {
    case 'no_docs':
      if (documentCount <= 0) {
        return {
          badge: '当前工作区暂无资料',
          badgeClass: 'bg-red-500/10 text-red-400',
          title: `${workspaceName} 里还没有可用资料`,
          description: '先导入一份文档或网页，再回到聊天页提问；导入后也可以先去知识库核对原文。',
          primaryLabel: '去导入资料',
          secondaryLabel: questionContext ? '帮我改写问题' : undefined,
          followUpPrompt: questionContext ? `请帮我把这个问题改写成更具体、便于检索的版本：${questionContext}` : undefined,
        }
      }
      return {
        badge: '当前工作区未命中',
        badgeClass: 'bg-red-500/10 text-red-400',
        title: `${workspaceName} 里没有找到直接相关的内容`,
        description: '先去知识库核对当前来源范围，再决定是补充资料，还是换一种更具体的问法。',
        primaryLabel: '去验证来源',
        secondaryLabel: questionContext ? '换个问法' : undefined,
        followUpPrompt: questionContext ? `请基于当前工作区，帮我把这个问题改写得更具体：${questionContext}` : undefined,
      }
    case 'web_empty':
      return {
        badge: '当前无结果',
        badgeClass: 'bg-red-500/10 text-red-400',
        title: '当前工作区和联网结果都不足以回答',
        description: '建议先核对当前工作区里的来源范围，再补充资料或换一个更明确的问题。',
        primaryLabel: '去验证来源',
        secondaryLabel: questionContext ? '换个问法' : undefined,
        followUpPrompt: questionContext ? `请帮我把这个问题改写得更明确，并指出缺少哪些关键信息：${questionContext}` : undefined,
      }
    case 'weak_evidence':
      return {
        badge: '证据偏弱',
        badgeClass: 'bg-orange-500/10 text-orange-400',
        title: '当前证据不足以支撑可靠回答',
        description: message.evidence_summary
          ? `${message.evidence_summary}。先去核对来源，再决定是否补充资料。`
          : '先去核对当前工作区里的来源片段，再决定是否补充更相关的资料。',
        primaryLabel: '去验证来源',
        secondaryLabel: questionContext ? '帮我缩小问题范围' : undefined,
        followUpPrompt: questionContext ? `请帮我把这个问题缩小范围，并改写成更容易命中文档的问题：${questionContext}` : undefined,
      }
    case 'vague_question':
      return {
        badge: '问题不够具体',
        badgeClass: 'bg-orange-500/10 text-orange-400',
        title: '问题还不够具体',
        description: '补充对象、时间、范围或你想验证的结论后，当前工作区更容易给出可核对的回答。',
        secondaryLabel: questionContext ? '帮我改写问题' : undefined,
        followUpPrompt: questionContext ? `请把这个问题改写得更具体，并保留原意：${questionContext}` : undefined,
      }
    default:
      return null
  }
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
  workspaceId?: string
  workspaceSummary?: WorkspaceSummary
}

export default function MessageBubble({ message, prevMessage, threadId, onCitationClick, onSendQuestion, onNavigateBrowser, pinnedSources, onPinToggle, workspaceId, workspaceSummary }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const [sourceOpen, setSourceOpen] = useState(false)
  const [actionsOpen, setActionsOpen] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [activeDialog, setActiveDialog] = useState<'bookmark' | 'feedback' | 'export' | null>(null)
  const [feedbackCategory, setFeedbackCategory] = useState<string | null>(null)
  const [feedbackDetail, setFeedbackDetail] = useState('')
  const [exporting, setExporting] = useState(false)
  const [exportFormat, setExportFormat] = useState<'markdown' | 'json'>('markdown')
  const [exportSources, setExportSources] = useState(true)
  const [exportDebug, setExportDebug] = useState(false)
  const [bookmarked, setBookmarked] = useState(false)
  const [bookmarkNote, setBookmarkNote] = useState('')
  const questionContext = message.originalQuestion || (prevMessage?.role === 'user' ? prevMessage.content : '')
  const guidance = !isUser ? getOutcomeGuidance(message, workspaceSummary, questionContext) : null
  const bookmarkDialogOpen = activeDialog === 'bookmark'
  const feedbackDialogOpen = activeDialog === 'feedback'
  const exportDialogOpen = activeDialog === 'export'
  const feedbackReasonName = `feedback-reason-${message.id}`
  const nodeElapsedMs = message.debugData?.nodes.reduce((total, node) => total + node.elapsed_ms, 0)
  const strategyLabel = STRATEGY_LABELS[message.searchStrategy || ''] || '未知'
  const rerankLabel = formatBooleanEcho(message.usedRerank ?? message.debugData?.used_rerank)
  const webSearchLabel = formatBooleanEcho(message.webSearchEnabled ?? message.debugData?.used_web_search)
  const elapsedLabel = formatElapsed(message.elapsedMs, nodeElapsedMs)

  const handleBookmarkToggle = () => {
    if (bookmarked) return
    setActionsOpen(false)
    setActiveDialog('bookmark')
  }

  const handleBookmarkConfirm = async () => {
    const convId = message.convId || threadId
    try {
      await api.createBookmark({
        workspace_id: workspaceId || undefined,
        conversation_id: convId || '',
        message_id: message.assistantMsgId || 0,
        content: message.content.slice(0, 500),
        source: message.sources?.[0]?.source || '',
        note: bookmarkNote || undefined,
      })
      setBookmarked(true)
      setBookmarkNote('')
      setActiveDialog(null)
    } catch (e) { console.error('收藏失败', e) }
  }

  const handleExport = async () => {
    const convId = message.convId || threadId
    if (!convId) return
    setExporting(true)
    setActiveDialog(null)
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

  const handleHelpfulFeedback = async () => {
    setActiveDialog(null)
    setFeedback('helpful')
    setFeedbackCategory(null)
    setFeedbackDetail('')
    if (message.convId && message.assistantMsgId) {
      try {
        await api.updateFeedback(message.convId, message.assistantMsgId, 'helpful')
      } catch (e) {
        console.error('反馈提交失败', e)
      }
    }
  }

  const handleUnhelpfulFeedback = async () => {
    if (!feedbackCategory) return
    setFeedback('unhelpful')
    if (message.convId && message.assistantMsgId) {
      try {
        await api.updateFeedback(
          message.convId,
          message.assistantMsgId,
          'unhelpful',
          feedbackCategory,
          feedbackDetail.trim() || undefined,
        )
      } catch (e) {
        console.error('反馈提交失败', e)
      }
    }
    setActiveDialog(null)
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
                <div className="mt-3 flex flex-wrap items-center gap-2 text-2xs text-muted-foreground/80">
                  <span className="rounded-full border border-border/70 bg-surface/40 px-2.5 py-1">策略：{strategyLabel}</span>
                  <span className="rounded-full border border-border/70 bg-surface/40 px-2.5 py-1">重排：{rerankLabel}</span>
                  <span className="rounded-full border border-border/70 bg-surface/40 px-2.5 py-1">联网：{webSearchLabel}</span>
                  <span className="rounded-full border border-border/70 bg-surface/40 px-2.5 py-1">耗时：{elapsedLabel}</span>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {message.evidence_level && message.outcome_category === 'success' && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className={`inline-flex items-center gap-1 text-2xs font-medium px-2 py-0.5 rounded-full cursor-help ${
                            message.evidence_level === 'strong' ? 'bg-emerald-500/20 text-emerald-300' :
                            message.evidence_level === 'moderate' ? 'bg-yellow-500/20 text-yellow-300' :
                            message.evidence_level === 'weak' ? 'bg-orange-500/20 text-orange-300' :
                            'bg-red-500/20 text-red-300'
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
                  {message.sources && message.sources.length > 0 && (
                    <span className="text-2xs text-muted-foreground/70">
                      {message.sources.length} 个来源 · 可在当前工作区验证
                    </span>
                  )}
                  {guidance?.badge && (
                    <span className={`inline-flex items-center gap-1 text-2xs font-medium px-2 py-0.5 rounded-full ${guidance.badgeClass}`}>● {guidance.badge}</span>
                  )}

                  <CopyButton content={message.content} />

                  {(message.sources && message.sources.length > 0) && (
                    <div className="flex items-center gap-0.5 ml-auto">
                      <button onClick={handleBookmarkToggle}
                        aria-label={bookmarked ? '已收藏' : '收藏回答'}
                        aria-pressed={bookmarked}
                        className={`p-1 rounded transition-colors ${bookmarked ? 'text-amber-400' : 'text-muted-foreground/40 hover:text-amber-400'}`}
                        title={bookmarked ? '已收藏' : '收藏'}>
                        {bookmarked ? <BookmarkCheck className="h-3 w-3" /> : <Bookmark className="h-3 w-3" />}
                      </button>
                      <button onClick={handleHelpfulFeedback}
                        aria-label="有帮助"
                        aria-pressed={feedback === 'helpful'}
                        className={`p-1 rounded transition-colors ${feedback === 'helpful' ? 'text-emerald-400' : 'text-muted-foreground/40 hover:text-emerald-400'}`}>
                        <ThumbsUp className="h-3 w-3" />
                      </button>
                      <button
                        onClick={() => {
                          setActionsOpen(false)
                          setActiveDialog('feedback')
                        }}
                        aria-label="无帮助"
                        aria-pressed={feedback === 'unhelpful'}
                        className={`p-1 rounded transition-colors ${feedback === 'unhelpful' ? 'text-red-400' : 'text-muted-foreground/40 hover:text-red-400'}`}
                      >
                        <ThumbsDown className="h-3 w-3" />
                      </button>
                    </div>
                  )}
                </div>

                {/* No-answer guidance panel */}
                {guidance && (
                  <div className="mt-3 rounded-lg border border-border/60 bg-surface/30 px-3.5 py-3">
                    <p className="text-xs font-medium text-foreground/85">{guidance.title}</p>
                    <p className="mt-1 text-xs text-muted-foreground/80 leading-relaxed">{guidance.description}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      {guidance.primaryLabel && onNavigateBrowser && (
                        <button onClick={onNavigateBrowser}
                          className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-2xs font-medium text-primary/80 transition-colors hover:bg-primary/10 hover:text-primary">
                          <Upload className="h-3 w-3" />{guidance.primaryLabel}
                        </button>
                      )}
                      {guidance.followUpPrompt && onSendQuestion && (
                        <button
                          onClick={() => onSendQuestion(guidance.followUpPrompt || '')}
                          className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-2xs font-medium text-muted-foreground transition-colors hover:border-primary/20 hover:text-foreground"
                        >
                          <MessageSquare className="h-3 w-3" />{guidance.secondaryLabel}
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {message.outcome_category === 'success' && !message.streaming && message.content && (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {message.sources && message.sources.length > 0 && (
                      <button
                        onClick={() => setSourceOpen(!sourceOpen)}
                        className="inline-flex items-center gap-1 rounded-full border border-primary/15 bg-primary/5 px-3 py-1 text-2xs font-medium text-primary/80 transition-colors hover:bg-primary/10 hover:text-primary"
                      >
                        <Paperclip className="h-3 w-3" /> {sourceOpen ? '收起来源' : `${message.sources.length} 个来源`}
                      </button>
                    )}
                    <button
                      onClick={() => onSendQuestion?.(`关于上面的回答，请详细解释「${message.content.slice(0, 60)}」`)}
                      className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-2xs font-medium text-muted-foreground transition-colors hover:border-primary/20 hover:text-foreground"
                    >
                      <MessageSquare className="h-3 w-3" />继续追问
                    </button>
                    <DropdownMenu open={actionsOpen} onOpenChange={setActionsOpen}>
                      <DropdownMenuTrigger asChild>
                        <button
                          aria-label="更多操作"
                          aria-haspopup="menu"
                          className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-2xs font-medium text-muted-foreground transition-colors hover:border-primary/20 hover:text-foreground"
                        >
                          <MoreHorizontal className="h-3 w-3" />更多
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start">
                        <DropdownMenuItemButton
                          onSelect={() => {
                            onSendQuestion?.(message.originalQuestion || message.content.slice(0, 60))
                          }}
                        >
                          <RefreshCw className="h-3.5 w-3.5" />重新回答
                        </DropdownMenuItemButton>
                        <DropdownMenuItemButton
                          onSelect={() => {
                            onSendQuestion?.(`用一句话简洁回答：${message.originalQuestion || message.content.slice(0, 60)}`)
                          }}
                        >
                          <AlignLeft className="h-3.5 w-3.5" />更简洁
                        </DropdownMenuItemButton>
                        <DropdownMenuSeparatorLine />
                        <DropdownMenuItemButton
                          onSelect={(event) => {
                            event.preventDefault()
                            setActionsOpen(false)
                            window.setTimeout(() => setActiveDialog('export'), 0)
                          }}
                        >
                          <FileDown className="h-3.5 w-3.5" />导出对话
                        </DropdownMenuItemButton>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                )}

                <Dialog open={bookmarkDialogOpen} onOpenChange={(open) => setActiveDialog(open ? 'bookmark' : null)}>
                  <DialogContent className="max-w-sm">
                    <DialogHeader>
                      <DialogTitle>收藏回答</DialogTitle>
                      <DialogDescription>可以补一条备注，方便之后回看为什么保留这条回答。</DialogDescription>
                    </DialogHeader>
                    <form
                      className="space-y-4 pt-2"
                      onSubmit={async (event) => {
                        event.preventDefault()
                        await handleBookmarkConfirm()
                      }}
                    >
                      <div className="space-y-2">
                        <label htmlFor={`bookmark-note-${message.id}`} className="text-xs font-medium text-foreground/85">
                          备注
                        </label>
                        <Input
                          id={`bookmark-note-${message.id}`}
                          value={bookmarkNote}
                          onChange={(e) => setBookmarkNote(e.target.value)}
                          placeholder="为什么收藏这条回答？"
                          className="text-xs"
                          autoFocus
                        />
                      </div>
                      <div className="flex justify-end gap-2">
                        <Button type="button" variant="outline" onClick={() => setActiveDialog(null)}>
                          取消
                        </Button>
                        <Button type="submit">
                          保存
                        </Button>
                      </div>
                    </form>
                  </DialogContent>
                </Dialog>

                <Dialog open={feedbackDialogOpen} onOpenChange={(open) => setActiveDialog(open ? 'feedback' : null)}>
                  <DialogContent className="max-w-md">
                    <DialogHeader>
                      <DialogTitle>这条回答哪里不理想？</DialogTitle>
                      <DialogDescription>选择一个主要原因，可以补充说明，便于后续改进回答质量。</DialogDescription>
                    </DialogHeader>
                    <form
                      className="space-y-4 pt-2"
                      onSubmit={async (event) => {
                        event.preventDefault()
                        await handleUnhelpfulFeedback()
                      }}
                    >
                      <fieldset className="space-y-2">
                        <legend className="text-xs font-medium text-foreground/85">反馈原因</legend>
                        {FEEDBACK_OPTIONS.map((opt) => (
                          <label
                            key={opt.key}
                            className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors ${
                              feedbackCategory === opt.key
                                ? 'border-primary/30 bg-primary/10 text-primary'
                                : 'border-border text-foreground hover:bg-muted/40'
                            }`}
                          >
                            <input
                              type="radio"
                              name={feedbackReasonName}
                              value={opt.key}
                              checked={feedbackCategory === opt.key}
                              onChange={() => setFeedbackCategory(opt.key)}
                              className="accent-primary"
                            />
                            <span>{opt.label}</span>
                          </label>
                        ))}
                      </fieldset>
                      <div className="space-y-2">
                        <label htmlFor={`feedback-detail-${message.id}`} className="text-xs font-medium text-foreground/85">
                          补充说明
                        </label>
                        <textarea
                          id={`feedback-detail-${message.id}`}
                          value={feedbackDetail}
                          onChange={(e) => setFeedbackDetail(e.target.value)}
                          placeholder="可选，补充一下哪里不准确或不够有用"
                          className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/40 focus-visible:ring-2 focus-visible:ring-ring"
                        />
                      </div>
                      <div className="flex justify-end gap-2">
                        <Button type="button" variant="outline" onClick={() => setActiveDialog(null)}>
                          取消
                        </Button>
                        <Button type="submit" disabled={!feedbackCategory}>
                          提交反馈
                        </Button>
                      </div>
                    </form>
                  </DialogContent>
                </Dialog>

                <Dialog open={exportDialogOpen} onOpenChange={(open) => setActiveDialog(open ? 'export' : null)}>
                  <DialogContent className="max-w-sm">
                    <DialogHeader>
                      <DialogTitle>导出对话</DialogTitle>
                      <DialogDescription>选择导出格式和附带内容，导出后会直接下载到本地。</DialogDescription>
                    </DialogHeader>
                    <form
                      className="space-y-4 pt-2"
                      onSubmit={async (event) => {
                        event.preventDefault()
                        await handleExport()
                      }}
                    >
                      <fieldset className="space-y-2">
                        <legend className="text-xs font-medium text-foreground/85">导出格式</legend>
                        <label className="flex items-center gap-2 text-sm">
                          <input type="radio" name={`export-fmt-${message.id}`} checked={exportFormat === 'markdown'} onChange={() => setExportFormat('markdown')} className="accent-primary" />
                          Markdown
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <input type="radio" name={`export-fmt-${message.id}`} checked={exportFormat === 'json'} onChange={() => setExportFormat('json')} className="accent-primary" />
                          JSON
                        </label>
                      </fieldset>
                      <fieldset className="space-y-2">
                        <legend className="text-xs font-medium text-foreground/85">附带内容</legend>
                        <label className="flex items-center gap-2 text-sm">
                          <input type="checkbox" checked={exportSources} onChange={(e) => setExportSources(e.target.checked)} className="accent-primary" />
                          包含来源
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <input type="checkbox" checked={exportDebug} onChange={(e) => setExportDebug(e.target.checked)} className="accent-primary" />
                          包含调试信息
                        </label>
                      </fieldset>
                      <div className="flex justify-end gap-2">
                        <Button type="button" variant="outline" onClick={() => setActiveDialog(null)}>
                          取消
                        </Button>
                        <Button type="submit" disabled={exporting || !(message.convId || threadId)}>
                          <FileDown className="mr-1 h-3.5 w-3.5" />
                          {exporting ? '导出中…' : '确认导出'}
                        </Button>
                      </div>
                    </form>
                  </DialogContent>
                </Dialog>

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
                              <span className="text-2xs text-muted-foreground/40 font-mono">#{s.index}</span>
                              {s.source}{s.chunk_index !== undefined ? ` #${s.chunk_index}` : ''}{s.page ? ` · p.${s.page}` : ''}
                            </span>
                            {s.score != null && (
                              <span className={`text-2xs flex-shrink-0 font-mono ${
                                s.score < 0.1 ? 'text-muted-foreground/30' : 'text-muted-foreground'
                              }`}>
                                {s.score < 0.1 && '相关性较低 '}{s.score.toFixed(4)}
                              </span>
                            )}
                          </div>
                          {s.url && <p className="text-2xs text-primary/50 truncate mt-0.5">{s.url}</p>}
                          <p className="text-xs text-muted-foreground mt-1.5 line-clamp-3 leading-relaxed">{s.content}</p>
                          <div className="mt-1.5 flex items-center gap-2">
                            {onCitationClick && !isExcluded && (
                              <button
                                onClick={() => onCitationClick?.(s)}
                                className="inline-flex items-center gap-1 text-2xs text-primary/50 hover:text-primary transition-colors"
                              >
                                <ExternalLink className="h-2.5 w-2.5" />在当前工作区查看原文
                              </button>
                            )}
                            {onSendQuestion && !isExcluded && (
                              <button
                                onClick={() => onSendQuestion?.(`关于「${s.source}」中的内容，请详细解释`)}
                                className="inline-flex items-center gap-1 text-2xs text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                              >
                                <MessageSquare className="h-2.5 w-2.5" />追问
                              </button>
                            )}
                            {onPinToggle && (
                              <button
                                onClick={() => onPinToggle?.(s.chunk_id || '', isPinned ? 'unpin' : 'pin')}
                                className={`ml-auto inline-flex items-center gap-1 text-2xs transition-colors ${
                                  isPinned ? 'text-primary/70' : 'text-muted-foreground/30 hover:text-muted-foreground'
                                }`}
                              >
                                <Pin className={`h-3 w-3 ${isPinned ? 'fill-current' : ''}`} /> {isPinned ? '已固定' : '固定'}
                              </button>
                            )}
                            {onPinToggle && (
                              <button
                                onClick={() => onPinToggle?.(s.chunk_id || '', isExcluded ? 'unexclude' : 'exclude')}
                                className={`inline-flex items-center gap-1 text-2xs transition-colors ${
                                  isExcluded ? 'text-destructive/70' : 'text-muted-foreground/30 hover:text-muted-foreground'
                                }`}
                              >
                                <X className="h-3 w-3" /> {isExcluded ? '已排除' : '排除'}
                              </button>
                            )}
                          </div>
                        </div>
                      )})}
                    </motion.div>
                  )}
                </AnimatePresence>

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
