import { useState, useRef } from 'react'
import { toast } from 'sonner'
import { Button, Input, Separator } from '@/components/ui'
import { Globe, Trash2, Upload, Loader2 } from 'lucide-react'
import * as api from '@/lib/api'
import type { DocSource } from '@/lib/api'

interface DocumentPanelProps {
  sources: DocSource[]
  onRefresh: () => Promise<boolean>
  onSendQuestion?: (q: string) => void
}

export default function DocumentPanel({ sources, onRefresh, onSendQuestion }: DocumentPanelProps) {
  const [urlInput, setUrlInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const [suggested, setSuggested] = useState<string[] | null>(null)
  const [versionPrompted, setVersionPrompted] = useState<{ res: any; file: File; sourceName: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>, versionMode?: string) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setSuggested(null)
    setVersionPrompted(null)
    try {
      // Probe first: check if this source already exists (without importing)
      const probe = await api.checkSource(file.name)
      if (probe.exists && !versionMode) {
        // Source exists and user hasn't chosen a mode yet — prompt before importing
        setVersionPrompted({ res: probe, file, sourceName: file.name })
        setUploading(false)
        return
      }
      const res: any = await api.uploadDocument(file, versionMode)
      if (await onRefresh()) {
        const msg = versionMode === 'replace' ? '文档已替换为新版本' :
                    versionMode === 'append' ? '文档已追加新版本' :
                    '文档已上传'
        toast.success(msg, { description: file.name })
        if (res.suggested_questions?.length) {
          setSuggested(res.suggested_questions)
        }
      }
    } catch (err) {
      toast.error('上传失败', { description: String(err) })
    }
    setUploading(false)
  }

  const handleVersionAction = async (action: 'replace' | 'append' | 'skip') => {
    if (!versionPrompted) return
    setVersionPrompted(null)
    if (action === 'skip') {
      toast.info('已跳过，未重复导入')
      return
    }
    // Re-trigger upload with the chosen version mode
    if (fileInputRef.current) {
      const dt = new DataTransfer()
      dt.items.add(versionPrompted.file)
      fileInputRef.current.files = dt.files
      await handleUpload(
        { target: { files: dt.files } } as unknown as React.ChangeEvent<HTMLInputElement>,
        action,
      )
    }
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
        <label className={`flex cursor-pointer items-center gap-2 rounded-md border border-dashed px-3 py-2.5 text-sm transition-colors ${
          uploading ? 'border-primary/40 bg-primary/5 text-primary' : 'border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'
        }`}>
          {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
          {uploading ? '正在处理…' : '选择文件'}
          <input type="file" className="hidden" accept=".txt,.md,.pdf,.docx,.html" onChange={handleUpload} disabled={uploading} />
        </label>
        {uploading && (
          <div className="mt-1.5 h-1 w-full rounded-full bg-muted overflow-hidden">
            <div className="h-full rounded-full bg-primary animate-pulse" style={{ width: '60%' }} />
          </div>
        )}

        {/* Version mode selector */}
        {versionPrompted && (
          <div className="mt-2 rounded-lg border border-primary/15 bg-primary/5 p-3">
            <p className="text-[10px] font-medium text-primary/80 mb-2 tracking-wide">该文档已存在，请选择操作方式</p>
            <div className="space-y-1">
              <button onClick={() => handleVersionAction('replace')}
                className="block w-full text-left text-[11px] px-2 py-1.5 rounded hover:bg-primary/10 text-foreground/80 transition-colors">
                替换为新版本（删除旧内容后重新导入）
              </button>
              <button onClick={() => handleVersionAction('append')}
                className="block w-full text-left text-[11px] px-2 py-1.5 rounded hover:bg-primary/10 text-foreground/80 transition-colors">
                保留两者（新旧版本共存）
              </button>
              <button onClick={() => handleVersionAction('skip')}
                className="block w-full text-left text-[11px] px-2 py-1.5 rounded hover:bg-muted/50 text-muted-foreground transition-colors">
                取消，不重复导入
              </button>
            </div>
          </div>
        )}

        {suggested && suggested.length > 0 && (
          <div className="mt-2 rounded-lg border border-primary/15 bg-primary/5 p-3">
            <p className="text-[10px] font-medium text-primary/80 mb-2 tracking-wide">试试问这些问题</p>
            <div className="space-y-1">
              {suggested.map((q, i) => (
                <button
                  key={i}
                  onClick={() => { onSendQuestion?.(q); setSuggested(null) }}
                  className="block w-full text-left text-[11px] text-foreground/70 hover:text-foreground hover:bg-primary/10 rounded px-2 py-1 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
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
