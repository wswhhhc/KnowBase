import { useState } from 'react'
import { toast } from 'sonner'
import { Button, Input, Separator } from '@/components/ui'
import { Globe, Trash2, Upload } from 'lucide-react'
import * as api from '@/lib/api'
import type { DocSource } from '@/lib/api'

interface DocumentPanelProps {
  sources: DocSource[]
  onRefresh: () => Promise<boolean>
}

export default function DocumentPanel({ sources, onRefresh }: DocumentPanelProps) {
  const [urlInput, setUrlInput] = useState('')

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await api.uploadDocument(file)
      if (await onRefresh()) {
        toast.success('文档已上传', { description: file.name })
      }
    } catch (err) {
      toast.error('上传失败', { description: String(err) })
    }
    e.target.value = ''
  }

  const handleIngestUrl = async () => {
    if (!urlInput.trim()) return
    try {
      await api.ingestUrl(urlInput.trim())
      setUrlInput('')
      if (await onRefresh()) {
        toast.success('网页已导入')
      }
    } catch (err) {
      toast.error('导入失败', { description: String(err) })
    }
  }

  const handleClearAll = async () => {
    try {
      await api.clearKnowledgeBase()
      if (await onRefresh()) toast.success('知识库已清空')
    } catch (e) {
      toast.error('清空失败', { description: String(e) })
    }
  }

  const handleDeleteSource = async (source: string) => {
    try {
      await api.deleteSource(source)
      if (await onRefresh()) toast.success('已删除来源')
    } catch (e) {
      toast.error('删除失败', { description: String(e) })
    }
  }

  return (
    <div className="space-y-4">
      {/* Upload */}
      <div>
        <label className="block text-xs font-medium text-muted-foreground mb-1.5 tracking-wide uppercase">上传文档</label>
        <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-border px-3 py-2.5 text-sm text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors">
          <Upload className="h-4 w-4" />选择文件
          <input type="file" className="hidden" accept=".txt,.md,.pdf,.docx,.html" onChange={handleUpload} />
        </label>
      </div>

      {/* URL Import */}
      <div>
        <label className="block text-xs font-medium text-muted-foreground mb-1.5 tracking-wide uppercase">导入公开网页</label>
        <div className="flex gap-2">
          <Input
            placeholder="https://…"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleIngestUrl() }}
            className="flex-1"
          />
          <Button size="sm" onClick={handleIngestUrl}>
            <Globe className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <Separator />

      {/* Source List */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-muted-foreground tracking-wide uppercase">文档来源</span>
          {sources.length > 0 && (
            <button onClick={handleClearAll} className="text-[10px] text-destructive/50 hover:text-destructive transition-colors">
              清空
            </button>
          )}
        </div>
        <div className="space-y-0.5">
          {sources.map((s) => (
            <div key={s.source} className="group flex items-center justify-between rounded-md px-2.5 py-1.5 text-sm text-foreground/70 hover:bg-muted transition-colors">
              <span className="truncate flex-1">{s.source}</span>
              <span className="text-[10px] text-muted-foreground mr-2 font-mono">{s.count}</span>
              <button
                onClick={() => handleDeleteSource(s.source)}
                className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-all"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))}
          {sources.length === 0 && (
            <p className="text-xs text-muted-foreground/60 text-center py-6 italic">知识库为空</p>
          )}
        </div>
      </div>
    </div>
  )
}
