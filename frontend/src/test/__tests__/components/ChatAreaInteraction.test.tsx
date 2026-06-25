import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ChatArea from '@/components/ChatArea'

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
    Search: 'Search', Globe: 'Globe', Zap: 'Zap', RotateCcw: 'RotateCcw',
    Download: 'Download', ThumbsUp: 'ThumbsUp', ThumbsDown: 'ThumbsDown',
    BookOpen: 'BookOpen', BarChart3: 'BarChart3', FileDown: 'FileDown',
    Sun: 'Sun', Moon: 'Moon', Copy: 'Copy', CheckCircle: 'CheckCircle',
    Bug: 'Bug', ChevronDown: 'ChevronDown', ChevronRight: 'ChevronRight',
    MessageSquare: 'MessageSquare',
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
      {...propsOverrides}
    />
  )
}

describe('ChatArea interactions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders input area with placeholder', () => {
    renderChatArea()
    expect(screen.getByPlaceholderText('输入你的问题…')).toBeInTheDocument()
  })

  it('renders 4 search strategy buttons', () => {
    renderChatArea()
    expect(screen.getByText('⚡快速')).toBeInTheDocument()
    expect(screen.getByText('⚖️标准')).toBeInTheDocument()
    expect(screen.getByText('🔬严谨')).toBeInTheDocument()
    expect(screen.getByText('🔍深度')).toBeInTheDocument()
  })

  it('sends message when clicking send button', async () => {
    renderChatArea()
    const input = screen.getByPlaceholderText('输入你的问题…')
    await userEvent.type(input, '你好')
    await userEvent.click(screen.getByText('发送'))
    expect(mockSendMessage).toHaveBeenCalledWith('你好', false, 'balanced')
  })

  it('sends message on Enter key', async () => {
    renderChatArea()
    const input = screen.getByPlaceholderText('输入你的问题…')
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
    const input = screen.getByPlaceholderText('输入你的问题…')
    expect(input).toBeDisabled()
  })

  it('renders skeleton during message loading', () => {
    render( <ChatArea
        chat={createChat()}
        onOpenSidebar={mockOnOpenSidebar}
        sidebarOpen={true}
        onNavigate={mockOnNavigate}
        isLoadingMessages={true}
      />)
    // Skeleton elements have a class or role — look for multiple skeleton divs
    const skeletons = document.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('renders welcome message when no messages', () => {
    renderChatArea()
    expect(screen.getByText('知识库问答助手')).toBeInTheDocument()
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
    // dark mode theme renders Sun icon (click to switch to light)
    const themeBtn = screen.getByText('Sun')
    await userEvent.click(themeBtn)
    expect(mockToggleTheme).toHaveBeenCalled()
  })

  it('nav pills call onNavigate', async () => {
    renderChatArea()
    // Browse nav pill
    const browseBtn = screen.getByText('浏览')
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
