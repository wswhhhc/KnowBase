import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Sidebar from '@/components/Sidebar'
import { useConversations, useSources, useWorkspaces } from '@/hooks/useData'
import * as api from '@/lib/api'
import { mockConversations, mockMessages, mockSources, mockKBStats } from '@/test/mocks/data'

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

// sonner 的 mock 引用（vi.mock 已提升到文件顶部，这里拿到的引用是安全可用的）
import { toast as sonnerToast } from 'sonner'

// Mock lucide-react
vi.mock('lucide-react', () => {
  const icons: Record<string, string> = {
    MessageSquare: 'MessageSquare', Plus: 'Plus', Trash2: 'Trash2',
    BookOpen: 'BookOpen', BarChart3: 'BarChart3', PanelRightClose: 'PanelRightClose',
    Pencil: 'Pencil', Check: 'Check', X: 'X', Upload: 'Upload', Globe: 'Globe',
    FileText: 'FileText', Loader2: 'Loader2', Sun: 'Sun', Moon: 'Moon', Settings: 'Settings',
    Bookmark: 'Bookmark', Search: 'Search', Tag: 'Tag',
    ChevronDown: 'ChevronDown', ChevronRight: 'ChevronRight',
  }
  return Object.fromEntries(
    Object.keys(icons).map((name) => [name, () => <span>{name}</span>])
  )
})

vi.mock('@/hooks/useData', () => ({
  useConversations: vi.fn(),
  useSources: vi.fn(),
  useWorkspaces: vi.fn(),
}))

vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ theme: 'dark', toggle: vi.fn() }),
}))

vi.mock('@/lib/api', () => ({
  getMessages: vi.fn().mockResolvedValue([]),
  uploadDocument: vi.fn(),
  uploadDocumentStream: vi.fn().mockImplementation((file, versionMode, callbacks) => {
    callbacks.onDone?.({ chunk_count: 5, existing_version: false })
    return { abort: vi.fn() }
  }),
  checkSource: vi.fn(),
  ingestUrl: vi.fn(),
  ingestUrlStream: vi.fn().mockImplementation((url, _mode, callbacks) => {
    callbacks.onDone?.({ chunk_count: 1, existing_version: false })
    return { abort: vi.fn() }
  }),
  clearKnowledgeBase: vi.fn(),
  deleteSource: vi.fn(),
  deleteConversations: vi.fn(),
  getKBStats: vi.fn(),
  queryLogs: vi.fn().mockResolvedValue([]),
}))

const defaultProps = {
  chat: { messages: [] as any[], loadMessages: vi.fn(), clearMessages: vi.fn(), sendMessage: vi.fn() },
  activeView: 'chat' as const,
  onNavigate: vi.fn(),
  onClose: vi.fn(),
  convRefreshKey: 0,
  activeThreadId: null,
}

