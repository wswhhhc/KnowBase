import { render, screen } from '@testing-library/react'
import ChatArea from '@/components/ChatArea'

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      // Strip animation-related props
      const { initial, animate, exit, transition, ...rest } = props
      return <div {...rest}>{children}</div>
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

// Mock the useChat hook
vi.mock('@/hooks/useChat', () => ({
  useChat: () => ({
    messages: [],
    isStreaming: false,
    streamingNodes: [],
    sendMessage: vi.fn(),
    stopStreaming: vi.fn(),
    clearMessages: vi.fn(),
    loadMessages: vi.fn(),
    threadId: null,
  }),
}))

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  PanelRightOpen: 'PanelRightOpen',
  Square: 'Square',
  Sparkles: 'Sparkles',
  Search: 'Search',
  Globe: 'Globe',
  Zap: 'Zap',
  RotateCcw: 'RotateCcw',
  Download: 'Download',
  ThumbsUp: 'ThumbsUp',
  ThumbsDown: 'ThumbsDown',
  BookOpen: 'BookOpen',
  BarChart3: 'BarChart3',
  FileDown: 'FileDown',
  Sun: 'Sun',
  Moon: 'Moon',
  Copy: 'Copy',
  CheckCircle: 'CheckCircle',
  Bug: 'Bug',
  ChevronDown: 'ChevronDown',
  ChevronRight: 'ChevronRight',
}))

describe('ChatArea', () => {
  const defaultProps = {
    chat: {
      messages: [] as any[],
      isStreaming: false,
      streamingNodes: [] as string[],
      sendMessage: vi.fn(),
      stopStreaming: vi.fn(),
      clearMessages: vi.fn(),
      loadMessages: vi.fn(),
      threadId: null,
    },
    onOpenSidebar: vi.fn(),
    sidebarOpen: true,
    onNavigate: vi.fn(),
    theme: { theme: 'dark' as const, toggle: vi.fn() },
    isLoadingMessages: false,
  }

  it('renders the input area with placeholder', () => {
    render(<ChatArea {...defaultProps} />)

    const input = screen.getByPlaceholderText('输入你的问题…')
    expect(input).toBeInTheDocument()
  })

  it('renders the send button', () => {
    render(<ChatArea {...defaultProps} />)

    const sendButton = screen.getByText('发送')
    expect(sendButton).toBeInTheDocument()
  })

  it('renders the welcome message when no messages', () => {
    render(<ChatArea {...defaultProps} />)

    expect(screen.getByText('知识库问答助手')).toBeInTheDocument()
    expect(screen.getByText(/上传文档或导入网页/)).toBeInTheDocument()
  })
})
