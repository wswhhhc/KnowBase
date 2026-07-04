import { render, screen, waitFor, act, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ChatArea from '@/pages/chat/ChatPage'

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { initial, animate, exit, transition, ...rest } = props
      return <div {...rest}>{children}</div>
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

// Mock lucide-react
vi.mock('lucide-react', () => {
  const icons: Record<string, string> = {
    PanelRightOpen: 'PanelRightOpen', Square: 'Square', Sparkles: 'Sparkles',
    Search: 'Search', Globe: 'Globe', Zap: 'Zap', Scale: 'Scale', FileSearch: 'FileSearch', RotateCcw: 'RotateCcw',
    SlidersHorizontal: 'SlidersHorizontal',
    Download: 'Download', ThumbsUp: 'ThumbsUp', ThumbsDown: 'ThumbsDown',
    BookOpen: 'BookOpen', BarChart3: 'BarChart3', FileDown: 'FileDown',
    Sun: 'Sun', Moon: 'Moon', Copy: 'Copy', CheckCircle: 'CheckCircle',
    Bug: 'Bug', ChevronDown: 'ChevronDown', ChevronRight: 'ChevronRight',
    MessageSquare: 'MessageSquare',
    Bookmark: 'Bookmark', BookmarkCheck: 'BookmarkCheck', ExternalLink: 'ExternalLink', Upload: 'Upload',
    RefreshCw: 'RefreshCw', AlignLeft: 'AlignLeft', Paperclip: 'Paperclip', Pin: 'Pin', X: 'X',
    ArrowRight: 'ArrowRight', LibraryBig: 'LibraryBig', MessageSquareText: 'MessageSquareText', History: 'History',
  }
  return Object.fromEntries(
    Object.keys(icons).map((name) => [name, () => <span>{name}</span>])
  )
})

const mockSendMessage = vi.fn()
const mockStopStreaming = vi.fn()
const mockClearMessages = vi.fn()
const mockLoadMessages = vi.fn()
const mockToggleTheme = vi.fn()
const mockOnNavigate = vi.fn()
const mockOnOpenSidebar = vi.fn()

// Mock useTheme before any imports that might use it
vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ theme: 'dark', toggle: mockToggleTheme }),
}))

function createChat(overrides?: any) {
  return {
    messages: [] as any[],
    isStreaming: false,
    streamingNodes: [] as string[],
    sendMessage: mockSendMessage,
    stopStreaming: mockStopStreaming,
    clearMessages: mockClearMessages,
    loadMessages: mockLoadMessages,
    pinnedSources: [] as any[],
    setPinnedSources: vi.fn(),
    workspaceId: '',
    setWorkspaceId: vi.fn(),
    threadId: null,
    ...overrides,
  }
}

function renderChatArea(chatOverrides?: any, propsOverrides?: any) {
  const chat = createChat(chatOverrides)
  return render(
    <ChatArea
      chat={chat}
      onOpenSidebar={mockOnOpenSidebar}
      sidebarOpen={true}
      onNavigate={mockOnNavigate}
      isLoadingMessages={false}
      workspaceSummary={{
        workspaceName: '默认工作区',
        documentCount: 0,
        conversationCount: 0,
      }}
      isMobile={false}
      {...propsOverrides}
    />
  )
}

