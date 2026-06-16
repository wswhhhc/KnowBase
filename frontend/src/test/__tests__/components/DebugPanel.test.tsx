import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DebugPanel from '@/components/DebugPanel'
import { mockDebugInfo } from '@/test/mocks/data'
import type { DebugInfo } from '@/lib/api'

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

// Mock lucide-react icons used by DebugPanel
vi.mock('lucide-react', () => ({
  Bug: 'Bug',
  ChevronDown: 'ChevronDown',
  ChevronRight: 'ChevronRight',
  Search: 'Search',
  Globe: 'Globe',
  RotateCcw: 'RotateCcw',
  Zap: 'Zap',
}))

describe('DebugPanel', () => {
  it('renders the toggle button', () => {
    render(<DebugPanel debugData={mockDebugInfo} />)

    expect(screen.getByText('链路详情')).toBeInTheDocument()
  })

  it('shows node timeline when expanded', async () => {
    const user = userEvent.setup()
    render(<DebugPanel debugData={mockDebugInfo} />)

    // Click to expand
    await user.click(screen.getByText('链路详情'))

    // Check that node labels are visible
    expect(screen.getByText('问题路由')).toBeInTheDocument()
    expect(screen.getByText('检索文档')).toBeInTheDocument()
  })

  it('shows quality passed status when quality_passed is true', async () => {
    const user = userEvent.setup()
    render(<DebugPanel debugData={mockDebugInfo} />)

    await user.click(screen.getByText('链路详情'))

    // Since quality_passed is true, we should NOT see the failure message
    expect(screen.queryByText(/质量检查未通过/)).not.toBeInTheDocument()
  })

  it('shows quality failure message when quality_passed is false', async () => {
    const failedDebug: DebugInfo = {
      ...mockDebugInfo,
      quality_passed: false,
      quality_reason: '回答不完整',
    }

    const user = userEvent.setup()
    render(<DebugPanel debugData={failedDebug} />)

    await user.click(screen.getByText('链路详情'))

    expect(screen.getByText(/质量检查未通过/)).toBeInTheDocument()
    expect(screen.getByText(/回答不完整/)).toBeInTheDocument()
  })
})
