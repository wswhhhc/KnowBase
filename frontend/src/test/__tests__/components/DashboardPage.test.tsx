import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DashboardPage from '@/components/DashboardPage'
import * as api from '@/lib/api'
import { mockQueryLogs } from '@/test/mocks/data'

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

// Mock lucide-react icons used by DashboardPage
vi.mock('lucide-react', () => {
  const icons: Record<string, string> = {
    BarChart3: 'BarChart3',
    PanelRightOpen: 'PanelRightOpen',
    ArrowLeft: 'ArrowLeft',
    TrendingUp: 'TrendingUp',
    Clock: 'Clock',
    CheckCircle2: 'CheckCircle2',
    XCircle: 'XCircle',
    HelpCircle: 'HelpCircle',
    AlertTriangle: 'AlertTriangle',
    Sun: 'Sun',
    Moon: 'Moon',
    Globe: 'Globe',
    ChevronDown: 'ChevronDown',
    ChevronUp: 'ChevronUp',
    X: 'X',
    DollarSign: 'DollarSign',
  }
  return Object.fromEntries(
    Object.keys(icons).map((name) => [name, () => <span>{name}</span>])
  )
})

// Mock api
vi.mock('@/lib/api', () => ({
  queryLogs: vi.fn(),
}))

const defaultProps = {
  onOpenSidebar: vi.fn(),
  sidebarOpen: false,
  onNavigate: vi.fn(),
  theme: { theme: 'dark' as const, toggle: vi.fn() },
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.queryLogs).mockResolvedValue({
      logs: mockQueryLogs,
      total_cost: 0.006,
      total_tokens: 12000,
      total_prompt_tokens: 8000,
      total_completion_tokens: 4000,
    })
  })

  it('renders the "指标面板" title', async () => {
    await act(async () => {
      render(<DashboardPage {...defaultProps} />)
    })
    expect(screen.getByText('指标面板')).toBeInTheDocument()
  })

  it('renders stat cards', async () => {
    await act(async () => {
      render(<DashboardPage {...defaultProps} />)
    })

    await waitFor(() => {
      expect(screen.getByText('总查询')).toBeInTheDocument()
    })
    expect(screen.getByText('平均耗时')).toBeInTheDocument()
    expect(screen.getByText('质量通过率')).toBeInTheDocument()
    expect(screen.getByText('总 Token 消耗')).toBeInTheDocument()
    expect(screen.getByText('Token 估算')).toBeInTheDocument()
    expect(screen.getByText('<¥0.01')).toBeInTheDocument()
    expect(screen.getByText(/输入 8,000 \/ 输出 4,000/)).toBeInTheDocument()
  })

  it('prefers backend total cost summary when provided', async () => {
    vi.mocked(api.queryLogs).mockResolvedValue({
      logs: mockQueryLogs,
      total_cost: 1.23,
    } as any)

    await act(async () => {
      render(<DashboardPage {...defaultProps} />)
    })

    await waitFor(() => {
      expect(screen.getByText('¥1.23')).toBeInTheDocument()
    })
  })

  it('renders time range buttons', async () => {
    await act(async () => {
      render(<DashboardPage {...defaultProps} />)
    })

    await waitFor(() => {
      expect(screen.getByText('近1天')).toBeInTheDocument()
    })
    expect(screen.getByText('近7天')).toBeInTheDocument()
    expect(screen.getByText('近30天')).toBeInTheDocument()
  })

  it('renders query log table with question text and token columns', async () => {
    await act(async () => {
      render(<DashboardPage {...defaultProps} />)
    })

    // "你好" appears in both the recent queries list and the logs table
    await waitFor(() => {
      expect(screen.getAllByText('你好').length).toBeGreaterThanOrEqual(1)
    })
    // New token and cost columns
    expect(screen.getByText('Token')).toBeInTheDocument()
    expect(screen.getByText('费用')).toBeInTheDocument()
    expect(screen.getByText('¥0.0060')).toBeInTheDocument()
  })

  it('back button calls onNavigate(\'chat\')', async () => {
    const onNavigate = vi.fn()

    await act(async () => {
      render(<DashboardPage {...defaultProps} onNavigate={onNavigate} />)
    })

    await waitFor(() => {
      expect(screen.getByText('返回')).toBeInTheDocument()
    })

    await userEvent.click(screen.getByText('返回'))
    expect(onNavigate).toHaveBeenCalledWith('chat')
  })

  it('shows "暂无查询数据" when logs empty', async () => {
    vi.mocked(api.queryLogs).mockResolvedValue({
      logs: [],
      total_cost: 0,
      total_tokens: 0,
      total_prompt_tokens: 0,
      total_completion_tokens: 0,
    })

    await act(async () => {
      render(<DashboardPage {...defaultProps} />)
    })

    await waitFor(() => {
      expect(screen.getByText('暂无查询数据')).toBeInTheDocument()
    })
  })

  it('re-fetches data when time range changes', async () => {
    await act(async () => {
      render(<DashboardPage {...defaultProps} />)
    })

    await waitFor(() => {
      expect(screen.getByText('近7天')).toBeInTheDocument()
    })

    await userEvent.click(screen.getByText('近1天'))

    expect(api.queryLogs).toHaveBeenCalledWith(1, 1000)
  })
})
