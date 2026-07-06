import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from '@/app/App'

const mockLogin = vi.fn()

const mockChat = {
  messages: [],
  isStreaming: false,
  streamingNodes: [],
  sendMessage: vi.fn(),
  stopStreaming: vi.fn(),
  clearMessages: vi.fn(),
  loadMessages: vi.fn(),
  threadId: null,
  workspaceId: '',
  setWorkspaceId: vi.fn(),
}

// Mock all child components as they are tested independently
vi.mock('@/components/Sidebar', () => ({
  default: (props: any) => (
    <div data-testid="sidebar">
      <button onClick={() => props.onWorkspaceSummaryChange?.({ workspaceName: 'Alpha', documentCount: 2, conversationCount: 1 })}>
        sync-summary
      </button>
      <button onClick={() => props.onWorkspaceChange?.('ws-2')}>switch-workspace</button>
      <button onClick={() => props.onNavigate?.('browser')}>知识库</button>
      Sidebar Mock
    </div>
  ),
}))
vi.mock('@/pages/chat/ChatPage', () => ({
  default: (props: any) => (
    <div data-testid="chatarea">
      ChatArea Mock {props.workspaceSummary.workspaceName}:{props.workspaceSummary.documentCount}:{props.workspaceSummary.conversationCount}
    </div>
  ),
}))
vi.mock('@/pages/browser/BrowserPage', async () => {
  const React = await import('react')
  return {
    default: (props: any) => {
      const [uploadEvents, setUploadEvents] = React.useState(0)
      React.useEffect(() => {
        const handleTrigger = () => setUploadEvents((count) => count + 1)
        window.addEventListener('kb-trigger-upload', handleTrigger)
        return () => window.removeEventListener('kb-trigger-upload', handleTrigger)
      }, [])
      return <div data-testid="browserpage">BrowserPage Mock workspace:{props.workspaceId} upload-events:{uploadEvents}</div>
    },
  }
})
vi.mock('@/pages/dashboard/DashboardPage', () => ({
  default: (props: any) => <div data-testid="dashboardpage">DashboardPage Mock</div>,
}))
vi.mock('@/pages/settings/SettingsPage', () => ({
  default: (props: any) => <div data-testid="settingspage">SettingsPage Mock</div>,
}))

// Mock hooks
vi.mock('@/hooks/useChat', () => ({
  useChat: () => mockChat,
}))
vi.mock('@/hooks/useData', () => ({
  useConversations: () => ({
    conversations: [], activeId: null, setActiveId: vi.fn(),
    create: vi.fn(), remove: vi.fn(), rename: vi.fn(),
    refresh: vi.fn(), loading: false,
  }),
  useSources: () => ({ sources: [], refresh: vi.fn() }),
}))
vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ theme: 'dark', toggle: vi.fn() }),
}))
vi.mock('@/shared/api/auth', () => ({
  login: (...args: unknown[]) => mockLogin(...args),
}))

describe('App component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
    mockChat.workspaceId = ''
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
    })
  })

  it('shows login page when no JWT session or legacy API key exists', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'KnowBase' })).toBeInTheDocument()
    expect(screen.getByLabelText('用户名')).toBeInTheDocument()
    expect(screen.queryByTestId('sidebar')).not.toBeInTheDocument()
  })

  it('logs in and renders the workspace shell', async () => {
    mockLogin.mockResolvedValue({
      access_token: 'access-token',
      refresh_token: 'refresh-token',
      token_type: 'bearer',
      expires_in: 1800,
      user: {
        id: 'user-1',
        username: 'admin',
        role: 'admin',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    })

    render(<App />)

    await userEvent.type(screen.getByLabelText('用户名'), 'admin')
    await userEvent.type(screen.getByLabelText('密码'), 'admin-pass')
    await userEvent.click(screen.getByRole('button', { name: '登录' }))

    expect(await screen.findByTestId('sidebar')).toBeInTheDocument()
    expect(localStorage.getItem('knowbase_access_token')).toBe('access-token')
  })

  it('renders Sidebar and ChatArea when a legacy API key is configured', async () => {
    localStorage.setItem('knowbase_api_key', 'legacy-key')
    render(<App />)
    expect(screen.getByTestId('sidebar')).toBeInTheDocument()
    expect(await screen.findByTestId('chatarea')).toBeInTheDocument()
  })

  it('clears chat state and refreshes workspace-scoped props when the workspace changes', async () => {
    localStorage.setItem('knowbase_api_key', 'legacy-key')
    render(<App />)

    expect(await screen.findByTestId('chatarea')).toBeInTheDocument()
    await userEvent.click(screen.getByText('sync-summary'))
    expect(screen.getByTestId('chatarea')).toHaveTextContent('Alpha:2:1')

    await userEvent.click(screen.getByText('switch-workspace'))

    expect(mockChat.clearMessages).toHaveBeenCalled()
    expect(mockChat.setWorkspaceId).toHaveBeenCalledWith('ws-2')

    await userEvent.click(screen.getAllByText('知识库')[0])
    expect(await screen.findByTestId('browserpage')).toHaveTextContent('workspace:ws-2')
  })

  it('dispatches the upload trigger when the mobile FAB is clicked on the browser view', async () => {
    localStorage.setItem('knowbase_api_key', 'legacy-key')
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: query === '(max-width: 767px)',
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
    })

    render(<App />)

    await userEvent.click(screen.getAllByText('知识库')[0])
    expect(await screen.findByTestId('browserpage')).toHaveTextContent('upload-events:0')

    await userEvent.click(screen.getByTitle('上传文档'))

    await waitFor(() => {
      expect(screen.getByTestId('browserpage')).toHaveTextContent('upload-events:1')
    })
    expect(sessionStorage.getItem('kb_trigger_upload')).toBe('true')
  })

  it('hides the mobile upload FAB outside the browser view', async () => {
    localStorage.setItem('knowbase_api_key', 'legacy-key')
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: query === '(max-width: 767px)',
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
    })

    render(<App />)

    expect(await screen.findByTestId('chatarea')).toBeInTheDocument()
    expect(screen.queryByTitle('上传文档')).not.toBeInTheDocument()
  })

  it('logs out and returns to the login page', async () => {
    localStorage.setItem('knowbase_access_token', 'access-token')
    localStorage.setItem('knowbase_refresh_token', 'refresh-token')
    localStorage.setItem('knowbase_auth_user', JSON.stringify({
      id: 'user-1',
      username: 'admin',
      role: 'admin',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }))

    render(<App />)

    expect(await screen.findByTestId('sidebar')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '退出登录' }))

    expect(screen.getByLabelText('用户名')).toBeInTheDocument()
    expect(localStorage.getItem('knowbase_access_token')).toBeNull()
  })
})
