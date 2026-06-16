import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Sidebar from '@/components/Sidebar'
import { useConversations, useSources } from '@/hooks/useData'
import * as api from '@/lib/api'
import { mockConversations, mockSources, mockKBStats } from '@/test/mocks/data'

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

// Mock sonner
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

// Mock lucide-react
vi.mock('lucide-react', () => {
  const icons: Record<string, string> = {
    MessageSquare: 'MessageSquare', Plus: 'Plus', Trash2: 'Trash2',
    BookOpen: 'BookOpen', BarChart3: 'BarChart3', PanelRightClose: 'PanelRightClose',
    Pencil: 'Pencil', Check: 'Check', X: 'X', Upload: 'Upload', Globe: 'Globe',
    FileText: 'FileText',
  }
  return Object.fromEntries(
    Object.keys(icons).map((name) => [name, () => <span>{name}</span>])
  )
})

vi.mock('@/hooks/useData', () => ({
  useConversations: vi.fn(),
  useSources: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  getMessages: vi.fn().mockResolvedValue([]),
  uploadDocument: vi.fn(),
  ingestUrl: vi.fn(),
  clearKnowledgeBase: vi.fn(),
  deleteSource: vi.fn(),
  getKBStats: vi.fn(),
}))

const defaultProps = {
  chat: { messages: [] as any[], loadMessages: vi.fn(), clearMessages: vi.fn() },
  activeView: 'chat' as const,
  onNavigate: vi.fn(),
  onClose: vi.fn(),
  convRefreshKey: 0,
  activeThreadId: null,
}

describe('Sidebar interactions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useConversations).mockReturnValue({
      conversations: mockConversations,
      activeId: 'conv-1',
      setActiveId: vi.fn(),
      create: vi.fn().mockResolvedValue({ id: 'new-id' }),
      remove: vi.fn(),
      rename: vi.fn(),
      refresh: vi.fn().mockResolvedValue(mockConversations),
      loading: false,
    })
    vi.mocked(useSources).mockReturnValue({
      sources: mockSources,
      refresh: vi.fn(),
    })
    vi.mocked(api.getKBStats).mockResolvedValue(mockKBStats)
  })

  it('clicking 新对话 button clears messages', async () => {
    const clearMessages = vi.fn()
    const setActiveId = vi.fn()
    vi.mocked(useConversations).mockReturnValue({
      conversations: mockConversations,
      activeId: 'conv-1', setActiveId,
      create: vi.fn().mockResolvedValue({ id: 'new-id' }),
      remove: vi.fn(), rename: vi.fn(),
      refresh: vi.fn().mockResolvedValue(mockConversations), loading: false,
    })

    render(<Sidebar {...defaultProps} chat={{ ...defaultProps.chat, clearMessages }} />)
    await userEvent.click(screen.getByText('新对话'))
    expect(clearMessages).toHaveBeenCalled()
  })

  it('conversation delete button calls remove', async () => {
    const remove = vi.fn()
    vi.mocked(useConversations).mockReturnValue({
      conversations: mockConversations, activeId: 'conv-1', setActiveId: vi.fn(),
      create: vi.fn(), remove, rename: vi.fn(),
      refresh: vi.fn().mockResolvedValue(mockConversations), loading: false,
    })

    render(<Sidebar {...defaultProps} />)
    const trashButtons = screen.getAllByText('Trash2')
    await userEvent.click(trashButtons[0])
    expect(remove).toHaveBeenCalled()
  })

  it('shows 暂无对话 when empty', () => {
    vi.mocked(useConversations).mockReturnValue({
      conversations: [], activeId: null, setActiveId: vi.fn(),
      create: vi.fn(), remove: vi.fn(), rename: vi.fn(),
      refresh: vi.fn().mockResolvedValue([]), loading: false,
    })
    render(<Sidebar {...defaultProps} />)
    expect(screen.getByText('暂无对话')).toBeInTheDocument()
  })

  it('in dashboard view shows hint text', () => {
    render(<Sidebar {...defaultProps} activeView="dashboard" />)
    expect(screen.getByText('打开指标面板查看详情')).toBeInTheDocument()
  })

  it('navigation buttons call onNavigate', async () => {
    const onNavigate = vi.fn()
    render(<Sidebar {...defaultProps} onNavigate={onNavigate} />)
    await userEvent.click(screen.getByText('知识库'))
    expect(onNavigate).toHaveBeenCalledWith('browser')
  })

  it('shows KB stats in browser view', async () => {
    await act(async () => {
      render(<Sidebar {...defaultProps} activeView="browser" />)
    })
    expect(screen.getByText('150')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('toggles between 对话 and 文档 tabs', async () => {
    render(<Sidebar {...defaultProps} />)
    // Tab buttons
    const docTab = screen.getByText('文档')
    await userEvent.click(docTab)
    // Doc tab active — upload area visible
    expect(screen.getByText('Upload')).toBeInTheDocument()
  })
})
