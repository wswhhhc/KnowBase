import { useEffect, useMemo, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ScrollArea, Skeleton } from '@/components/ui'
import EmptyState from '@/components/EmptyState'
import MessageBubble from '@/components/MessageBubble'
import type { PinnedSource, ChatMessage } from '@/hooks/useChat'
import type { Source } from '@/shared/api'
import type { WorkspaceSummary } from '@/types/workspace-summary'

interface ChatMessageListProps {
  messages: ChatMessage[]
  isStreaming: boolean
  streamingNodes: string[]
  isLoadingMessages?: boolean
  threadId: string | null
  workspaceId: string
  workspaceSummary: WorkspaceSummary
  pinnedSources: PinnedSource[]
  onCitationClick?: (source: Source) => void
  onSendQuestion?: (question: string) => void
  onOpenDocuments: () => void
  onFocusComposer: () => void
  onNavigateBrowser: () => void
  onPinToggle: (chunkId: string, action: 'pin' | 'unpin' | 'exclude' | 'unexclude') => void
}

export default function ChatMessageList({
  messages,
  isStreaming,
  streamingNodes,
  isLoadingMessages,
  threadId,
  workspaceId,
  workspaceSummary,
  pinnedSources,
  onCitationClick,
  onSendQuestion,
  onOpenDocuments,
  onFocusComposer,
  onNavigateBrowser,
  onPinToggle,
}: ChatMessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const previousLoadingRef = useRef(isLoadingMessages)
  const isEmpty = messages.length === 0
  const emptyStateMode = useMemo(() => {
    if (workspaceSummary.documentCount <= 0) return 'onboarding' as const
    if (workspaceSummary.conversationCount > 0) return 'returning' as const
    return 'first-question' as const
  }, [workspaceSummary.conversationCount, workspaceSummary.documentCount])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streamingNodes, isLoadingMessages])

  useEffect(() => {
    if (previousLoadingRef.current && !isLoadingMessages) {
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
      })
    }
    previousLoadingRef.current = isLoadingMessages
  }, [isLoadingMessages])

  return (
    <ScrollArea ref={scrollRef} className="flex-1">
      <div className="mx-auto max-w-3xl px-5 py-8">
        {isLoadingMessages ? <MessageSkeleton /> : isEmpty ? (
          <EmptyState
            mode={emptyStateMode}
            workspaceName={workspaceSummary.workspaceName}
            documentCount={workspaceSummary.documentCount}
            conversationCount={workspaceSummary.conversationCount}
            onPrimaryAction={emptyStateMode === 'onboarding' ? onOpenDocuments : onFocusComposer}
            onSecondaryAction={emptyStateMode === 'onboarding' ? undefined : onNavigateBrowser}
          />
        ) : (
          <div className="space-y-6">
            {messages.map((message, index) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: 'easeOut' }}
              >
                <MessageBubble
                  message={message}
                  prevMessage={index > 0 ? messages[index - 1] : undefined}
                  threadId={threadId}
                  onCitationClick={onCitationClick}
                  onSendQuestion={onSendQuestion}
                  onNavigateBrowser={onNavigateBrowser}
                  pinnedSources={pinnedSources}
                  onPinToggle={onPinToggle}
                  workspaceId={workspaceId}
                  workspaceSummary={workspaceSummary}
                />
              </motion.div>
            ))}

            <AnimatePresence>
              {isStreaming && streamingNodes.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="flex items-center gap-2 text-xs text-muted-foreground"
                >
                  <div className="flex items-center gap-1 flex-wrap">
                    {streamingNodes.map((node, index) => (
                      <span key={node}
                        className={`px-2 py-0.5 rounded-full transition-all ${
                          index === streamingNodes.length - 1
                            ? 'bg-primary/15 text-primary font-medium'
                            : 'bg-muted text-muted-foreground'
                        }`}>
                        {node}
                      </span>
                    ))}
                  </div>
                  <span className="animate-pulse-soft text-primary">●</span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </ScrollArea>
  )
}

function MessageSkeleton() {
  const widths = [75, 85, 60, 90]
  return (
    <div className="space-y-6">
      {widths.map((width, index) => (
        <div key={index} className={`flex gap-3 ${index % 2 === 0 ? '' : 'flex-row-reverse'}`}>
          {index % 2 === 0 && <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />}
          <div className={`flex-1 ${index % 2 === 0 ? '' : 'max-w-[75%]'}`}>
            <Skeleton className="h-16 rounded-2xl" style={index % 2 === 0 ? { width: `${width}%` } : { width: `${width}%`, marginLeft: 'auto' }} />
          </div>
        </div>
      ))}
    </div>
  )
}
