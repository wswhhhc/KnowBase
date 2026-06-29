import { useRef } from 'react'
import { Button, Input } from '@/components/ui'
import { Upload, Globe, RefreshCw } from 'lucide-react'

interface DocumentActionsProps {
  uploading: boolean
  ingesting: boolean
  uploadPhase: string
  uploadPercent: number
  urlInput: string
  setUrlInput: (v: string) => void
  handleIngestUrl: () => void
  refreshData: () => void
  /* exposed via ref forwarding */
  onUploadClick: () => void
}

export default function DocumentActions({
  uploading, ingesting, uploadPhase, uploadPercent,
  urlInput, setUrlInput, handleIngestUrl, refreshData, onUploadClick,
}: DocumentActionsProps) {
  return (
    <>
      <div className="flex items-center gap-2 border-b border-border px-5 py-2 bg-surface/20">
        <button onClick={onUploadClick}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-md bg-primary/10 text-primary hover:bg-primary/15 transition-colors">
          <Upload className="h-3 w-3" />上传文档
        </button>
        <div className="flex items-center gap-1 flex-1 max-w-sm">
          <Input
            placeholder="导入公开网页 https://…"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleIngestUrl() }}
            className="h-7 text-xs flex-1"
          />
          <Button size="sm" onClick={handleIngestUrl} disabled={ingesting || !urlInput.trim()}>
            <Globe className="h-3 w-3" />
          </Button>
        </div>
        {(uploading || ingesting) && (
          <div className="min-w-[120px] text-right">
            <div className="text-2xs text-muted-foreground/60">
              {{ loading: '正在加载文档…', splitting: '正在切分段落…', embedding: '正在向量化…', done: '完成' }[uploadPhase] || '正在处理…'}
            </div>
            <div className="mt-1 h-1 w-full rounded-full bg-muted overflow-hidden">
              <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${uploadPercent}%` }} />
            </div>
          </div>
        )}
        <button onClick={refreshData}
          className="p-1.5 rounded-md text-muted-foreground/50 hover:text-foreground hover:bg-muted/30 transition-colors">
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
    </>
  )
}
