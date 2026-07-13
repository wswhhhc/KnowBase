import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChatMessageList from '@/components/chat/ChatMessageList'

vi.mock('framer-motion', () => ({
  motion: { div: ({ children }: { children: React.ReactNode }) => <div>{children}</div> },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('@/components/ui', async () => {
  const React = await import('react')
  return {
    ScrollArea: React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
      ({ children, ...props }, ref) => <div ref={ref} data-testid="message-scroll" {...props}>{children}</div>,
    ),
    Skeleton: (props: React.HTMLAttributes<HTMLDivElement>) => <div {...props} />,
  }
})

vi.mock('@/components/EmptyState', () => ({
  default: () => <div>empty state</div>,
}))

vi.mock('@/components/MessageBubble', () => ({
  default: () => <div>message</div>,
}))

const baseProps = {
  messages: [],
  isStreaming: false,
  streamingNodes: [],
  threadId: null,
  workspaceId: '',
  workspaceSummary: { workspaceName: '默认工作区', documentCount: 0, conversationCount: 0 },
  pinnedSources: [],
  onOpenDocuments: vi.fn(),
  onFocusComposer: vi.fn(),
  onNavigateBrowser: vi.fn(),
  onPinToggle: vi.fn(),
}

describe('ChatMessageList', () => {
  beforeEach(() => {
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
      callback(0)
      return 1
    }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('performs the deferred second scroll when message loading completes', () => {
    const { rerender } = render(<ChatMessageList {...baseProps} isLoadingMessages />)
    const scrollArea = screen.getByTestId('message-scroll')
    Object.defineProperty(scrollArea, 'scrollHeight', { configurable: true, value: 480 })
    scrollArea.scrollTop = 0

    rerender(<ChatMessageList {...baseProps} isLoadingMessages={false} />)

    expect(requestAnimationFrame).toHaveBeenCalledOnce()
    expect(scrollArea.scrollTop).toBe(480)
  })
})