describe('Sidebar interactions', () => {
  beforeEach(() => {
    vi.clearAllMocks()

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
      sourceError: null,
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

  it('closes the drawer on mobile when creating a new conversation', async () => {
    const onClose = vi.fn()
    render(<Sidebar {...defaultProps} onClose={onClose} isMobile />)
    await userEvent.click(screen.getByText('新对话'))
    expect(onClose).toHaveBeenCalled()
  })

  it('deleting the active conversation clears local chat state', async () => {
    const remove = vi.fn()
    const clearMessages = vi.fn()
    vi.mocked(useConversations).mockReturnValue({
      conversations: mockConversations, activeId: 'conv-1', setActiveId: vi.fn(),
      create: vi.fn(), remove, rename: vi.fn(),
      refresh: vi.fn().mockResolvedValue(mockConversations), loading: false,
    })

    render(<Sidebar {...defaultProps} chat={{ ...defaultProps.chat, clearMessages }} />)
    const trashButtons = screen.getAllByText('Trash2')
    await userEvent.click(trashButtons[0])
    // 确认弹窗出现，点击确认删除
    await userEvent.click(screen.getByText('确认删除'))
    expect(remove).toHaveBeenCalled()
    await waitFor(() => {
      expect(clearMessages).toHaveBeenCalled()
    })
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

  it('in dashboard view shows summary', async () => {
    await act(async () => {
      render(<Sidebar {...defaultProps} activeView="dashboard" />)
    })
    expect(screen.getByText('快速统计')).toBeInTheDocument()
    await waitFor(() => {
      expect(api.queryLogs).toHaveBeenCalledWith(7, 100)
    })
  })

  it('in settings view does not fall back to dashboard summary', () => {
    render(<Sidebar {...defaultProps} activeView="settings" />)
    expect(screen.queryByText('快速统计')).not.toBeInTheDocument()
    expect(screen.getByText('设置项将在主面板中编辑')).toBeInTheDocument()
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

  // ── 批量选择/删除测试 ──

  it('shows checkbox for each conversation', () => {
    render(<Sidebar {...defaultProps} />)
    const checkboxes = screen.getAllByRole('checkbox')
    // 全选 checkbox + 2 个对话 checkbox
    expect(checkboxes.length).toBe(3)
  })

  it('checking a conversation checkbox enables batch delete button', async () => {
    render(<Sidebar {...defaultProps} />)
    const checkboxes = screen.getAllByRole('checkbox')
    // 跳过全选 checkbox（index=0），勾选第一个对话
    await userEvent.click(checkboxes[1])
    // 批量删除按钮显示已选数量
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('select all checkbox toggles all conversations', async () => {
    render(<Sidebar {...defaultProps} />)
    const checkboxes = screen.getAllByRole('checkbox')
    // 全选 checkbox 是第一个
    await userEvent.click(checkboxes[0])
    // 批量删除按钮显示已选数量 = 对话总数
    expect(screen.getByText('2')).toBeInTheDocument()
    // 再点一下取消全选
    await userEvent.click(checkboxes[0])
    expect(screen.queryByText('2')).not.toBeInTheDocument()
  })

  it('batch delete calls deleteConversations with selected ids on success', async () => {
    vi.mocked(api.deleteConversations!).mockResolvedValue({ ok: true } as any)

    render(<Sidebar {...defaultProps} />)
    const checkboxes = screen.getAllByRole('checkbox')
    // 全选
    await userEvent.click(checkboxes[0])
    // 批量删除按钮显示已选数量，点击它
    await userEvent.click(screen.getByText('2'))
    // 确认弹窗出现，点击确认按钮
    await userEvent.click(screen.getByText('确认删除'))
    expect(api.deleteConversations).toHaveBeenCalledWith(['conv-1', 'conv-2'])
  })

  it('batch delete shows error toast on failure', async () => {
    vi.mocked(api.deleteConversations!).mockRejectedValue(new Error('网络错误'))

    render(<Sidebar {...defaultProps} />)
    const checkboxes = screen.getAllByRole('checkbox')
    await userEvent.click(checkboxes[0])
    await userEvent.click(screen.getByText('2'))
    // 确认弹窗出现，点击确认按钮
    await userEvent.click(screen.getByText('确认删除'))

    await waitFor(() => {
      expect(sonnerToast.error).toHaveBeenCalledWith('批量删除失败', expect.anything())
    })
  })

  it('switching conversation loads messages with convId and assistantMsgId', async () => {
    vi.mocked(api.getMessages).mockResolvedValue(mockMessages as any)
    const loadMessages = vi.fn()
    render(<Sidebar {...defaultProps} chat={{ ...defaultProps.chat, loadMessages }} />)
    await userEvent.click(screen.getAllByText('测试对话')[0])

    await waitFor(() => {
      expect(loadMessages).toHaveBeenCalled()
    })

    const loaded = loadMessages.mock.calls[0][0] as any[]
    // Each message should carry conversation.id as convId
    loaded.forEach((m: any) => {
      expect(m.convId).toBe('conv-1')
    })
    // Assistant messages should have assistantMsgId from the db row id
    const assistantMsgs = loaded.filter((m: any) => m.role === 'assistant')
    assistantMsgs.forEach((m: any) => {
      expect(m.assistantMsgId).toBeGreaterThan(0)
    })
  })

  it('closes the drawer on mobile when switching conversation', async () => {
    vi.mocked(api.getMessages).mockResolvedValue(mockMessages as any)
    const onClose = vi.fn()
    render(<Sidebar {...defaultProps} onClose={onClose} isMobile />)
    await userEvent.click(screen.getAllByText('测试对话')[0])

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled()
    })
  })

  // ── upload/ingest-url refresh 结果逻辑 ──

  it('upload document shows success toast only when refresh returns true', async () => {
    const refresh = vi.fn()
    vi.mocked(useSources).mockReturnValue({
      sources: mockSources, sourceError: null, refresh,
    })
    vi.mocked(api.uploadDocument).mockResolvedValue({ chunk_count: 5, existing_version: false })
    vi.mocked(api.checkSource).mockResolvedValue({ exists: false })
    refresh.mockResolvedValue(true)
    render(<Sidebar {...defaultProps} />)
    await userEvent.click(screen.getByText('文档'))
    const file = new File(['test'], 'test.txt', { type: 'text/plain' })
    const input = screen.getByLabelText(/选择文件/)
    await userEvent.upload(input, file)
    await waitFor(() => {
      expect(sonnerToast.success).toHaveBeenCalledWith('文档已上传', expect.anything())
    })
  })

  it('upload document skips success toast when refresh returns false', async () => {
    const refresh = vi.fn()
    vi.mocked(useSources).mockReturnValue({
      sources: mockSources, sourceError: null, refresh,
    })
    vi.mocked(api.uploadDocument).mockResolvedValue({ chunk_count: 5, existing_version: false })
    vi.mocked(api.checkSource).mockResolvedValue({ exists: false })
    refresh.mockResolvedValue(false)
    render(<Sidebar {...defaultProps} />)
    await userEvent.click(screen.getByText('文档'))
    const file = new File(['test'], 'test.txt', { type: 'text/plain' })
    const input = screen.getByLabelText(/选择文件/)
    await userEvent.upload(input, file)
    await waitFor(() => {
      expect(sonnerToast.success).not.toHaveBeenCalled()
    })
  })

  it('ingest url shows success toast only when refresh returns true', async () => {
    const refresh = vi.fn()
    vi.mocked(useSources).mockReturnValue({
      sources: mockSources, sourceError: null, refresh,
    })
    refresh.mockResolvedValue(true)
    render(<Sidebar {...defaultProps} />)
    await userEvent.click(screen.getByText('文档'))
    const input = screen.getByPlaceholderText('https://…')
    await userEvent.type(input, 'https://example.com')
    await userEvent.click(screen.getByText('Globe'))
    await waitFor(() => {
      expect(sonnerToast.success).toHaveBeenCalledWith('网页已导入')
    })
  })

  it('ingest url skips success toast when refresh returns false', async () => {
    const refresh = vi.fn()
    vi.mocked(useSources).mockReturnValue({
      sources: mockSources, sourceError: null, refresh,
    })
    refresh.mockResolvedValue(false)
    render(<Sidebar {...defaultProps} />)
    await userEvent.click(screen.getByText('文档'))
    const input = screen.getByPlaceholderText('https://…')
    await userEvent.type(input, 'https://example.com')
    await userEvent.click(screen.getByText('Globe'))
    await waitFor(() => {
      expect(sonnerToast.success).not.toHaveBeenCalled()
    })
  })

  it('duplicate upload can continue with replace mode after user confirms', async () => {
    const refresh = vi.fn().mockResolvedValue(true)
    vi.mocked(useSources).mockReturnValue({
      sources: mockSources, sourceError: null, refresh,
    })
    vi.mocked(api.checkSource).mockResolvedValue({ exists: true })

    render(<Sidebar {...defaultProps} />)
    await userEvent.click(screen.getByText('文档'))

    const file = new File(['test'], 'duplicate.txt', { type: 'text/plain' })
    const input = screen.getByLabelText(/选择文件/)
    await userEvent.upload(input, file)

    await waitFor(() => {
      expect(screen.getByText('该来源已存在，请选择操作方式')).toBeInTheDocument()
    })

    await userEvent.click(screen.getByText('替换为新版本（删除旧内容后重新导入）'))

    await waitFor(() => {
      expect(api.uploadDocumentStream).toHaveBeenCalledWith(
        expect.any(File),
        'replace',
        expect.objectContaining({
          onProgress: expect.any(Function),
          onDone: expect.any(Function),
          onError: expect.any(Function),
        }),
      )
    })
  })

  it('re-prompts version handling if the stream completion reports an existing source', async () => {
    const refresh = vi.fn().mockResolvedValue(true)
    vi.mocked(useSources).mockReturnValue({
      sources: mockSources, sourceError: null, refresh,
    })
    vi.mocked(api.checkSource).mockResolvedValue({ exists: false })
    vi.mocked(api.uploadDocumentStream).mockImplementationOnce((_file, _mode, callbacks) => {
      callbacks.onDone?.({ existing_version: true, chunk_count: 0 })
      return { abort: vi.fn() } as any
    })

    render(<Sidebar {...defaultProps} />)
    await userEvent.click(screen.getByText('文档'))

    const file = new File(['test'], 'duplicate.txt', { type: 'text/plain' })
    const input = screen.getByLabelText(/选择文件/)
    await userEvent.upload(input, file)

    await waitFor(() => {
      expect(screen.getByText('该来源已存在，请选择操作方式')).toBeInTheDocument()
    })
    expect(sonnerToast.success).not.toHaveBeenCalled()
  })
})
