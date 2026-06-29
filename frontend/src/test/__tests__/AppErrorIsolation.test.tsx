import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '@/App'

vi.mock('@/components/Sidebar', () => ({
  default: () => <div data-testid="sidebar">Sidebar Mock</div>,
}))
vi.mock('@/components/ChatArea', () => ({
  default: () => {
    throw new Error('chat exploded')
  },
}))
vi.mock('@/components/BrowserPage', () => ({
  default: () => <div data-testid="browserpage">BrowserPage Mock</div>,
}))
vi.mock('@/components/DashboardPage', () => ({
  default: () => <div data-testid="dashboardpage">DashboardPage Mock</div>,
}))
vi.mock('@/components/SettingsPage', () => ({
  default: () => <div data-testid="settingspage">SettingsPage Mock</div>,
}))
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
    setWorkspaceId: vi.fn(),
  }),
}))

describe('App error isolation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.matchMedia = ((query: string) => ({
      matches: query === '(max-width: 767px)',
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })) as typeof window.matchMedia
  })

  it('keeps other views usable after a single view crashes', async () => {
    render(<App />)

    expect(screen.getByText('聊天组件异常，请刷新页面')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '知识库' }))

    expect(screen.getByTestId('browserpage')).toBeInTheDocument()
    expect(screen.queryByText('聊天组件异常，请刷新页面')).not.toBeInTheDocument()
  })
})
