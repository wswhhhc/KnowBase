import * as React from 'react'
import { Button } from './button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './dialog'

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'default' | 'destructive'
  onConfirm: () => Promise<void> | void
}

export function ConfirmDialog({
  open, onOpenChange, title, description,
  confirmLabel = '确认删除', cancelLabel = '取消',
  variant = 'destructive', onConfirm,
}: ConfirmDialogProps) {
  const [loading, setLoading] = React.useState(false)

  const handleConfirm = async () => {
    setLoading(true)
    try {
      await onConfirm()
    } finally {
      setLoading(false)
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button variant={variant} onClick={handleConfirm} disabled={loading}>
            {loading ? '处理中…' : confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
