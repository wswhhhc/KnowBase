import { FileDown } from 'lucide-react'
import { Button, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui'

interface ExportDialogProps {
  open: boolean
  messageId: string
  exporting: boolean
  exportFormat: 'markdown' | 'json'
  exportSources: boolean
  exportDebug: boolean
  canExport: boolean
  onOpenChange: (open: boolean) => void
  onFormatChange: (format: 'markdown' | 'json') => void
  onSourcesChange: (value: boolean) => void
  onDebugChange: (value: boolean) => void
  onSubmit: () => Promise<void> | void
}

export default function ExportDialog({
  open,
  messageId,
  exporting,
  exportFormat,
  exportSources,
  exportDebug,
  canExport,
  onOpenChange,
  onFormatChange,
  onSourcesChange,
  onDebugChange,
  onSubmit,
}: ExportDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>导出对话</DialogTitle>
          <DialogDescription>选择导出格式和附带内容，导出后会直接下载到本地。</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4 pt-2"
          onSubmit={async (event) => {
            event.preventDefault()
            await onSubmit()
          }}
        >
          <fieldset className="space-y-2">
            <legend className="text-xs font-medium text-foreground/85">导出格式</legend>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={`export-fmt-${messageId}`}
                checked={exportFormat === 'markdown'}
                onChange={() => onFormatChange('markdown')}
                className="accent-primary"
              />
              Markdown
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={`export-fmt-${messageId}`}
                checked={exportFormat === 'json'}
                onChange={() => onFormatChange('json')}
                className="accent-primary"
              />
              JSON
            </label>
          </fieldset>
          <fieldset className="space-y-2">
            <legend className="text-xs font-medium text-foreground/85">附带内容</legend>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={exportSources}
                onChange={(event) => onSourcesChange(event.target.checked)}
                className="accent-primary"
              />
              包含来源
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={exportDebug}
                onChange={(event) => onDebugChange(event.target.checked)}
                className="accent-primary"
              />
              包含调试信息
            </label>
          </fieldset>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={exporting || !canExport}>
              <FileDown className="mr-1 h-3.5 w-3.5" />
              {exporting ? '导出中…' : '确认导出'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