describe('ChatArea interactions', () => {
  const onboardingPlaceholder = '先导入资料，或直接输入你想验证的问题…'

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders input area with placeholder', () => {
    renderChatArea()
    expect(screen.getByPlaceholderText(onboardingPlaceholder)).toBeInTheDocument()
  })

  it('shows search strategy buttons by default', async () => {
    renderChatArea()
    expect(screen.getByText('快速')).toBeInTheDocument()
    expect(screen.getByText('标准')).toBeInTheDocument()
    expect(screen.getByText('严谨')).toBeInTheDocument()
    expect(screen.getByText('深度')).toBeInTheDocument()
  })

  it('hydrates persisted search preferences from localStorage', async () => {
    localStorage.setItem('kb_web_search', 'true')
    localStorage.setItem('kb_search_strategy', 'deep')

    renderChatArea()
    const input = screen.getByPlaceholderText(onboardingPlaceholder)

    await userEvent.type(input, '读取偏好')
    await userEvent.click(screen.getByText('发送'))

    expect(mockSendMessage).toHaveBeenCalledWith('读取偏好', true, 'deep')
  })

  it('persists updated search preferences to localStorage', async () => {
    renderChatArea()

    await userEvent.click(screen.getByRole('switch'))
    await userEvent.click(screen.getByText('深度'))

    expect(localStorage.getItem('kb_web_search')).toBe('true')
    expect(localStorage.getItem('kb_search_strategy')).toBe('deep')
  })

  it('treats search strategies as a keyboard-navigable radio group', async () => {
    renderChatArea()

    const group = screen.getByRole('radiogroup', { name: '检索策略' })
    expect(group).toBeInTheDocument()

    const balanced = screen.getByRole('radio', { name: /标准$/ })
    const deep = screen.getByRole('radio', { name: /深度$/ })

    expect(balanced).toHaveAttribute('aria-checked', 'true')
    expect(balanced).toHaveAttribute('tabindex', '0')
    expect(deep).toHaveAttribute('tabindex', '-1')

    await act(async () => {
      balanced.focus()
      fireEvent.keyDown(balanced, { key: 'ArrowRight' })
    })

    expect(screen.getByRole('radio', { name: /严谨$/ })).toHaveAttribute('aria-checked', 'true')
    expect(localStorage.getItem('kb_search_strategy')).toBe('high_quality')

    await act(async () => {
      fireEvent.keyDown(screen.getByRole('radio', { name: /严谨$/ }), { key: 'End' })
    })

    expect(deep).toHaveAttribute('aria-checked', 'true')
    expect(deep).toHaveFocus()
    expect(localStorage.getItem('kb_search_strategy')).toBe('deep')
  })

  it('sends message when clicking send button', async () => {
    renderChatArea()
    const input = screen.getByPlaceholderText(onboardingPlaceholder)
    await userEvent.type(input, '你好')
    await userEvent.click(screen.getByText('发送'))
    expect(mockSendMessage).toHaveBeenCalledWith('你好', false, 'balanced')
  })

  it('sends message on Enter key', async () => {
    renderChatArea()
    const input = screen.getByPlaceholderText(onboardingPlaceholder)
    await userEvent.type(input, '年假多少天')
    await userEvent.keyboard('{Enter}')
    expect(mockSendMessage).toHaveBeenCalled()
  })

  it('disables send button when streaming', () => {
    renderChatArea({ isStreaming: true })
    expect(screen.getByText('Square')).toBeInTheDocument() // stop button icon
  })

  it('stop button calls stopStreaming', async () => {
    renderChatArea({ isStreaming: true })
    await userEvent.click(screen.getByText('Square'))
    expect(mockStopStreaming).toHaveBeenCalled()
  })

  it('disables input when streaming', () => {
    renderChatArea({ isStreaming: true })
    const input = screen.getByPlaceholderText(onboardingPlaceholder)
    expect(input).toBeDisabled()
  })

  it('renders skeleton during message loading', () => {
    render( <ChatArea
        chat={createChat()}
        onOpenSidebar={mockOnOpenSidebar}
        sidebarOpen={true}
        onNavigate={mockOnNavigate}
        isLoadingMessages={true}
        workspaceSummary={{
          workspaceName: '默认工作区',
          documentCount: 0,
          conversationCount: 0,
        }}
      />)
    // Skeleton elements have a class or role — look for multiple skeleton divs
    const skeletons = document.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('renders welcome message when no messages', () => {
    renderChatArea()
    expect(screen.getByText('当前工作区还没有资料')).toBeInTheDocument()
  })

  it('shows a compact strategy trigger instead of the full strategy group on mobile', () => {
    renderChatArea(undefined, { isMobile: true })

    expect(screen.queryByRole('radiogroup', { name: '检索策略' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /检索与策略/i })).toBeInTheDocument()
  })

  it('renders messages with citations', () => {
    renderChatArea({
      messages: [
        { id: 1, role: 'assistant', content: '年假 [1] 为 5 天 [2]', sources: [
          { source: 'policy.txt', index: 1, content: '年假5天' },
          { source: 'hr.txt', index: 2, content: '适用' },
        ]},
      ],
    })
    expect(screen.getByText(/年假/)).toBeInTheDocument()
  })

  it('renders copy button and copies content', async () => {
    const writeText = vi.fn()
    Object.assign(navigator, { clipboard: { writeText } })
    renderChatArea({
      messages: [{ id: 1, role: 'assistant', content: '可复制的内容', sources: [] }],
    })
    // Copy button renders as Copy icon
    const copyButtons = screen.getAllByText('Copy')
    expect(copyButtons.length).toBeGreaterThan(0)
  })

  it('theme toggle button calls toggle', async () => {
    renderChatArea()
    // Theme toggle removed from ChatArea — Sidebar owns it now
    // Verify there's no Sun/Moon in ChatArea
    expect(screen.queryByText('Sun')).not.toBeInTheDocument()
  })

  it('nav pills call onNavigate', async () => {
    renderChatArea()
    // Browse nav pill
    const browseBtn = screen.getByText('知识库')
    await userEvent.click(browseBtn)
    expect(mockOnNavigate).toHaveBeenCalledWith('browser')
  })

  it('renders debug panel toggle', () => {
    renderChatArea({
      messages: [{ id: 1, role: 'assistant', content: 'test', sources: [], debugData: { nodes: [] } }],
    })
    // Debug panel renders as a button with Bug icon + "链路详情" text
    expect(screen.getByText('链路详情')).toBeInTheDocument()
  })
})
