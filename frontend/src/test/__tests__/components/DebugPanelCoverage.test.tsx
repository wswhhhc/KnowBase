import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import DebugPanel from '@/components/DebugPanel'
import { mockSSEDebugEvent, mockDebugInfo } from '@/test/mocks/data'
import type { DebugInfo } from '@/lib/api'

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
  const icon = (name: string) => ({ children, ...props }: any) => <span data-testid={`lucide-${name}`} {...props}>{children}</span>
  return {
    Bug: icon('Bug'), ChevronDown: icon('ChevronDown'), ChevronRight: icon('ChevronRight'),
    Search: icon('Search'), Globe: icon('Globe'), RotateCcw: icon('RotateCcw'), Zap: icon('Zap'),
  }
})

describe('DebugPanel coverage', () => {
  it('renders rewrite info when used_rewrite is true', async () => {
    const data: DebugInfo = {
      ...mockDebugInfo,
      used_rewrite: true,
      rewritten_question: '年假政策是什么',
    }
    render(<DebugPanel debugData={data} />)
    await userEvent.click(screen.getByText('链路详情'))
    expect(screen.getByText(/年假政策是什么/)).toBeInTheDocument()
  })

  it('renders web search info when used', async () => {
    const data: DebugInfo = {
      ...mockDebugInfo,
      used_web_search: true,
      web_results_count: 3,
    }
    render(<DebugPanel debugData={data} />)
    await userEvent.click(screen.getByText('链路详情'))
    expect(screen.getByText(/联网 3 条/)).toBeInTheDocument()
  })

  it('renders rerank info when used_rerank is true', async () => {
    const data: DebugInfo = {
      ...mockDebugInfo,
      used_rerank: true,
      candidates_before: 30,
      after_rerank: 5,
    }
    render(<DebugPanel debugData={data} />)
    await userEvent.click(screen.getByText('链路详情'))
    // Should show rerank info (the "rerank 30→5" text)
    expect(screen.getByText(/rerank 30.+5/)).toBeInTheDocument()
  })

  it('renders retry count badge', async () => {
    const data: DebugInfo = {
      ...mockDebugInfo,
      retry_count: 2,
    }
    render(<DebugPanel debugData={data} />)
    await userEvent.click(screen.getByText('链路详情'))
    expect(screen.getByText(/重试 2 次/)).toBeInTheDocument()
  })

  it('toggles collapse/expand', async () => {
    render(<DebugPanel debugData={mockDebugInfo} />)
    // Start collapsed
    expect(screen.queryByText('问题路由')).not.toBeInTheDocument()

    await userEvent.click(screen.getByText('链路详情'))
    expect(screen.getByText('问题路由')).toBeInTheDocument()

    await userEvent.click(screen.getByText('收起链路详情'))
    expect(screen.queryByText('问题路由')).not.toBeInTheDocument()
  })

  it('shows quality failure message when quality_passed is false', async () => {
    const failed: DebugInfo = {
      ...mockDebugInfo,
      quality_passed: false,
      quality_reason: '证据不足',
    }
    render(<DebugPanel debugData={failed} />)
    await userEvent.click(screen.getByText('链路详情'))
    expect(screen.getByText(/证据不足/)).toBeInTheDocument()
  })

  it('uses monospace only for timing and score spans', async () => {
    render(<DebugPanel debugData={mockDebugInfo} />)
    await userEvent.click(screen.getByText('链路详情'))

    expect(screen.getByText('200ms')).toHaveClass('font-mono')
    expect(screen.getByText('0.910')).toHaveClass('font-mono')
    expect(screen.getByText('送入模型的段落').closest('div')).not.toHaveClass('font-mono')
  })
})
