import type { ComponentProps } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MessageBubble from '@/components/MessageBubble'
import * as api from '@/shared/api'

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { initial, animate, exit, transition, ...rest } = props
      return <div {...rest}>{children}</div>
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock('@/components/DebugPanel', () => ({
  default: () => <div>DebugPanel</div>,
}))

vi.mock('@/shared/api', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api')>('@/shared/api')
  return {
    ...actual,
    createBookmark: vi.fn(),
    updateFeedback: vi.fn(),
    exportConversation: vi.fn(),
  }
})

vi.mock('lucide-react', () => {
  const icon = (name: string) => ({ children, ...props }: any) => <span {...props}>{children || name}</span>
  return {
    ThumbsUp: icon('ThumbsUp'),
    ThumbsDown: icon('ThumbsDown'),
    FileDown: icon('FileDown'),
    Copy: icon('Copy'),
    CheckCircle: icon('CheckCircle'),
    MessageSquare: icon('MessageSquare'),
    ExternalLink: icon('ExternalLink'),
    Upload: icon('Upload'),
    Bookmark: icon('Bookmark'),
    BookmarkCheck: icon('BookmarkCheck'),
    RefreshCw: icon('RefreshCw'),
    AlignLeft: icon('AlignLeft'),
    Paperclip: icon('Paperclip'),
    Pin: icon('Pin'),
    X: icon('X'),
    MoreHorizontal: icon('MoreHorizontal'),
  }
})

