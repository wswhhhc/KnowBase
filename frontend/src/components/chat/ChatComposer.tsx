import { Button } from '@/components/ui'
import { Sparkles, Square } from 'lucide-react'

interface ChatComposerProps {
  input: string
  inputRef: React.RefObject<HTMLTextAreaElement | null>
  placeholder: string
  isStreaming: boolean
  onInputChange: (input: string) => void
  onKeyDown: (event: React.KeyboardEvent) => void
  onSend: () => void
  onStopStreaming: () => void
}

export default function ChatComposer({
  input,
  inputRef,
  placeholder,
  isStreaming,
  onInputChange,
  onKeyDown,
  onSend,
  onStopStreaming,
}: ChatComposerProps) {
  return (
    <div className="border-t border-border bg-surface/30 backdrop-blur-sm">
      <div className="mx-auto max-w-3xl px-5 py-4">
        <div className="relative flex items-end gap-2 rounded-xl border border-input bg-background px-4 py-2 shadow-lg shadow-black/5 focus-within:border-primary/50 focus-within:ring-1 focus-within:ring-primary/30 transition-all">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => onInputChange(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground/40 outline-none py-1.5 font-body leading-relaxed"
            disabled={isStreaming}
          />
          {isStreaming ? (
            <Button variant="secondary" size="sm" onClick={onStopStreaming}>
              <Square className="h-3.5 w-3.5 mr-1" />停止
            </Button>
          ) : (
            <Button size="sm" onClick={onSend} disabled={!input.trim()}>
              <Sparkles className="h-3.5 w-3.5 mr-1" />发送
            </Button>
          )}
        </div>
        <p className="mt-1.5 text-2xs text-muted-foreground/30 text-center font-mono tracking-wider">
          KnowBase · RAG 问答 · 回答仅供参考
        </p>
      </div>
    </div>
  )
}
