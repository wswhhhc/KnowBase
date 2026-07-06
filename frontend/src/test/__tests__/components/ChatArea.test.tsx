import { render, screen } from '@testing-library/react'
import ChatArea from '@/pages/chat/ChatPage'

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
vi.mock('lucide-react', () => {
  const icon = (name: string) => ({ children, ...props }: any) => <span data-testid={`icon-${name}`} {...props}>{children}</span>
  return {
    PanelRightOpen: icon('PanelRightOpen'),
    Square: icon('Square'),
    Sparkles: icon('Sparkles'),
    Search: icon('Search'),
    Scale: icon('Scale'),
    FileSearch: icon('FileSearch'),
    Globe: icon('Globe'),
    Zap: icon('Zap'),
    RotateCcw: icon('RotateCcw'),
    Download: icon('Download'),
    ThumbsUp: icon('ThumbsUp'),
    ThumbsDown: icon('ThumbsDown'),
    BookOpen: icon('BookOpen'),
    BarChart3: icon('BarChart3'),
    FileDown: icon('FileDown'),
    Sun: icon('Sun'),
    Moon: icon('Moon'),
    SlidersHorizontal: icon('SlidersHorizontal'),
    Copy: icon('Copy'),
    CheckCircle: icon('CheckCircle'),
    Bug: icon('Bug'),
    ChevronDown: icon('ChevronDown'),
    ChevronRight: icon('ChevronRight'),
    Upload: icon('Upload'),
    MessageSquare: icon('MessageSquare'),
    Bookmark: icon('Bookmark'),
    BookmarkCheck: icon('BookmarkCheck'),
    ExternalLink: icon('ExternalLink'),
    RefreshCw: icon('RefreshCw'),
    AlignLeft: icon('AlignLeft'),
    Paperclip: icon('Paperclip'),
    Pin: icon('Pin'),
    X: icon('X'),
    ArrowRight: icon('ArrowRight'),
    LibraryBig: icon('LibraryBig'),
    MessageSquareText: icon('MessageSquareText'),
    History: icon('History'),
  }
})

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
      pinnedSources: [] as any[],
      setPinnedSources: vi.fn(),
      workspaceId: '',
      setWorkspaceId: vi.fn(),
      threadId: null,
    },
    onOpenSidebar: vi.fn(),
    sidebarOpen: true,
    onNavigate: vi.fn(),
    workspaceSummary: {
      workspaceName: '默认工作区',
      documentCount: 0,
      conversationCount: 0,
    },
    isLoadingMessages: false,
    isMobile: false,
  }

  it('renders the input area with placeholder', () => {
    render(<ChatArea {...defaultProps} />)

    const input = screen.getByPlaceholderText('先导入资料，或直接输入你想验证的问题…')
    expect(input).toBeInTheDocument()
  })

  it('renders the send button', () => {
    render(<ChatArea {...defaultProps} />)

    const sendButton = screen.getByText('发送')
    expect(sendButton).toBeInTheDocument()
  })

  it('renders the welcome message when no messages', () => {
    render(<ChatArea {...defaultProps} />)

    expect(screen.getByText('当前工作区还没有资料')).toBeInTheDocument()
    expect(screen.getByText('未导入资料')).toBeInTheDocument()
  })

  it('shows a first-question prompt when the workspace has documents but no conversations yet', () => {
    render(
      <ChatArea
        {...defaultProps}
        workspaceSummary={{
          workspaceName: '默认工作区',
          documentCount: 5,
          conversationCount: 0,
        }}
      />,
    )

    expect(screen.getByText('资料已导入，还没开始提问')).toBeInTheDocument()
    expect(screen.getByText('去知识库核对来源')).toBeInTheDocument()
  })

  it('shows a return-user prompt when the workspace already has documents and conversations', () => {
    render(
      <ChatArea
        {...defaultProps}
        workspaceSummary={{
          workspaceName: '默认工作区',
          documentCount: 5,
          conversationCount: 3,
        }}
      />,
    )

    expect(screen.getByText('已有历史对话，可继续推进')).toBeInTheDocument()
    expect(screen.getByText('继续当前问题')).toBeInTheDocument()
  })

  it('renders the browser navigation label as 知识库', () => {
    render(<ChatArea {...defaultProps} />)

    expect(screen.getByText('知识库')).toBeInTheDocument()
  })

  it('hides the dashboard navigation pill when app management is unavailable', () => {
    render(<ChatArea {...defaultProps} canManageApp={false} />)

    expect(screen.queryByText('指标')).not.toBeInTheDocument()
  })

  it('shows the current workspace summary in the header', () => {
    render(<ChatArea {...defaultProps} />)

    expect(screen.getByText('当前工作区：默认工作区 · 0 份资料')).toBeInTheDocument()
  })
})
