import { MessageSquare, Upload } from 'lucide-react'
import { useChatContext } from './ChatContext'
import type { OutcomeGuidance } from './types'

interface OutcomeGuidancePanelProps {
  guidance: OutcomeGuidance
}

export default function OutcomeGuidancePanel({
  guidance,
}: OutcomeGuidancePanelProps) {
  const { onNavigateBrowser, onSendQuestion } = useChatContext()
  return (
    <div className="mt-3 rounded-lg border border-border/60 bg-surface/30 px-3.5 py-3">
      <p className="text-xs font-medium text-foreground/85">{guidance.title}</p>
      <p className="mt-1 text-xs text-muted-foreground/80 leading-relaxed">{guidance.description}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {guidance.primaryLabel && onNavigateBrowser && (
          <button
            onClick={onNavigateBrowser}
            className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-2xs font-medium text-primary/80 transition-colors hover:bg-primary/10 hover:text-primary"
          >
            <Upload className="h-3 w-3" />
            {guidance.primaryLabel}
          </button>
        )}
        {guidance.followUpPrompt && onSendQuestion && (
          <button
            onClick={() => onSendQuestion(guidance.followUpPrompt || '')}
            className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-2xs font-medium text-muted-foreground transition-colors hover:border-primary/20 hover:text-foreground"
          >
            <MessageSquare className="h-3 w-3" />
            {guidance.secondaryLabel}
          </button>
        )}
      </div>
    </div>
  )
}
