import { useState, useRef } from 'react'
import { toast } from 'sonner'
import { Button, Input, Separator, ConfirmDialog } from '@/components/ui'
import { Globe, Trash2, Upload, Loader2 } from 'lucide-react'
import * as api from '@/lib/api'
import type { DocSource } from '@/lib/api'

interface DocumentPanelProps {
  sources: DocSource[]
  onRefresh: () => Promise<boolean>
  workspaceId?: string
  onSendQuestion?: (q: string) => void
}

type VersionPrompt =
  | { kind: 'file'; file: File; sourceName: string }
  | { kind: 'url'; url: string; sourceName: string }

export default function DocumentPanel({ sources, onRefresh, workspaceId, onSendQuestion }: DocumentPanelProps) {
  const [urlInput, setUrlInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadPhase, setUploadPhase] = useState('')
  const [uploadPercent, setUploadPercent] = useState(0)
  const [suggested, setSuggested] = useState<string[] | null>(null)
  const [versionPrompted, setVersionPrompted] = useState<VersionPrompt | null>(null)
  const [deleteSourceTarget, setDeleteSourceTarget] = useState<string | null>(null)
  const [clearOpen, setClearOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const resetUploadState = () => {
    setUploading(false)
    setUploadPhase('')
    setUploadPercent(0)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const startUpload = async (file: File, versionMode?: string) => {
    setUploading(true)
    setUploadPhase('loading')
    setUploadPercent(0)
    setSuggested(null)
    setVersionPrompted(null)
    try {
      // Probe first: check if this source already exists (without importing)
      const probe = await api.checkSource(file.name, workspaceId)
      if (probe.exists && !versionMode) {
        // Source exists and user hasn't chosen a mode yet — prompt before importing
        setVersionPrompted({ kind: 'file', file, sourceName: file.name })
        resetUploadState()
        return
      }

      api.uploadDocumentStream(file, versionMode, {
        onProgress: (phase, percent) => {
          setUploadPhase(phase)
          setUploadPercent(percent)
        },
        onDone: async (res) => {
          if (res.existing_version && !versionMode) {
            setVersionPrompted({ kind: 'file', file, sourceName: file.name })
            resetUploadState()
            return
          }
          if (await onRefresh()) {
            const msg = versionMode === 'replace' ? '文档已替换为新版本' :
                        versionMode === 'append' ? '文档已追加新版本' :
                        '文档已上传'
            toast.success(msg, { description: file.name })
            if (res.suggested_questions?.length) {
              setSuggested(res.suggested_questions)
            }
          }
          resetUploadState()
        },
        onError: (message) => {
          toast.error('上传失败', { description: message })
          resetUploadState()
        },
      }, workspaceId)
    } catch (err) {
      toast.error('上传失败', { description: String(err) })
      resetUploadState()
    }
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>, versionMode?: string) => {
    const file = e.target.files?.[0]
    if (!file) return
    await startUpload(file, versionMode)
  }

  const handleVersionAction = async (action: 'replace' | 'append' | 'skip') => {
    if (!versionPrompted) return
    if (action === 'skip') {
      setVersionPrompted(null)
      toast.info('已跳过，未重复导入')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }
    if (versionPrompted.kind === 'file') {
      await startUpload(versionPrompted.file, action)
      return
    }
    await startUrlIngest(versionPrompted.url, action)
  }

  const startUrlIngest = async (url: string, versionMode?: string) => {
    setUploading(true)
    setUploadPhase('loading')
    setUploadPercent(0)
    setVersionPrompted(null)
    try {
      const probe = await api.checkSource(url, workspaceId)
      if (probe.exists && !versionMode) {
        setVersionPrompted({ kind: 'url', url, sourceName: url })
        resetUploadState()
        return
      }
    } catch (err) {
      toast.error('导入前检查失败', { description: String(err) })
      resetUploadState()
      return
    }

    api.ingestUrlStream(url, versionMode, {
      onProgress: (phase, percent) => {
        setUploadPhase(phase)
        setUploadPercent(percent)
      },
      onDone: async (res) => {
        if (res.existing_version && !versionMode) {
          setVersionPrompted({ kind: 'url', url, sourceName: url })
          resetUploadState()
          return
        }
        setUrlInput('')
        if (await onRefresh()) {
          const msg = versionMode === 'replace' ? '网页已替换为新版本' :
            versionMode === 'append' ? '网页已追加新版本' :
            '网页已导入'
          toast.success(msg)
        }
        resetUploadState()
      },
      onError: (message) => {
        toast.error('导入失败', { description: message })
        resetUploadState()
      },
    }, workspaceId)
  }

  const handleIngestUrl = async () => {
    const url = urlInput.trim()
    if (!url) return
    await startUrlIngest(url)
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
          {uploading && uploadPhase ? (
            <span>{ { loading: '正在加载文档…', splitting: '正在切分段落…', embedding: '正在向量化…', done: '完成' }[uploadPhase] || '正在处理…' }</span>
          ) : '选择文件'}
          <input ref={fileInputRef} type="file" className="hidden" accept=".txt,.md,.pdf,.docx,.html" onChange={handleUpload} disabled={uploading} />
        </label>
        {uploading && (
          <div className="mt-1.5 space-y-1">
            <div className="h-1 w-full rounded-full bg-muted overflow-hidden">
              <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${uploadPercent}%` }} />
            </div>
            <p className="text-2xs text-muted-foreground/60 text-right">{uploadPercent}%</p>
          </div>
        )}

        {/* Version mode selector */}
        {versionPrompted && (
          <div className="mt-2 rounded-lg border border-primary/15 bg-primary/5 p-3">
            <p className="text-2xs font-medium text-primary/80 mb-2 tracking-wide">该来源已存在，请选择操作方式</p>
            <div className="space-y-1">
              <button onClick={() => handleVersionAction('replace')}
                className="block w-full text-left text-xs px-2 py-1.5 rounded hover:bg-primary/10 text-foreground/80 transition-colors">
                替换为新版本（删除旧内容后重新导入）
              </button>
              <button onClick={() => handleVersionAction('append')}
                className="block w-full text-left text-xs px-2 py-1.5 rounded hover:bg-primary/10 text-foreground/80 transition-colors">
                保留两者（新旧版本共存）
              </button>
              <button onClick={() => handleVersionAction('skip')}
                className="block w-full text-left text-xs px-2 py-1.5 rounded hover:bg-muted/50 text-muted-foreground transition-colors">
                取消，不重复导入
              </button>
            </div>
          </div>
        )}

        {suggested && suggested.length > 0 && (
          <div className="mt-2 rounded-lg border border-primary/15 bg-primary/5 p-3">
            <p className="text-2xs font-medium text-primary/80 mb-2 tracking-wide">试试问这些问题</p>
            <div className="space-y-1">
              {suggested.map((q, i) => (
                <button
                  key={i}
                  onClick={() => { onSendQuestion?.(q); setSuggested(null) }}
                  className="block w-full text-left text-xs text-foreground/70 hover:text-foreground hover:bg-primary/10 rounded px-2 py-1 transition-colors"
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
          <span className="text-xs font-medium text-muted-foreground tracking-wide uppercase">引用文档</span>
          {sources.length > 0 && (
            <button onClick={() => setClearOpen(true)} className="text-2xs text-destructive/50 hover:text-destructive transition-colors">
              清空
            </button>
          )}
        </div>
        <div className="space-y-0.5">
          {sources.map((s) => (
            <div key={s.source} className="group flex items-center justify-between rounded-md px-2.5 py-1.5 text-sm text-foreground/70 hover:bg-muted transition-colors">
              <span className="truncate flex-1">{s.source}</span>
              <span className="text-2xs text-muted-foreground mr-2 font-mono">{s.count} 段落</span>
              <button
                onClick={() => setDeleteSourceTarget(s.source)}
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

      {/* Delete source confirm */}
      <ConfirmDialog
        open={!!deleteSourceTarget}
        onOpenChange={(open) => { if (!open) setDeleteSourceTarget(null) }}
        title="删除引用文档"
        description={`确定要删除"${deleteSourceTarget ?? ''}"吗？关联的段落将被移除。`}
        onConfirm={async () => {
          if (!deleteSourceTarget) return
          try {
            await api.deleteSource(deleteSourceTarget, workspaceId)
            if (await onRefresh()) toast.success('已删除引用文档')
          } catch (e) {
            toast.error('删除失败', { description: String(e) })
          }
        }}
      />

      {/* Clear KB confirm */}
      <ConfirmDialog
        open={clearOpen}
        onOpenChange={setClearOpen}
        title="清空知识库"
        description="确定要清空整个知识库中的所有文档和段落吗？此操作不可撤销。"
        onConfirm={async () => {
          try {
            await api.clearKnowledgeBase(workspaceId)
            if (await onRefresh()) toast.success('知识库已清空')
          } catch (e) {
            toast.error('清空失败', { description: String(e) })
          }
        }}
      />
    </div>
  )
}
