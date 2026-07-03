import { useState } from 'react'
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItemButton,
  DropdownMenuSeparatorLine,
  DropdownMenuTrigger,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui'
import * as api from '@/lib/api'
import DebugPanel from '../DebugPanel'
import CitationText from './CitationText'
import CopyButton from './CopyButton'
import OutcomeGuidancePanel from './OutcomeGuidancePanel'
import SourcePanel from './SourcePanel'
import BookmarkDialog from './Dialogs/BookmarkDialog'
import FeedbackDialog from './Dialogs/FeedbackDialog'
import ExportDialog from './Dialogs/ExportDialog'
import { useChatContext } from './ChatContext'
import {
  formatBooleanEcho,
  formatElapsed,
  getEvidenceBadgeClass,
  getEvidenceLabel,
  getEvidenceTooltip,
  getOutcomeGuidance,
  STRATEGY_LABELS,
} from './guidance'
import type { MessageBubbleProps } from './types'
import {
  AlignLeft,
  Bookmark,
  BookmarkCheck,
  FileDown,
  MessageSquare,
  MoreHorizontal,
  Paperclip,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react'

export default function AssistantMessageBubble({
  message,
  prevMessage,
  threadId,
  workspaceId,
  workspaceSummary,
}: MessageBubbleProps) {
  const { onCitationClick, onSendQuestion, onNavigateBrowser } = useChatContext()
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
  const guidance = getOutcomeGuidance(message, workspaceSummary, questionContext)
  const nodeElapsedMs = Array.isArray(message.debugData?.nodes)
    ? message.debugData.nodes.reduce((total, node) => total + node.elapsed_ms, 0)
    : undefined
  const strategyLabel = message.searchStrategy ? STRATEGY_LABELS[message.searchStrategy] : undefined
  const rerankValue = message.usedRerank ?? message.debugData?.used_rerank
  const webSearchValue = message.webSearchEnabled ?? message.debugData?.used_web_search
  const elapsedLabel = message.elapsedMs != null ? formatElapsed(message.elapsedMs, nodeElapsedMs) : undefined

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
    } catch (error) {
      console.error('收藏失败', error)
    }
  }

  const handleExport = async () => {
    const convId = message.convId || threadId
    if (!convId) return

    setExporting(true)
    setActiveDialog(null)

    try {
      const result = await api.exportConversation(convId, exportFormat, exportSources, exportDebug)
      const blob = exportFormat === 'json'
        ? new Blob([JSON.stringify(result.json, null, 2)], { type: 'application/json' })
        : new Blob([result.markdown || ''], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `knowbase-${convId.slice(0, 8)}.${exportFormat === 'json' ? 'json' : 'md'}`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('导出失败', error)
    }

    setExporting(false)
  }

  const handleHelpfulFeedback = async () => {
    setActiveDialog(null)
    setFeedback('helpful')
    setFeedbackCategory(null)
    setFeedbackDetail('')

    if (!message.convId || !message.assistantMsgId) {
      return
    }

    try {
      await api.updateFeedback(message.convId, message.assistantMsgId, 'helpful')
    } catch (error) {
      console.error('反馈提交失败', error)
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
      } catch (error) {
        console.error('反馈提交失败', error)
      }
    }

    setActiveDialog(null)
  }

  return (
    <div className="flex gap-3">
      <div className="flex-shrink-0 mt-1">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-primary font-heading text-sm border border-primary/10">
          K
        </div>
      </div>

      <div className="flex-1 min-w-0">
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
            <div className="mt-3 flex flex-wrap items-center gap-2 text-2xs text-muted-foreground/80">
              {strategyLabel && (
                <span className="rounded-full border border-border/70 bg-surface/40 px-2.5 py-1">策略：{strategyLabel}</span>
              )}
              {rerankValue != null && (
                <span className="rounded-full border border-border/70 bg-surface/40 px-2.5 py-1">重排：{formatBooleanEcho(rerankValue)}</span>
              )}
              {webSearchValue != null && (
                <span className="rounded-full border border-border/70 bg-surface/40 px-2.5 py-1">联网：{formatBooleanEcho(webSearchValue)}</span>
              )}
              {elapsedLabel && (
                <span className="rounded-full border border-border/70 bg-surface/40 px-2.5 py-1">耗时：{elapsedLabel}</span>
              )}
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              {message.evidence_level && message.outcome_category === 'success' && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className={`inline-flex items-center gap-1 text-2xs font-medium px-2 py-0.5 rounded-full cursor-help ${getEvidenceBadgeClass(message.evidence_level)}`}>
                        ● {getEvidenceLabel(message.evidence_level)}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs text-xs">
                      {getEvidenceTooltip(message)}
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
                <span className={`inline-flex items-center gap-1 text-2xs font-medium px-2 py-0.5 rounded-full ${guidance.badgeClass}`}>
                  ● {guidance.badge}
                </span>
              )}

              <CopyButton content={message.content} />

              {message.sources && message.sources.length > 0 && (
                <div className="flex items-center gap-0.5 ml-auto">
                  <button
                    onClick={() => {
                      if (bookmarked) return
                      setActionsOpen(false)
                      setActiveDialog('bookmark')
                    }}
                    aria-label={bookmarked ? '已收藏' : '收藏回答'}
                    aria-pressed={bookmarked}
                    className={`p-1 rounded transition-colors ${bookmarked ? 'text-amber-400' : 'text-muted-foreground/40 hover:text-amber-400'}`}
                    title={bookmarked ? '已收藏' : '收藏'}
                  >
                    {bookmarked ? <BookmarkCheck className="h-3 w-3" /> : <Bookmark className="h-3 w-3" />}
                  </button>
                  <button
                    onClick={handleHelpfulFeedback}
                    aria-label="有帮助"
                    aria-pressed={feedback === 'helpful'}
                    className={`p-1 rounded transition-colors ${feedback === 'helpful' ? 'text-emerald-400' : 'text-muted-foreground/40 hover:text-emerald-400'}`}
                  >
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

            {guidance && (
              <OutcomeGuidancePanel guidance={guidance} />
            )}

            {message.outcome_category === 'success' && message.content && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {message.sources && message.sources.length > 0 && (
                  <button
                    onClick={() => setSourceOpen((current) => !current)}
                    className="inline-flex items-center gap-1 rounded-full border border-primary/15 bg-primary/5 px-3 py-1 text-2xs font-medium text-primary/80 transition-colors hover:bg-primary/10 hover:text-primary"
                  >
                    <Paperclip className="h-3 w-3" />
                    {sourceOpen ? '收起来源' : `${message.sources.length} 个来源`}
                  </button>
                )}
                <button
                  onClick={() => onSendQuestion?.(`关于上面的回答，请详细解释「${message.content.slice(0, 60)}」`)}
                  className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-2xs font-medium text-muted-foreground transition-colors hover:border-primary/20 hover:text-foreground"
                >
                  <MessageSquare className="h-3 w-3" />
                  继续追问
                </button>
                <DropdownMenu open={actionsOpen} onOpenChange={setActionsOpen}>
                  <DropdownMenuTrigger asChild>
                    <button
                      aria-label="更多操作"
                      aria-haspopup="menu"
                      className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-2xs font-medium text-muted-foreground transition-colors hover:border-primary/20 hover:text-foreground"
                    >
                      <MoreHorizontal className="h-3 w-3" />
                      更多
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start">
                    <DropdownMenuItemButton
                      onSelect={() => {
                        onSendQuestion?.(message.originalQuestion || message.content.slice(0, 60))
                      }}
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      重新回答
                    </DropdownMenuItemButton>
                    <DropdownMenuItemButton
                      onSelect={() => {
                        onSendQuestion?.(`用一句话简洁回答：${message.originalQuestion || message.content.slice(0, 60)}`)
                      }}
                    >
                      <AlignLeft className="h-3.5 w-3.5" />
                      更简洁
                    </DropdownMenuItemButton>
                    <DropdownMenuSeparatorLine />
                    <DropdownMenuItemButton
                      onSelect={(event) => {
                        event.preventDefault()
                        setActionsOpen(false)
                        window.setTimeout(() => setActiveDialog('export'), 0)
                      }}
                    >
                      <FileDown className="h-3.5 w-3.5" />
                      导出对话
                    </DropdownMenuItemButton>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            )}

            <BookmarkDialog
              open={activeDialog === 'bookmark'}
              note={bookmarkNote}
              messageId={message.id}
              onNoteChange={setBookmarkNote}
              onOpenChange={(open) => setActiveDialog(open ? 'bookmark' : null)}
              onConfirm={handleBookmarkConfirm}
            />

            <FeedbackDialog
              open={activeDialog === 'feedback'}
              messageId={message.id}
              feedbackCategory={feedbackCategory}
              feedbackDetail={feedbackDetail}
              onCategoryChange={setFeedbackCategory}
              onDetailChange={setFeedbackDetail}
              onOpenChange={(open) => setActiveDialog(open ? 'feedback' : null)}
              onSubmit={handleUnhelpfulFeedback}
            />

            <ExportDialog
              open={activeDialog === 'export'}
              messageId={message.id}
              exporting={exporting}
              exportFormat={exportFormat}
              exportSources={exportSources}
              exportDebug={exportDebug}
              canExport={Boolean(message.convId || threadId)}
              onOpenChange={(open) => setActiveDialog(open ? 'export' : null)}
              onFormatChange={setExportFormat}
              onSourcesChange={setExportSources}
              onDebugChange={setExportDebug}
              onSubmit={handleExport}
            />

            <SourcePanel
              open={sourceOpen}
              sources={message.sources}
            />

            {message.debugData && <DebugPanel debugData={message.debugData} />}
          </>
        )}
      </div>
    </div>
  )
}
