import { Button, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui'
import { FEEDBACK_OPTIONS } from '../guidance'

interface FeedbackDialogProps {
  open: boolean
  messageId: string
  feedbackCategory: string | null
  feedbackDetail: string
  onCategoryChange: (category: string) => void
  onDetailChange: (detail: string) => void
  onOpenChange: (open: boolean) => void
  onSubmit: () => Promise<void> | void
}

export default function FeedbackDialog({
  open,
  messageId,
  feedbackCategory,
  feedbackDetail,
  onCategoryChange,
  onDetailChange,
  onOpenChange,
  onSubmit,
}: FeedbackDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>这条回答哪里不理想？</DialogTitle>
          <DialogDescription>选择一个主要原因，可以补充说明，便于后续改进回答质量。</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4 pt-2"
          onSubmit={async (event) => {
            event.preventDefault()
            await onSubmit()
          }}
        >
          <fieldset className="space-y-2">
            <legend className="text-xs font-medium text-foreground/85">反馈原因</legend>
            {FEEDBACK_OPTIONS.map((option) => (
              <label
                key={option.key}
                className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors ${
                  feedbackCategory === option.key
                    ? 'border-primary/30 bg-primary/10 text-primary'
                    : 'border-border text-foreground hover:bg-muted/40'
                }`}
              >
                <input
                  type="radio"
                  name={`feedback-reason-${messageId}`}
                  value={option.key}
                  checked={feedbackCategory === option.key}
                  onChange={() => onCategoryChange(option.key)}
                  className="accent-primary"
                />
                <span>{option.label}</span>
              </label>
            ))}
          </fieldset>
          <div className="space-y-2">
            <label htmlFor={`feedback-detail-${messageId}`} className="text-xs font-medium text-foreground/85">
              补充说明
            </label>
            <textarea
              id={`feedback-detail-${messageId}`}
              value={feedbackDetail}
              onChange={(event) => onDetailChange(event.target.value)}
              placeholder="可选，补充一下哪里不准确或不够有用"
              className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/40 focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={!feedbackCategory}>
              提交反馈
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
