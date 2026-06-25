import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Sidebar from '@/components/Sidebar'
import { useConversations, useSources, useWorkspaces } from '@/hooks/useData'
import * as api from '@/lib/api'
import { mockConversations, mockSources, mockKBStats } from '@/test/mocks/data'

// Mock framer-motion (Sidebar doesn't use framer-motion directly, but KBSummary might)
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

// Mock lucide-react icons used by Sidebar
vi.mock('lucide-react', () => {
  const icons: Record<string, string> = {
    MessageSquare: 'MessageSquare',
    Plus: 'Plus',
    Trash2: 'Trash2',
    BookOpen: 'BookOpen',
    BarChart3: 'BarChart3',
    PanelRightClose: 'PanelRightClose',
    Pencil: 'Pencil',
    Check: 'Check',
    X: 'X',
    Upload: 'Upload',
    Globe: 'Globe',
    FileText: 'FileText',
    Loader2: 'Loader2',
  }
  return Object.fromEntries(
    Object.keys(icons).map((name) => [name, () => <span>{name}</span>])
  )
})

// Mock hooks
vi.mock('@/hooks/useData', () => ({
  useConversations: vi.fn(),
  useSources: vi.fn(),
  useWorkspaces: vi.fn(),
}))

// Mock api
vi.mock('@/lib/api', () => ({
  getMessages: vi.fn().mockResolvedValue([]),
  uploadDocument: vi.fn(),
  ingestUrl: vi.fn(),
  clearKnowledgeBase: vi.fn(),
  deleteSource: vi.fn(),
  getKBStats: vi.fn(),
}))

const defaultProps = {
  chat: {
    messages: [] as any[],
    loadMessages: vi.fn(),
    clearMessages: vi.fn(),
    sendMessage: vi.fn(),
  },
  activeView: 'chat' as const,
  onNavigate: vi.fn(),
  onClose: vi.fn(),
  convRefreshKey: 0,
  activeThreadId: null,
}

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(useConversations).mockReturnValue({
      conversations: mockConversations,
      activeId: 'conv-1',
      setActiveId: vi.fn(),
      create: vi.fn(),
      remove: vi.fn(),
      rename: vi.fn(),
      refresh: vi.fn().mockResolvedValue(mockConversations),
      loading: false,
    })

    vi.mocked(useWorkspaces).mockReturnValue({
      workspaces: [{ id: 'ws-1', name: '默认工作区', description: '', created_at: '', updated_at: '' }],
      activeWorkspaceId: 'ws-1',
      setActiveWorkspaceId: vi.fn(),
      create: vi.fn(),
      remove: vi.fn(),
      rename: vi.fn(),
      refresh: vi.fn(),
      loading: false,
    })

    vi.mocked(useSources).mockReturnValue({
      sources: mockSources,
      sourceError: null,
      refresh: vi.fn(),
    })

    vi.mocked(api.getKBStats).mockResolvedValue(mockKBStats)
  })

  it('renders the "K" logo and "KnowBase" title', () => {
    render(<Sidebar {...defaultProps} />)

    expect(screen.getByText('K')).toBeInTheDocument()
    expect(screen.getByText('KnowBase')).toBeInTheDocument()
    expect(screen.getByText('RAG Assistant')).toBeInTheDocument()
  })

  it('renders 3 navigation buttons: 对话, 工作区, 指标', () => {
    render(<Sidebar {...defaultProps} />)

    // Nav buttons: there are 3 nav items: 对话, 工作区, 指标
    // "对话" also appears in the tab toggle at the bottom, so use getAllByText
    expect(screen.getAllByText('对话')[0]).toBeInTheDocument()
    expect(screen.getByText('工作区')).toBeInTheDocument()
    expect(screen.getByText('指标')).toBeInTheDocument()
  })

  it('shows conversation list from useConversations', () => {
    render(<Sidebar {...defaultProps} />)

    expect(screen.getByText('测试对话')).toBeInTheDocument()
    expect(screen.getByText('关于 LLM 的讨论')).toBeInTheDocument()
  })

  it('shows "暂无对话" when conversations empty', () => {
    vi.mocked(useConversations).mockReturnValue({
      conversations: [],
      activeId: null,
      setActiveId: vi.fn(),
      create: vi.fn(),
      remove: vi.fn(),
      rename: vi.fn(),
      refresh: vi.fn().mockResolvedValue([]),
      loading: false,
    })

    render(<Sidebar {...defaultProps} />)

    expect(screen.getByText('暂无对话')).toBeInTheDocument()
  })

  it('in browser view, shows KBSummary with chunk/source labels', async () => {
    vi.mocked(api.getKBStats).mockResolvedValue(mockKBStats)

    await act(async () => {
      render(<Sidebar {...defaultProps} activeView="browser" />)
    })

    // KBSummary renders "片段" and "来源" labels
    expect(screen.getByText('段落')).toBeInTheDocument()
    expect(screen.getByText('引用文档')).toBeInTheDocument()
    expect(screen.getByText('150')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('in dashboard view, shows hint text', () => {
    render(<Sidebar {...defaultProps} activeView="dashboard" />)

    expect(screen.getByText('打开指标面板查看详情')).toBeInTheDocument()
  })

  it('clicking 新对话 button clears messages and navigates to chat', async () => {
    const onNavigate = vi.fn()
    const clearMessages = vi.fn()
    const setActiveId = vi.fn()

    vi.mocked(useConversations).mockReturnValue({
      conversations: mockConversations,
      activeId: 'conv-1',
      setActiveId,
      create: vi.fn(),
      remove: vi.fn(),
      rename: vi.fn(),
      refresh: vi.fn().mockResolvedValue(mockConversations),
      loading: false,
    })

    render(
      <Sidebar
        {...defaultProps}
        onNavigate={onNavigate}
        chat={{ ...defaultProps.chat, clearMessages }}
      />
    )

    await userEvent.click(screen.getByText('新对话'))
    expect(clearMessages).toHaveBeenCalled()
    expect(setActiveId).toHaveBeenCalledWith(null)
    expect(onNavigate).toHaveBeenCalledWith('chat')
  })
})
