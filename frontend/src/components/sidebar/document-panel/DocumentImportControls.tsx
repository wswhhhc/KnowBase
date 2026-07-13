import { useState, type ReactNode, type RefObject } from 'react'
import { Globe, Loader2, Upload } from 'lucide-react'
import { Button, Input } from '@/components/ui'
import { DocumentImportProgressCopy } from '@/components/sidebar/document-panel/DocumentImportFeedback'
import type { useDocumentImport } from '@/features/documents/hooks/useDocumentImport'

type DocumentImportController = ReturnType<typeof useDocumentImport>

interface DocumentImportControlsProps {
  controller: DocumentImportController
  workspaceName: string
  fileInputRef: RefObject<HTMLInputElement | null>
  children?: ReactNode
}

export default function DocumentImportControls({
  controller,
  workspaceName,
  fileInputRef,
  children,
}: DocumentImportControlsProps) {
  const [dragDepth, setDragDepth] = useState(0)
  const isDragActive = dragDepth > 0

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
            setDragDepth((current) => current + 1)
          }}
          onDragOver={(event) => {
            event.preventDefault()
            if (!controller.uploading) event.dataTransfer.dropEffect = 'copy'
          }}
          onDragLeave={(event) => {
            event.preventDefault()
            setDragDepth((current) => Math.max(0, current - 1))
          }}
          onDrop={(event) => {
            event.preventDefault()
            setDragDepth(0)
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
              {controller.uploading ? (
                <DocumentImportProgressCopy uploadPhase={controller.uploadPhase} />
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
              const file = event.currentTarget.files?.[0]
              event.currentTarget.value = ''
              if (file) void controller.importFile(file)
            }}
          />
        </label>
        {children}
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
