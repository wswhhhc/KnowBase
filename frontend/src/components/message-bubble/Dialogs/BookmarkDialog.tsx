import { Button, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, Input } from '@/components/ui'

interface BookmarkDialogProps {
  open: boolean
  note: string
  messageId: string
  onNoteChange: (note: string) => void
  onOpenChange: (open: boolean) => void
  onConfirm: () => Promise<void> | void
}

export default function BookmarkDialog({
  open,
  note,
  messageId,
  onNoteChange,
  onOpenChange,
  onConfirm,
}: BookmarkDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>收藏回答</DialogTitle>
          <DialogDescription>可以补一条备注，方便之后回看为什么保留这条回答。</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4 pt-2"
          onSubmit={async (event) => {
            event.preventDefault()
            await onConfirm()
          }}
        >
          <div className="space-y-2">
            <label htmlFor={`bookmark-note-${messageId}`} className="text-xs font-medium text-foreground/85">
              备注
            </label>
            <Input
              id={`bookmark-note-${messageId}`}
              value={note}
              onChange={(event) => onNoteChange(event.target.value)}
              placeholder="为什么收藏这条回答？"
              className="text-xs"
              autoFocus
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit">保存</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
