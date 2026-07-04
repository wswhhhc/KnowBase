import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Button, Input, ConfirmDialog, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui'
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import { formatTime, truncate } from '@/lib/utils'
import * as api from '@/shared/api'
import type { Conversation } from '@/shared/api'

export interface ConversationListProps {
  conversations: Conversation[]
  activeId: string | null
  loading: boolean
  onSwitch: (conversation: Conversation) => void
  onNew: () => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
  onBatchDelete: (ids: string[]) => void
  setActiveId: (id: string | null) => void
  clearMessages: () => void
}

const GROUP_LABELS = ['今天', '昨天', '更早'] as const

function getConversationGroupLabel(updatedAt: string, now = new Date()) {
  const updatedDate = new Date(updatedAt)
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const targetDay = new Date(updatedDate.getFullYear(), updatedDate.getMonth(), updatedDate.getDate())
  const diffDays = Math.round((today.getTime() - targetDay.getTime()) / 86400000)

  if (diffDays <= 0) return '今天'
  if (diffDays === 1) return '昨天'
  return '更早'
}

export default function ConversationList({
  conversations, activeId, loading, onSwitch, onNew, onRename, onDelete, onBatchDelete, setActiveId, clearMessages,
}: ConversationListProps) {
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false)
  const [searchValue, setSearchValue] = useState('')

  const filteredConversations = useMemo(() => {
    const keyword = searchValue.trim().toLowerCase()
    if (!keyword) return conversations
    return conversations.filter((conversation) => {
      const preview = conversation.last_message_preview?.toLowerCase() || ''
      return conversation.title.toLowerCase().includes(keyword) || preview.includes(keyword)
    })
  }, [conversations, searchValue])

  const groupedConversations = useMemo(() => {
    return GROUP_LABELS
      .map((label) => ({
        label,
        conversations: filteredConversations.filter((conversation) => getConversationGroupLabel(conversation.updated_at) === label),
      }))
      .filter((group) => group.conversations.length > 0)
  }, [filteredConversations])

  const visibleConversationIds = filteredConversations.map((conversation) => conversation.id)
  const allVisibleSelected = visibleConversationIds.length > 0
    && visibleConversationIds.every((id) => selectedIds.has(id))

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleRenameConfirm = async (id: string) => {
    if (renameValue.trim()) {
      await onRename(id, renameValue.trim())
    }
    setRenamingId(null)
  }

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return
    const ids = Array.from(selectedIds)
    try {
      await api.deleteConversations(ids)
      if (activeId && selectedIds.has(activeId)) {
        clearMessages()
        setActiveId(null)
      }
      setSelectedIds(new Set())
      onBatchDelete(ids)
      toast.success(`已删除 ${ids.length} 个对话`)
    } catch (err) {
      toast.error('批量删除失败', { description: String(err) })
    }
  }

  const toggleSelectVisible = () => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (allVisibleSelected) {
        visibleConversationIds.forEach((id) => next.delete(id))
      } else {
        visibleConversationIds.forEach((id) => next.add(id))
      }
      return next
    })
  }

  return (
    <div className="space-y-1">
      {/* New + Select All + Batch Delete */}
      <div className="flex items-center gap-1 mb-3">
        <Button variant="secondary" size="sm" className="flex-1 justify-start gap-2" onClick={onNew}>
          <Plus className="h-4 w-4" />新对话
        </Button>
        {conversations.length > 0 && (
          <label className="flex items-center gap-1 cursor-pointer text-xs text-muted-foreground hover:text-foreground transition-colors px-1">
            <input
              type="checkbox"
              checked={allVisibleSelected}
              onChange={toggleSelectVisible}
              className="h-3.5 w-3.5 accent-primary shrink-0 cursor-pointer"
            />
            全选
          </label>
        )}
        {selectedIds.size > 0 && (
          <Button variant="destructive" size="sm" className="gap-1" onClick={() => setBatchDeleteOpen(true)}>
            <Trash2 className="h-3.5 w-3.5" />{selectedIds.size}
          </Button>
        )}
      </div>

      {conversations.length > 0 && (
        <div className="mb-3">
          <Input
            type="search"
            value={searchValue}
            onChange={(event) => setSearchValue(event.target.value)}
            placeholder="搜索标题或摘要"
            aria-label="搜索对话"
            className="h-8 text-xs"
          />
        </div>
      )}

      {/* Conversation Items */}
      {groupedConversations.map((group) => (
        <section key={group.label} className="space-y-1">
          <h3 className="px-2 pt-2 text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground/70">
            {group.label}
          </h3>
          {group.conversations.map((c) => {
            const preview = c.last_message_preview?.trim() || '暂无消息'

            return (
              <div
                key={c.id}
                className={`group flex items-center rounded-md px-3 py-2 text-sm transition-all ${
                  activeId === c.id
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
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleRenameConfirm(c.id)
                        if (e.key === 'Escape') setRenamingId(null)
                      }}
                    />
                    <button onClick={() => handleRenameConfirm(c.id)}>
                      <Check className="h-3 w-3 text-emerald-400" />
                    </button>
                    <button onClick={() => setRenamingId(null)}>
                      <X className="h-3 w-3 text-muted-foreground" />
                    </button>
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
                    <TooltipProvider delayDuration={0}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            type="button"
                            className="truncate flex-1 cursor-pointer text-left"
                            onClick={() => onSwitch(c)}
                          >
                            {truncate(c.title, 24)}
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="right" align="start" className="max-w-xs whitespace-pre-wrap leading-relaxed">
                          {preview}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <span className="text-2xs text-muted-foreground opacity-0 group-hover:opacity-60 transition-opacity flex-shrink-0 mr-1">
                      {formatTime(c.updated_at)}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setRenamingId(c.id)
                        setRenameValue(c.title)
                      }}
                      className="opacity-0 group-hover:opacity-60 text-muted-foreground hover:text-foreground transition-all mr-0.5"
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setDeleteTarget(c.id)
                      }}
                      className="opacity-0 group-hover:opacity-60 text-muted-foreground hover:text-destructive transition-all"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </>
                )}
              </div>
            )
          })}
        </section>
      ))}

      {/* Empty State */}
      {conversations.length === 0 && !loading && (
        <p className="text-xs text-muted-foreground text-center py-6">暂无对话</p>
      )}
      {conversations.length > 0 && filteredConversations.length === 0 && !loading && (
        <p className="text-xs text-muted-foreground text-center py-6">没有匹配的对话</p>
      )}

      {/* Single delete confirm */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
        title="删除对话"
        description="确定要删除此对话吗？此操作不可撤销。"
        onConfirm={async () => {
          if (deleteTarget) await onDelete(deleteTarget)
          setDeleteTarget(null)
        }}
      />

      {/* Batch delete confirm */}
      <ConfirmDialog
        open={batchDeleteOpen}
        onOpenChange={setBatchDeleteOpen}
        title="批量删除"
        description={`确定要删除选中的 ${selectedIds.size} 个对话吗？此操作不可撤销。`}
        onConfirm={handleBatchDelete}
      />
    </div>
  )
}
