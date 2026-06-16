import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from '@/App'

// Mock all child components as they are tested independently
vi.mock('@/components/Sidebar', () => ({
  default: (props: any) => <div data-testid="sidebar">Sidebar Mock</div>,
}))
vi.mock('@/components/ChatArea', () => ({
  default: (props: any) => <div data-testid="chatarea">ChatArea Mock</div>,
}))
vi.mock('@/components/BrowserPage', () => ({
  default: (props: any) => <div data-testid="browserpage">BrowserPage Mock</div>,
}))
vi.mock('@/components/DashboardPage', () => ({
  default: (props: any) => <div data-testid="dashboardpage">DashboardPage Mock</div>,
}))

// Mock hooks
vi.mock('@/hooks/useChat', () => ({
  useChat: () => ({
    messages: [], isStreaming: false, streamingNodes: [],
    sendMessage: vi.fn(), stopStreaming: vi.fn(),
    clearMessages: vi.fn(), loadMessages: vi.fn(), threadId: null,
  }),
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

describe('App component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders Sidebar and ChatArea by default', () => {
    render(<App />)
    expect(screen.getByTestId('sidebar')).toBeInTheDocument()
    expect(screen.getByTestId('chatarea')).toBeInTheDocument()
  })
})
