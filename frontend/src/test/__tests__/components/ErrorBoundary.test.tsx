import { render, screen } from '@testing-library/react'
import ErrorBoundary from '@/components/ErrorBoundary'

describe('ErrorBoundary', () => {
  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <div>child content</div>
      </ErrorBoundary>
    )
    expect(screen.getByText('child content')).toBeInTheDocument()
  })

  it('renders fallback UI on error', () => {
    const Bomb = () => { throw new Error('test error') }

    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    )

    expect(screen.getByText('出现了意外错误')).toBeInTheDocument()
    expect(screen.getByText('test error')).toBeInTheDocument()
  })

  it('renders a custom fallback when provided', () => {
    const Bomb = () => { throw new Error('test error') }

    render(
      <ErrorBoundary fallback={<div>custom fallback</div>}>
        <Bomb />
      </ErrorBoundary>,
    )

    expect(screen.getByText('custom fallback')).toBeInTheDocument()
    expect(screen.queryByText('出现了意外错误')).not.toBeInTheDocument()
  })
})
