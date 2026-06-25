import { useState } from 'react'
import { toast } from 'sonner'
import { Button, Input } from '@/components/ui'
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import { formatTime, truncate } from '@/lib/utils'
import * as api from '@/lib/api'
import type { Conversation } from '@/lib/api'

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

export default function ConversationList({
  conversations, activeId, loading, onSwitch, onNew, onRename, onDelete, onBatchDelete, setActiveId, clearMessages,
}: ConversationListProps) {
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

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
              checked={selectedIds.size === conversations.length && conversations.length > 0}
              onChange={() =>
                setSelectedIds(
                  selectedIds.size === conversations.length
                    ? new Set()
                    : new Set(conversations.map((c) => c.id)),
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

      {/* Conversation Items */}
      {conversations.map((c) => (
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
              <span className="truncate flex-1 cursor-pointer" onClick={() => onSwitch(c)}>
                {truncate(c.title, 24)}
              </span>
              <span className="text-[10px] text-muted-foreground opacity-0 group-hover:opacity-60 transition-opacity flex-shrink-0 mr-1">
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
                onClick={async (e) => {
                  e.stopPropagation()
                  await onDelete(c.id)
                }}
                className="opacity-0 group-hover:opacity-60 text-muted-foreground hover:text-destructive transition-all"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </>
          )}
        </div>
      ))}

      {/* Empty State */}
      {conversations.length === 0 && !loading && (
        <p className="text-xs text-muted-foreground text-center py-6">暂无对话</p>
      )}
    </div>
  )
}
