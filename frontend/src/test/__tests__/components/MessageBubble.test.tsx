import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MessageBubble from '@/components/MessageBubble'

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
  }

  it('keeps only the primary actions visible by default', () => {
    render(<MessageBubble message={baseMessage} onSendQuestion={vi.fn()} />)

    expect(screen.getByRole('button', { name: /1 个来源/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /继续追问/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /更多操作/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /重新回答/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /更简洁/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /导出对话/i })).not.toBeInTheDocument()
  })

  it('reveals secondary actions only after opening the more-actions menu', async () => {
    render(<MessageBubble message={baseMessage} onSendQuestion={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: /更多操作/i }))

    expect(screen.getByRole('button', { name: /重新回答/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /更简洁/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /导出对话/i })).toBeInTheDocument()
  })
})
