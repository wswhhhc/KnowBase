import { useState, useRef } from 'react'
import { toast } from 'sonner'
import { Button, Input, Separator, ConfirmDialog } from '@/components/ui'
import { Globe, Trash2, Upload, Loader2 } from 'lucide-react'
import * as api from '@/shared/api'
import type { DocSource } from '@/shared/api'

interface DocumentPanelProps {
  sources: DocSource[]
  onRefresh: () => Promise<boolean>
  workspaceId?: string
  workspaceName?: string
  onSendQuestion?: (q: string) => void
  onOpenKnowledgeBase?: () => void
  canManageKnowledgeBase?: boolean
}

type VersionPrompt =
  | { kind: 'file'; file: File; sourceName: string }
  | { kind: 'url'; url: string; sourceName: string }

interface PostImportGuide {
  title: string
  description: string
  suggestedQuestions: string[]
}

const PHASE_COPY: Record<string, { title: string; detail: string }> = {
  loading: {
    title: '正在读取资料并检查来源…',
    detail: '先确认文件或网页是否可解析，以及当前工作区里是否已经存在同名来源。',
  },
  splitting: {
    title: '正在切分为可检索片段…',
    detail: '把内容拆成更适合检索和引用的段落片段。',
  },
  embedding: {
    title: '正在写入向量索引…',
    detail: '生成检索向量并准备上传完成后的推荐问题。',
  },
  done: {
    title: '资料已处理完成',
    detail: '现在可以直接提问，或先去知识库核对原文来源。',
  },
}

