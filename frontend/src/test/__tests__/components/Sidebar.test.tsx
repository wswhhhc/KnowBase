import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Sidebar from '@/components/Sidebar'

vi.mock('lucide-react', () => {
  const icons: Record<string, string> = {
    MessageSquare: 'MessageSquare',
    Plus: 'Plus',
    Trash2: 'Trash2',
    BookOpen: 'BookOpen',
    ClipboardList: 'ClipboardList',
    BarChart3: 'BarChart3',
    PanelRightClose: 'PanelRightClose',
    Sun: 'Sun',
    Moon: 'Moon',
    Pencil: 'Pencil',
    Check: 'Check',
    X: 'X',
    Upload: 'Upload',
    Globe: 'Globe',
    FileText: 'FileText',
    Loader2: 'Loader2',
    Settings: 'Settings',
    Bookmark: 'Bookmark',
    Search: 'Search',
    Tag: 'Tag',
    BookmarkCheck: 'BookmarkCheck',
    ChevronDown: 'ChevronDown',
    ChevronRight: 'ChevronRight',
  }
  return Object.fromEntries(
    Object.keys(icons).map((name) => [name, () => <span>{name}</span>])
  )
})

const mockConversations = [
  { id: 'conv-1', thread_id: 'thread-1', title: '测试对话 1', created_at: '2024-01-01T00:00:00', updated_at: '2024-01-01T00:00:00', last_message_preview: '第一条摘要' },
  { id: 'conv-2', thread_id: 'thread-2', title: '测试对话 2', created_at: '2024-01-02T00:00:00', updated_at: '2024-01-02T00:00:00', last_message_preview: '第二条摘要' },
]

// Mock hooks
vi.mock('@/hooks/useData', () => ({
  useConversations: vi.fn(),
  useSources: vi.fn(),
  useWorkspaces: vi.fn(),
}))

vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ theme: 'dark', toggle: vi.fn() }),
}))

// Mock api
vi.mock('@/shared/api', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api')>('@/shared/api')
  return {
    ...actual,
    getMessages: vi.fn().mockResolvedValue([]),
    getConversationPinState: vi.fn().mockResolvedValue({ thread_id: 'thread-1', pinned_chunk_ids: [], excluded_chunk_ids: [] }),
    uploadDocument: vi.fn(),
    uploadDocumentStream: vi.fn(),
    ingestUrl: vi.fn(),
    ingestUrlStream: vi.fn(),
    clearKnowledgeBase: vi.fn(),
    deleteSource: vi.fn(),
    getKBStats: vi.fn(),
    queryLogs: vi.fn().mockResolvedValue([]),
  }
})

const { useConversations, useSources, useWorkspaces } = await import('@/hooks/useData')

const defaultProps = {
  chat: { messages: [] as any[], loadMessages: vi.fn(), clearMessages: vi.fn(), sendMessage: vi.fn(), threadId: null, workspaceId: 'ws-1' },
  activeView: 'chat' as const,
  onNavigate: vi.fn(),
  onClose: vi.fn(),
  convRefreshKey: 0,
  activeThreadId: null,
}

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks()

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

    vi.mocked(useConversations).mockReturnValue({
      conversations: mockConversations,
      activeId: 'conv-1',
      setActiveId: vi.fn(),
      rename: vi.fn(),
      create: vi.fn(),
      remove: vi.fn(),
      refresh: vi.fn().mockResolvedValue([]),
      loading: false,
    })

    vi.mocked(useSources).mockReturnValue({
      sources: [],
      sourceError: null,
      refresh: vi.fn(),
    })
  })

  it('renders the "K" logo and "KnowBase" title', () => {
    render(<Sidebar {...defaultProps} />)
    expect(screen.getByText('K')).toBeInTheDocument()
    expect(screen.getByText('KnowBase')).toBeInTheDocument()
  })

  it('renders 4 navigation buttons: 对话, 知识库, 指标, 设置', () => {
    render(<Sidebar {...defaultProps} />)
    const btns = screen.getAllByText('对话')
    expect(btns.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('知识库')).toBeInTheDocument()
    expect(screen.getByText('指标')).toBeInTheDocument()
    expect(screen.getByText('设置')).toBeInTheDocument()
  })

  it('hides admin panels and workspace management when the user lacks admin rights', () => {
    render(<Sidebar {...defaultProps} canManageApp={false} canManageWorkspaces={false} />)

    expect(screen.getByText('知识库')).toBeInTheDocument()
    expect(screen.queryByText('指标')).not.toBeInTheDocument()
    expect(screen.queryByText('设置')).not.toBeInTheDocument()
    expect(screen.queryByTitle('创建工作区')).not.toBeInTheDocument()
    expect(screen.queryByTitle('删除工作区')).not.toBeInTheDocument()
  })

  it('shows conversation list from useConversations', async () => {
    render(<Sidebar {...defaultProps} />)
    await waitFor(() => {
      expect(screen.getByText('测试对话 1')).toBeInTheDocument()
    })
  })

  it('shows "暂无对话" when conversations empty', () => {
    vi.mocked(useConversations).mockReturnValue({
      conversations: [],
      activeId: null,
      setActiveId: vi.fn(),
      rename: vi.fn(),
      create: vi.fn(),
      remove: vi.fn(),
      refresh: vi.fn().mockResolvedValue([]),
      loading: false,
    })
    render(<Sidebar {...defaultProps} />)
    expect(screen.getByText('暂无对话')).toBeInTheDocument()
  })

  it('clicking 新对话 button clears messages and navigates to chat', async () => {
    const onNavigate = vi.fn()
    const chat = { messages: [{ role: 'user', content: 'hi' }], loadMessages: vi.fn(), clearMessages: vi.fn(), sendMessage: vi.fn(), threadId: null, workspaceId: 'ws-1' }
    render(<Sidebar {...defaultProps} chat={chat as any} onNavigate={onNavigate} />)
    const newBtn = screen.getByText('新对话')
    await userEvent.click(newBtn)
    expect(chat.clearMessages).toHaveBeenCalled()
    expect(onNavigate).toHaveBeenCalledWith('chat')
  })

  it('renders the default workspace when its id is an empty string', () => {
    vi.mocked(useWorkspaces).mockReturnValue({
      workspaces: [{ id: '', name: '默认工作区', description: '', created_at: '', updated_at: '' }],
      activeWorkspaceId: '',
      setActiveWorkspaceId: vi.fn(),
      create: vi.fn(),
      remove: vi.fn(),
      rename: vi.fn(),
      refresh: vi.fn(),
      loading: false,
    })

    render(<Sidebar {...defaultProps} />)

    expect(screen.getByText('默认工作区')).toBeInTheDocument()
    expect(screen.getByText('知识库')).toBeInTheDocument()
  })
})
