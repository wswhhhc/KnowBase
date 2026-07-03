import AssistantMessageBubble from '@/components/message-bubble/AssistantMessageBubble'
import type { MessageBubbleProps } from '@/components/message-bubble/types'

export default function MessageBubble(props: MessageBubbleProps) {
  if (props.message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%]">
          <div className="rounded-2xl bg-primary/10 px-4 py-2.5 border border-primary/5">
            <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{props.message.content}</p>
          </div>
        </div>
      </div>
    )
  }

  return <AssistantMessageBubble {...props} />
}