describe('MessageBubble', () => {
  const baseMessage = {
    id: 'assistant-1',
    role: 'assistant' as const,
    content: '根据文档 [1]，标准上班时间为 09:00 - 18:00。',
    sources: [
      {
        index: 1,
        source: '员工手册.md',
        chunk_id: 'chunk-1',
        content: '标准上班时间为周一至周五 09:00 - 18:00',
      },
    ],
    evidence_level: 'strong',
    evidence_summary: '多个片段支持该结论',
    outcome_category: 'success',
    originalQuestion: '我们上午几点上班？',
    convId: 'conv-1',
    assistantMsgId: 42,
  }

  const createBookmarkMock = vi.mocked(api.createBookmark)
  const updateFeedbackMock = vi.mocked(api.updateFeedback)
  const exportConversationMock = vi.mocked(api.exportConversation)

  beforeEach(() => {
    vi.clearAllMocks()
    createBookmarkMock.mockResolvedValue({ id: 1 } as any)
    updateFeedbackMock.mockResolvedValue({ ok: true } as any)
    exportConversationMock.mockResolvedValue({ markdown: '# exported' } as any)
  })

  function renderBubble(props?: Partial<ComponentProps<typeof MessageBubble>>) {
    return render(
      <MessageBubble
        message={baseMessage}
        onSendQuestion={vi.fn()}
        threadId="thread-1"
        {...props}
      />,
    )
  }

  it('maps citation markers back to the matching source when clicked', async () => {
    const onCitationClick = vi.fn()
    renderBubble({ onCitationClick })

    await userEvent.click(screen.getByText('1'))

    expect(onCitationClick).toHaveBeenCalledWith(baseMessage.sources[0])
  })

  it('keeps only the primary actions visible by default', () => {
    renderBubble()

    expect(screen.getByRole('button', { name: /1 个来源/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /继续追问/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /更多操作/i })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /重新回答/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /更简洁/i })).not.toBeInTheDocument()
    expect(screen.queryByText('导出对话')).not.toBeInTheDocument()
  })

  it('reveals secondary actions only after opening the more-actions menu and closes on escape', async () => {
    renderBubble()

    await userEvent.click(screen.getByRole('button', { name: /更多操作/i }))

    expect(screen.getByRole('menuitem', { name: /重新回答/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /更简洁/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /导出对话/i })).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')

    await waitFor(() => {
      expect(screen.queryByRole('menuitem', { name: /重新回答/i })).not.toBeInTheDocument()
    })
  })

  it('opens and closes the bookmark dialog, then saves a note', async () => {
    renderBubble()

    await userEvent.click(screen.getByRole('button', { name: /收藏回答/i }))
    expect(screen.getByRole('dialog', { name: '收藏回答' })).toBeInTheDocument()

    const overlay = document.body.querySelector('.fixed.inset-0') as HTMLElement | null
    expect(overlay).not.toBeNull()
    if (overlay) {
      await userEvent.click(overlay)
    }

    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: '收藏回答' })).not.toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /收藏回答/i }))
    await userEvent.type(screen.getByLabelText('备注'), '用于核对考勤')
    await userEvent.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() => {
      expect(createBookmarkMock).toHaveBeenCalledWith(expect.objectContaining({
        conversation_id: 'conv-1',
        message_id: 42,
        note: '用于核对考勤',
      }))
    })
    expect(screen.queryByRole('dialog', { name: '收藏回答' })).not.toBeInTheDocument()
  })

  it('submits unhelpful feedback without leaking state into other overlays', async () => {
    renderBubble()

    await userEvent.click(screen.getByRole('button', { name: '无帮助' }))
    expect(screen.getByRole('dialog', { name: '这条回答哪里不理想？' })).toBeInTheDocument()

    await userEvent.click(screen.getByLabelText('答非所问'))
    await userEvent.type(screen.getByLabelText('补充说明'), '没有回答时间范围')
    await userEvent.click(screen.getByRole('button', { name: '提交反馈' }))

    await waitFor(() => {
      expect(updateFeedbackMock).toHaveBeenCalledWith(
        'conv-1',
        42,
        'unhelpful',
        'off_topic',
        '没有回答时间范围',
        undefined,
      )
    })

    expect(screen.queryByRole('dialog', { name: '这条回答哪里不理想？' })).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: '收藏回答' })).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: '导出对话' })).not.toBeInTheDocument()
  })

  it('opens export as a separate dialog from the menu and remains usable in a narrow container', async () => {
    render(
      <div style={{ width: 280 }}>
        <MessageBubble
          message={baseMessage}
          onSendQuestion={vi.fn()}
          threadId="thread-1"
        />
      </div>,
    )

    await userEvent.click(screen.getByRole('button', { name: /更多操作/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /导出对话/i }))

    expect(screen.queryByRole('menuitem', { name: /重新回答/i })).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: '导出对话' })).toBeInTheDocument()

    await userEvent.click(screen.getByLabelText('JSON'))
    await userEvent.click(screen.getByLabelText('包含调试信息'))

    expect(screen.getByLabelText('JSON')).toBeChecked()
    expect(screen.getByLabelText('包含调试信息')).toBeChecked()
    expect(screen.getByRole('button', { name: /确认导出/i })).toBeEnabled()
    expect(exportConversationMock).not.toHaveBeenCalled()

    await userEvent.keyboard('{Escape}')

    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: '导出对话' })).not.toBeInTheDocument()
    })
  })

  it('shows the answer strategy echo for assistant messages', () => {
    renderBubble({
      message: {
        ...baseMessage,
        searchStrategy: 'high_quality',
        webSearchEnabled: true,
        usedRerank: true,
        elapsedMs: 1520,
      },
    })

    expect(screen.getByText('策略：严谨')).toBeInTheDocument()
    expect(screen.getByText('重排：是')).toBeInTheDocument()
    expect(screen.getByText('联网：是')).toBeInTheDocument()
    expect(screen.getByText('耗时：1.5s')).toBeInTheDocument()
  })

  it('renders safely when debugData exists without nodes', () => {
    renderBubble({
      message: {
        ...baseMessage,
        debugData: { used_rerank: false, used_web_search: false } as any,
      },
    })

    expect(screen.getByText('重排：否')).toBeInTheDocument()
    expect(screen.getByText('联网：否')).toBeInTheDocument()
    expect(screen.queryByText(/策略：/)).not.toBeInTheDocument()
    expect(screen.queryByText(/耗时：/)).not.toBeInTheDocument()
  })
})