export default function DocumentPanel({
  sources,
  onRefresh,
  workspaceId,
  workspaceName = '默认工作区',
  onSendQuestion,
  onOpenKnowledgeBase,
  canManageKnowledgeBase = true,
}: DocumentPanelProps) {
  const [urlInput, setUrlInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadPhase, setUploadPhase] = useState('')
  const [uploadPercent, setUploadPercent] = useState(0)
  const [postImportGuide, setPostImportGuide] = useState<PostImportGuide | null>(null)
  const [versionPrompted, setVersionPrompted] = useState<VersionPrompt | null>(null)
  const [deleteSourceTarget, setDeleteSourceTarget] = useState<string | null>(null)
  const [clearOpen, setClearOpen] = useState(false)
  const [demoImporting, setDemoImporting] = useState(false)
  const [isDragActive, setIsDragActive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dragDepthRef = useRef(0)

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
    setPostImportGuide(null)
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
            setPostImportGuide({
              title: `资料已进入“${workspaceName}”`,
              description: `当前来源是“${file.name}”。可以直接发起第一个问题，或先去知识库核对原文。`,
              suggestedQuestions: res.suggested_questions ?? [],
            })
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
          setPostImportGuide({
            title: `资料已进入“${workspaceName}”`,
            description: `当前来源是“${url}”。你可以先去知识库核对原文，或直接基于这份资料发问。`,
            suggestedQuestions: res.suggested_questions ?? [],
          })
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

  const startDemoImport = async () => {
    setDemoImporting(true)
    setPostImportGuide(null)
    try {
      const res = await api.importDemoDocuments(workspaceId)
      const importedSources = res.imported_sources ?? []
      if (await onRefresh()) {
        toast.success(res.message, { description: `${importedSources.length} 份示例资料` })
        setPostImportGuide({
          title: `示例资料已进入“${workspaceName}”`,
          description: `已导入 ${importedSources.join('、')}。你现在可以直接提问，或先去知识库确认来源。`,
          suggestedQuestions: res.suggested_questions ?? [],
        })
      }
    } catch (err) {
      toast.error('导入示例资料失败', { description: String(err) })
    } finally {
      setDemoImporting(false)
    }
  }

  const startDroppedUpload = async (file: File | null | undefined) => {
    if (!file || uploading) return
    await startUpload(file)
  }

  const progressCopy = PHASE_COPY[uploadPhase] ?? {
    title: '正在处理资料…',
    detail: '请稍候，系统正在准备可检索内容。',
  }

  return (
    <div className="space-y-4">
      {canManageKnowledgeBase ? (
        <>
          <div className="rounded-xl border border-border/70 bg-surface/35 p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-foreground">导入示例资料</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  一键导入 3 份演示资料到“{workspaceName}”，用于快速体验问答、知识库核对与工作区作用域。
                </p>
              </div>
              <Button size="sm" onClick={startDemoImport} disabled={demoImporting || uploading} className="shrink-0">
                {demoImporting ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
                导入示例资料
              </Button>
            </div>
          </div>

          {/* Upload */}
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5 tracking-wide uppercase">上传文档</label>
            <label
              onDragEnter={(event) => {
                event.preventDefault()
                dragDepthRef.current += 1
                setIsDragActive(true)
              }}
              onDragOver={(event) => {
                event.preventDefault()
                if (!uploading) {
                  event.dataTransfer.dropEffect = 'copy'
                }
              }}
              onDragLeave={(event) => {
                event.preventDefault()
                dragDepthRef.current = Math.max(0, dragDepthRef.current - 1)
                if (dragDepthRef.current === 0) {
                  setIsDragActive(false)
                }
              }}
              onDrop={(event) => {
                event.preventDefault()
                dragDepthRef.current = 0
                setIsDragActive(false)
                const file = event.dataTransfer.files?.[0]
                void startDroppedUpload(file)
              }}
              className={`block cursor-pointer rounded-xl border border-dashed px-3 py-3 text-sm transition-colors ${
              uploading
                ? 'border-primary/40 bg-primary/5 text-primary'
                : isDragActive
                  ? 'border-primary/60 bg-primary/10 text-foreground'
                  : 'border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'
            }`}>
              <div className="flex items-start gap-3">
                {uploading ? <Loader2 className="mt-0.5 h-4 w-4 animate-spin" /> : <Upload className="mt-0.5 h-4 w-4" />}
                <div className="min-w-0 flex-1">
                  {uploading && uploadPhase ? (
                    <>
                      <p className="font-medium text-foreground">{progressCopy.title}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{progressCopy.detail}</p>
                    </>
                  ) : (
                    <>
                      <p className="font-medium text-foreground">拖拽文件到这里，或选择文件</p>
                      <p className="mt-1 text-xs text-muted-foreground">支持 `.txt`、`.md`、`.pdf`、`.docx`、`.html`，沿用当前工作区作用域导入。</p>
                    </>
                  )}
                </div>
              </div>
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

            {postImportGuide && (
              <div className="mt-3 rounded-xl border border-primary/15 bg-primary/5 p-3">
                <p className="text-sm font-medium text-foreground">{postImportGuide.title}</p>
                <p className="mt-1 text-xs text-muted-foreground">{postImportGuide.description}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {onOpenKnowledgeBase && (
                    <Button size="sm" variant="outline" onClick={onOpenKnowledgeBase}>
                      去知识库核对来源
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setPostImportGuide(null)
                      fileInputRef.current?.click()
                    }}
                  >
                    继续导入
                  </Button>
                </div>
                {postImportGuide.suggestedQuestions.length > 0 && (
                  <div className="mt-3 rounded-lg border border-primary/10 bg-background/70 p-2.5">
                    <p className="text-2xs font-medium text-primary/80 mb-2 tracking-wide">推荐直接追问</p>
                    <div className="space-y-1">
                      {postImportGuide.suggestedQuestions.map((q, i) => (
                        <button
                          key={i}
                          onClick={() => {
                            onSendQuestion?.(q)
                            setPostImportGuide(null)
                          }}
                          className="block w-full text-left text-xs text-foreground/75 hover:text-foreground hover:bg-primary/10 rounded px-2 py-1.5 transition-colors"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
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
        </>
      ) : (
        <div className="rounded-xl border border-border/70 bg-muted/20 p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground/80">当前账号为只读权限</p>
          <p className="mt-1">可以浏览引用文档并发起问答，导入、删除和清空知识库需要编辑者或管理员权限。</p>
        </div>
      )}

      {canManageKnowledgeBase && <Separator />}

      {/* Source List */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-muted-foreground tracking-wide uppercase">引用文档</span>
          {canManageKnowledgeBase && sources.length > 0 && (
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
              {canManageKnowledgeBase && (
                <button
                  onClick={() => setDeleteSourceTarget(s.source)}
                  className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-all"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              )}
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
