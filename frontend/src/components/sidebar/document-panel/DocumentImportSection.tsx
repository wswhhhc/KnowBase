import { useRef, useState } from 'react'
import { Globe, Loader2, Upload } from 'lucide-react'
import { Button, Input } from '@/components/ui'
import { PHASE_COPY, type useDocumentImport } from '@/features/documents/hooks/useDocumentImport'

type DocumentImportController = ReturnType<typeof useDocumentImport>

interface DocumentImportSectionProps {
  controller: DocumentImportController
  workspaceName: string
  onSendQuestion?: (question: string) => void
  onOpenKnowledgeBase?: () => void
}

export default function DocumentImportSection({
  controller,
  workspaceName,
  onSendQuestion,
  onOpenKnowledgeBase,
}: DocumentImportSectionProps) {
  const [isDragActive, setIsDragActive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dragDepthRef = useRef(0)
  const progressCopy = controller.uploadPhase
    ? PHASE_COPY[controller.uploadPhase] ?? { title: '正在处理资料…', detail: '请稍候，系统正在准备可检索内容。' }
    : null

  return (
    <>
      <div className="rounded-xl border border-border/70 bg-surface/35 p-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-foreground">导入示例资料</p>
            <p className="mt-1 text-xs text-muted-foreground">
              一键导入 3 份演示资料到“{workspaceName}”，用于快速体验问答、知识库核对与工作区作用域。
            </p>
          </div>
          <Button size="sm" onClick={controller.importDemoDocuments} disabled={controller.demoImporting || controller.uploading} className="shrink-0">
            {controller.demoImporting ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
            导入示例资料
          </Button>
        </div>
      </div>

      <div>
        <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted-foreground">上传文档</label>
        <label
          onDragEnter={(event) => {
            event.preventDefault()
            dragDepthRef.current += 1
            setIsDragActive(true)
          }}
          onDragOver={(event) => {
            event.preventDefault()
            if (!controller.uploading) event.dataTransfer.dropEffect = 'copy'
          }}
          onDragLeave={(event) => {
            event.preventDefault()
            dragDepthRef.current = Math.max(0, dragDepthRef.current - 1)
            if (dragDepthRef.current === 0) setIsDragActive(false)
          }}
          onDrop={(event) => {
            event.preventDefault()
            dragDepthRef.current = 0
            setIsDragActive(false)
            const file = event.dataTransfer.files?.[0]
            if (file && !controller.uploading) void controller.importFile(file)
          }}
          className={`block cursor-pointer rounded-xl border border-dashed px-3 py-3 text-sm transition-colors ${
            controller.uploading
              ? 'border-primary/40 bg-primary/5 text-primary'
              : isDragActive
                ? 'border-primary/60 bg-primary/10 text-foreground'
                : 'border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'
          }`}
        >
          <div className="flex items-start gap-3">
            {controller.uploading ? <Loader2 className="mt-0.5 h-4 w-4 animate-spin" /> : <Upload className="mt-0.5 h-4 w-4" />}
            <div className="min-w-0 flex-1">
              {controller.uploading && progressCopy ? (
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
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".txt,.md,.pdf,.docx,.html"
            disabled={controller.uploading}
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void controller.importFile(file)
            }}
          />
        </label>
        {controller.uploading && (
          <div className="mt-1.5 space-y-1">
            <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${controller.uploadPercent}%` }} />
            </div>
            <p className="text-right text-2xs text-muted-foreground/60">{controller.uploadPercent}%</p>
          </div>
        )}

        {controller.postImportGuide && (
          <div className="mt-3 rounded-xl border border-primary/15 bg-primary/5 p-3">
            <p className="text-sm font-medium text-foreground">{controller.postImportGuide.title}</p>
            <p className="mt-1 text-xs text-muted-foreground">{controller.postImportGuide.description}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {onOpenKnowledgeBase && <Button size="sm" variant="outline" onClick={onOpenKnowledgeBase}>去知识库核对来源</Button>}
              <Button size="sm" variant="outline" onClick={() => {
                controller.setPostImportGuide(null)
                fileInputRef.current?.click()
              }}>
                继续导入
              </Button>
            </div>
            {controller.postImportGuide.suggestedQuestions.length > 0 && (
              <div className="mt-3 rounded-lg border border-primary/10 bg-background/70 p-2.5">
                <p className="mb-2 text-2xs font-medium tracking-wide text-primary/80">推荐直接追问</p>
                <div className="space-y-1">
                  {controller.postImportGuide.suggestedQuestions.map((question, index) => (
                    <button
                      key={index}
                      onClick={() => {
                        onSendQuestion?.(question)
                        controller.setPostImportGuide(null)
                      }}
                      className="block w-full rounded px-2 py-1.5 text-left text-xs text-foreground/75 transition-colors hover:bg-primary/10 hover:text-foreground"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {controller.versionPrompt && (
          <div className="mt-2 rounded-lg border border-primary/15 bg-primary/5 p-3">
            <p className="mb-2 text-2xs font-medium tracking-wide text-primary/80">该来源已存在，请选择操作方式</p>
            <div className="space-y-1">
              <button onClick={() => void controller.selectVersionMode('replace')} className="block w-full rounded px-2 py-1.5 text-left text-xs text-foreground/80 transition-colors hover:bg-primary/10">
                替换为新版本（删除旧内容后重新导入）
              </button>
              <button onClick={() => void controller.selectVersionMode('append')} className="block w-full rounded px-2 py-1.5 text-left text-xs text-foreground/80 transition-colors hover:bg-primary/10">
                保留两者（新旧版本共存）
              </button>
              <button onClick={() => {
                controller.skipVersionPrompt()
                if (fileInputRef.current) fileInputRef.current.value = ''
              }} className="block w-full rounded px-2 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:bg-muted/50">
                取消，不重复导入
              </button>
            </div>
          </div>
        )}
      </div>

      <div>
        <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted-foreground">导入公开网页</label>
        <div className="flex gap-2">
          <Input
            placeholder="https://…"
            value={controller.urlInput}
            onChange={(event) => controller.setUrlInput(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter') void controller.importUrlInput() }}
            className="flex-1"
          />
          <Button size="sm" onClick={() => void controller.importUrlInput()}><Globe className="h-3.5 w-3.5" /></Button>
        </div>
      </div>
    </>
  )
}
