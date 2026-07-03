import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import BrowserPage from '@/components/BrowserPage'
import * as api from '@/lib/api'
import { mockKBStats, mockKBChunks } from '@/test/mocks/data'

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

// Mock lucide-react icons used by BrowserPage
vi.mock('lucide-react', () => {
  const icons: Record<string, string> = {
    BookOpen: 'BookOpen',
    PanelRightOpen: 'PanelRightOpen',
    ArrowLeft: 'ArrowLeft',
    Search: 'Search',
    FileText: 'FileText',
    Hash: 'Hash',
    ExternalLink: 'ExternalLink',
    Layers: 'Layers',
    Sun: 'Sun',
    Moon: 'Moon',
    Flame: 'Flame',
    Upload: 'Upload',
    Globe: 'Globe',
    RefreshCw: 'RefreshCw',
    LayoutGrid: 'LayoutGrid',
    List: 'List',
    X: 'X',
    Sparkles: 'Sparkles',
    Bookmark: 'Bookmark',
    BookmarkCheck: 'BookmarkCheck',
    Bug: 'Bug',
    Loader2: 'Loader2',
  }
  return Object.fromEntries(
    Object.keys(icons).map((name) => [name, () => <span>{name}</span>])
  )
})

// Mock api
vi.mock('@/lib/api', () => ({
  getKBChunks: vi.fn(),
  getKBStats: vi.fn(),
  getKBSourceNames: vi.fn(),
  getKBConfig: vi.fn(),
  getKBHotspots: vi.fn(),
  getKBChunkById: vi.fn(),
  uploadDocument: vi.fn(),
  ingestUrl: vi.fn(),
  debugSearch: vi.fn(),
}))

const defaultProps = {
  onOpenSidebar: vi.fn(),
  sidebarOpen: false,
  onNavigate: vi.fn(),
  theme: { theme: 'dark' as const, toggle: vi.fn() },
}

describe('BrowserPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock returns
    vi.mocked(api.getKBChunks).mockResolvedValue({ items: mockKBChunks, total: 2 })
    vi.mocked(api.getKBStats).mockResolvedValue(mockKBStats)
    vi.mocked(api.getKBSourceNames).mockResolvedValue(['doc1.txt', 'doc2.md'])
    vi.mocked(api.getKBConfig).mockResolvedValue({ chunk_size: 1000, chunk_overlap: 200 })
    vi.mocked(api.getKBHotspots).mockResolvedValue([])
  })

  it('renders the "知识库" title', async () => {
    await act(async () => {
      render(<BrowserPage {...defaultProps} />)
    })
    expect(screen.getByText('知识库')).toBeInTheDocument()
  })

  it('renders chunk cards after data loads', async () => {
    await act(async () => {
      render(<BrowserPage {...defaultProps} />)
    })

    await waitFor(() => {
      expect(screen.getByText('这是第一段内容')).toBeInTheDocument()
    })
    expect(screen.getByText('这是第二段内容')).toBeInTheDocument()
  })

  it('shows source filter buttons', async () => {
    await act(async () => {
      render(<BrowserPage {...defaultProps} />)
    })

    await waitFor(() => {
      expect(screen.getByText('全部')).toBeInTheDocument()
    })
    // "doc1.txt" appears both as a source filter button and in chunk card labels
    // use getAllByText to confirm it appears at least once
    expect(screen.getAllByText('doc1.txt').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('doc2.md')).toBeInTheDocument()
  })

  it('shows stats in header', async () => {
    await act(async () => {
      render(<BrowserPage {...defaultProps} />)
    })

    await waitFor(() => {
      expect(screen.getByText('150 段落')).toBeInTheDocument()
    })
  })

  it('shows a workspace-aware empty state when no chunks match the current view', async () => {
    vi.mocked(api.getKBChunks).mockResolvedValue({ items: [], total: 0 })

    await act(async () => {
      render(<BrowserPage {...defaultProps} />)
    })

    await waitFor(() => {
      expect(screen.getByText('当前工作区没有匹配结果')).toBeInTheDocument()
      expect(screen.getByText('去聊天页提问')).toBeInTheDocument()
    })
  })

  it('keeps the loading state until the initial chunk request resolves', async () => {
    let resolveChunks: ((value: { items: typeof mockKBChunks; total: number } | { items: []; total: number }) => void) | undefined
    vi.mocked(api.getKBChunks).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveChunks = resolve
        }) as ReturnType<typeof api.getKBChunks>,
    )

    render(<BrowserPage {...defaultProps} />)

    await waitFor(() => {
      expect(api.getKBStats).toHaveBeenCalled()
      expect(api.getKBSourceNames).toHaveBeenCalled()
      expect(api.getKBConfig).toHaveBeenCalled()
    })

    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.queryByText('当前工作区没有匹配结果')).not.toBeInTheDocument()
    expect(screen.queryByText('这是第一段内容')).not.toBeInTheDocument()

    await act(async () => {
      resolveChunks?.({ items: [], total: 0 })
    })

    await waitFor(() => {
      expect(screen.getByText('当前工作区没有匹配结果')).toBeInTheDocument()
    })
  })

  it('back button calls onNavigate(\'chat\') when clicked', async () => {
    const onNavigate = vi.fn()

    await act(async () => {
      render(<BrowserPage {...defaultProps} onNavigate={onNavigate} />)
    })

    await waitFor(() => {
      expect(screen.getByText('返回')).toBeInTheDocument()
    })

    await userEvent.click(screen.getByText('返回'))
    expect(onNavigate).toHaveBeenCalledWith('chat')
  })

  it('sidebar open button visible when sidebarOpen=false', async () => {
    await act(async () => {
      render(<BrowserPage {...defaultProps} sidebarOpen={false} />)
    })

    // PanelRightOpen icon is rendered as a span with text "PanelRightOpen"
    expect(screen.getByText('PanelRightOpen')).toBeInTheDocument()
  })
})
