import { render, screen, waitFor, act, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DashboardPage from '@/pages/dashboard/DashboardPage'
import * as api from '@/shared/api'
import { mockQueryLogs } from '@/test/mocks/data'

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { initial, animate, exit, transition, ...rest } = props
      return <div {...rest}>{children}</div>
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))
vi.mock('lucide-react', () => {
  const icons: Record<string, string> = {
    BarChart3: 'BarChart3', PanelRightOpen: 'PanelRightOpen', ArrowLeft: 'ArrowLeft',
    TrendingUp: 'TrendingUp', Clock: 'Clock', CheckCircle2: 'CheckCircle2',
    XCircle: 'XCircle', HelpCircle: 'HelpCircle', AlertTriangle: 'AlertTriangle',
    Sun: 'Sun', Moon: 'Moon', Globe: 'Globe', ChevronDown: 'ChevronDown',
    ChevronUp: 'ChevronUp', X: 'X', DollarSign: 'DollarSign',
  }
  return Object.fromEntries(Object.keys(icons).map((n) => [n, () => <span>{n}</span>]))
})
vi.mock('@/shared/api', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api')>('@/shared/api')
  return {
    ...actual,
    queryLogs: vi.fn(),
  }
})

const defaultProps = {
  onOpenSidebar: vi.fn(), sidebarOpen: false, onNavigate: vi.fn(),
  theme: { theme: 'dark' as const, toggle: vi.fn() },
}

describe('DashboardPage interactions', () => {
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

  it('stat cards display correct values', async () => {
    await act(async () => { render(<DashboardPage {...defaultProps} />) })

    await waitFor(() => {
      expect(screen.getByText('总查询')).toBeInTheDocument()
    })
    expect(screen.getByText('平均耗时')).toBeInTheDocument()
    expect(screen.getByText('质量通过率')).toBeInTheDocument()
    expect(screen.getByText('Token 估算')).toBeInTheDocument()
  })

  it('empty log state shows message', async () => {
    vi.mocked(api.queryLogs).mockResolvedValue({
      logs: [],
      total_cost: 0,
      total_tokens: 0,
      total_prompt_tokens: 0,
      total_completion_tokens: 0,
    })

    await act(async () => { render(<DashboardPage {...defaultProps} />) })

    await waitFor(() => {
      expect(screen.getByText('暂无查询数据')).toBeInTheDocument()
    })
  })

  it('re-fetches on time range change', async () => {
    await act(async () => { render(<DashboardPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('近7天')).toBeInTheDocument())

    await userEvent.click(screen.getByText('近1天'))
    expect(api.queryLogs).toHaveBeenCalledWith(1, 1000)
  })

  it('logs question appears in table', async () => {
    await act(async () => { render(<DashboardPage {...defaultProps} />) })

    await waitFor(() => {
      expect(screen.getAllByText('你好').length).toBeGreaterThanOrEqual(1)
    })
  })

  it('expands and collapses long logs while preserving error and formatting details', async () => {
    const logs = Array.from({ length: 16 }, (_, index) => ({
      ...mockQueryLogs[0],
      question: `查询 ${index}`,
      quality_ok: index !== 15,
      used_web_search: index === 15,
      elapsed_ms: index === 15 ? 2345 : 1500,
      retrieval_count: index === 15 ? 7 : 3,
      token_count: index === 15 ? 321 : 12000,
      estimated_cost: index === 15 ? 0.0123 : 0.006,
    }))
    vi.mocked(api.queryLogs).mockResolvedValue({ logs } as any)

    await act(async () => { render(<DashboardPage {...defaultProps} />) })
    const table = await screen.findByRole('table')
    expect(within(table).queryByText('查询 15')).not.toBeInTheDocument()

    await userEvent.click(screen.getByText('全部加载'))
    const errorQuestion = within(table).getByText('查询 15')
    const errorRow = errorQuestion.closest('tr')!
    expect(within(errorRow).getByText('✗ 失败')).toBeInTheDocument()
    expect(within(errorRow).getByText('Globe')).toBeInTheDocument()
    expect(within(errorRow).getByText('2345ms')).toBeInTheDocument()
    expect(within(errorRow).getByText('7')).toBeInTheDocument()
    expect(within(errorRow).getByText('321')).toBeInTheDocument()
    expect(within(errorRow).getByText('¥0.0123')).toBeInTheDocument()

    await userEvent.click(screen.getByText('收起'))
    expect(within(table).queryByText('查询 15')).not.toBeInTheDocument()
  })
})
