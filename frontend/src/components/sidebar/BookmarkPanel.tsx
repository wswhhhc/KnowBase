import { useState, useEffect, useCallback, useRef } from 'react'
import { Input, ScrollArea } from '@/components/ui'
import { BookmarkCheck, Search, Tag, X, Trash2 } from 'lucide-react'
import * as api from '@/lib/api'
import type { Bookmark as BookmarkType } from '@/lib/api'
import type { ViewType } from '@/App'

interface BookmarkPanelProps {
  workspaceId?: string
  onNavigate?: (view: ViewType) => void
  onRefresh?: () => void
}

export default function BookmarkPanel({ workspaceId, onNavigate, onRefresh }: BookmarkPanelProps) {
  const [bookmarks, setBookmarks] = useState<BookmarkType[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editTags, setEditTags] = useState('')
  const [editNote, setEditNote] = useState('')
  const longPressTimerRef = useRef<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getBookmarks(workspaceId, searchQuery || undefined)
      setBookmarks(data)
    } catch { /* ignore */ }
    setLoading(false)
  }, [workspaceId, searchQuery])

  useEffect(() => { load() }, [load])

  const handleUpdateBookmark = async (id: number) => {
    await api.updateBookmark(id, { tags: editTags, note: editNote })
    setEditingId(null)
    onRefresh?.()
    load()
  }

  const handleDelete = async (id: number) => {
    if (editingId === id) setEditingId(null)
    await api.deleteBookmark(id)
    onRefresh?.()
    load()
  }

  const openEditor = (bookmark: BookmarkType) => {
    setEditingId(bookmark.id)
    setEditTags(bookmark.tags)
    setEditNote(bookmark.note || '')
  }

  const clearLongPress = () => {
    if (longPressTimerRef.current !== null) {
      window.clearTimeout(longPressTimerRef.current)
      longPressTimerRef.current = null
    }
  }

  const handleClickChunk = (chunkId: string) => {
    if (onNavigate) {
      // Navigate to browser with highlight
      sessionStorage.setItem('highlightChunkId', chunkId)
      onNavigate('browser')
    }
  }

  const allTags = [...new Set(bookmarks.flatMap((b) => b.tags ? b.tags.split(',').map((t) => t.trim()).filter(Boolean) : []))]
  const displayedBookmarks = selectedTag
    ? bookmarks.filter((bookmark) => bookmark.tags.split(',').map((tag) => tag.trim()).includes(selectedTag))
    : bookmarks

  return (
    <div className="space-y-3">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/50" />
        <Input
          placeholder="搜索书签…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8 text-xs h-8"
        />
      </div>

      {/* Tag filters */}
      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {allTags.map((tag) => (
            <button
              key={tag}
              onClick={() => setSelectedTag((current) => current === tag ? null : tag)}
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-2xs transition-colors ${
                selectedTag === tag
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-primary/10 text-primary/80 hover:bg-primary/15'
              }`}
            >
              <Tag className="h-2.5 w-2.5" />
              {tag}
            </button>
          ))}
        </div>
      )}

      {/* List */}
      <ScrollArea className="max-h-[calc(100vh-300px)]">
        {loading ? (
          <p className="text-xs text-muted-foreground/60 text-center py-6 italic">加载中…</p>
        ) : displayedBookmarks.length === 0 ? (
          <p className="text-xs text-muted-foreground/60 text-center py-6 italic">
            {searchQuery || selectedTag ? '未找到匹配的书签' : '暂无书签，在知识浏览页面或消息气泡中可以收藏'}
          </p>
        ) : (
          <div className="space-y-1">
            {displayedBookmarks.map((bm) => (
              <div key={bm.id} className="group rounded-md border border-border/50 p-2.5 hover:border-border transition-colors">
                <div className="flex items-start justify-between gap-2">
                  <button
                    onClick={() => bm.chunk_id && handleClickChunk(bm.chunk_id)}
                    onContextMenu={(event) => {
                      event.preventDefault()
                      openEditor(bm)
                    }}
                    onTouchStart={() => {
                      clearLongPress()
                      longPressTimerRef.current = window.setTimeout(() => openEditor(bm), 500)
                    }}
                    onTouchEnd={clearLongPress}
                    onTouchCancel={clearLongPress}
                    className="flex-1 text-left"
                  >
                    <p className="text-xs text-foreground/80 leading-relaxed line-clamp-2">
                      {bm.content}
                    </p>
                    {bm.source && (
                      <p className="text-2xs text-muted-foreground/50 mt-1 truncate">{bm.source}</p>
                    )}
                  </button>
                  <button
                    onClick={() => handleDelete(bm.id)}
                    className="opacity-0 group-hover:opacity-100 shrink-0 text-muted-foreground hover:text-destructive transition-all"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>

                {/* Tags */}
                <div className="mt-1.5 flex items-center gap-1 flex-wrap">
                  {editingId === bm.id ? (
                    <div className="w-full space-y-1.5">
                      <Input
                        value={editTags}
                        onChange={(e) => setEditTags(e.target.value)}
                        placeholder="逗号分隔标签"
                        className="w-full text-2xs h-6 px-1.5"
                        autoFocus
                      />
                      <Input
                        value={editNote}
                        onChange={(e) => setEditNote(e.target.value)}
                        placeholder="备注（可选）"
                        className="w-full text-2xs h-6 px-1.5"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleUpdateBookmark(bm.id)
                          if (e.key === 'Escape') setEditingId(null)
                        }}
                      />
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleDelete(bm.id)}
                          aria-label="删除书签"
                          className="text-2xs text-destructive hover:text-destructive/80 mr-auto"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                        <button onClick={() => handleUpdateBookmark(bm.id)} className="text-2xs text-primary hover:text-primary/80">
                          <BookmarkCheck className="h-3 w-3" />
                        </button>
                        <button onClick={() => setEditingId(null)} className="text-2xs text-muted-foreground hover:text-foreground">
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      {bm.tags ? bm.tags.split(',').map((t) => t.trim()).filter(Boolean).map((tag) => (
                        <span key={tag} className="text-2xs text-primary/60 bg-primary/5 rounded px-1.5 py-0.5">{tag}</span>
                      )) : (
                        <span className="text-2xs text-muted-foreground/30 italic">无标签</span>
                      )}
                      <button
                        onClick={() => openEditor(bm)}
                        className="opacity-0 group-hover:opacity-100 text-2xs text-muted-foreground hover:text-foreground ml-auto transition-all"
                      >
                        <Tag className="h-2.5 w-2.5" />
                      </button>
                    </>
                  )}
                </div>
                {editingId !== bm.id && bm.note && (
                  <p className="mt-1 text-2xs text-muted-foreground/60 line-clamp-2">{bm.note}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
