import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, Separator } from '@/components/ui'
import { FileText } from 'lucide-react'

interface KBChunk {
  chunk_id: string
  source: string
  chunk_index: number
  page?: number | null
  content: string
  original_content?: string | null
  section?: string | null
}

interface ChunkDetailDialogProps {
  chunk: KBChunk | null
  onClose: () => void
}

export default function ChunkDetailDialog({ chunk, onClose }: ChunkDetailDialogProps) {
  return (
    <Dialog open={!!chunk} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">{chunk?.source}</span>
            <span className="text-xs text-muted-foreground font-mono">#{chunk?.chunk_index}</span>
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">查看当前段落的完整内容与基础元信息。</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {chunk?.section && (
              <span className="px-2 py-0.5 text-2xs font-medium rounded-full bg-primary/10 text-primary/80">{chunk.section}</span>
            )}
            {chunk?.page && (
              <span className="px-2 py-0.5 text-2xs font-medium rounded-full bg-muted text-muted-foreground">第 {chunk.page} 页</span>
            )}
            <span className="px-2 py-0.5 text-2xs font-mono rounded-full bg-muted text-muted-foreground">{chunk?.chunk_id.slice(0, 24)}…</span>
          </div>
          <Separator />
          <div className="prose-chat text-sm leading-relaxed">{chunk?.original_content || chunk?.content}</div>
          <div className="text-2xs text-muted-foreground/40 font-mono">{chunk?.content.length} 字符</div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
