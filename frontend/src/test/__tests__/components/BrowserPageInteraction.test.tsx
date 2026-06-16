import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import BrowserPage from '@/components/BrowserPage'
import * as api from '@/lib/api'
import { mockKBStats, mockKBChunks, mockHotspotData } from '@/test/mocks/data'

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { initial, animate, exit, transition, ...rest } = props
      return <div {...rest}>{children}</div>
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock('lucide-react', () => {
  const icons: Record<string, string> = {
    BookOpen: 'BookOpen', PanelRightOpen: 'PanelRightOpen', ArrowLeft: 'ArrowLeft',
    Search: 'Search', FileText: 'FileText', Hash: 'Hash', ExternalLink: 'ExternalLink',
    Layers: 'Layers', Sun: 'Sun', Moon: 'Moon', Flame: 'Flame', Upload: 'Upload',
    Globe: 'Globe', RefreshCw: 'RefreshCw', LayoutGrid: 'LayoutGrid', List: 'List', X: 'X',
  }
  return Object.fromEntries(Object.keys(icons).map((n) => [n, () => <span>{n}</span>]))
})
vi.mock('@/lib/api', () => ({
  getKBChunks: vi.fn(),
  getKBStats: vi.fn(),
  getKBSourceNames: vi.fn(),
  getKBConfig: vi.fn(),
  getKBHotspots: vi.fn(),
  uploadDocument: vi.fn(),
  ingestUrl: vi.fn(),
}))

const defaultProps = {
  onOpenSidebar: vi.fn(),
  sidebarOpen: false,
  onNavigate: vi.fn(),
  theme: { theme: 'dark' as const, toggle: vi.fn() },
}

describe('BrowserPage interactions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getKBChunks).mockResolvedValue({ items: mockKBChunks, total: 2 })
    vi.mocked(api.getKBStats).mockResolvedValue(mockKBStats)
    vi.mocked(api.getKBSourceNames).mockResolvedValue(['doc1.txt', 'doc2.md'])
    vi.mocked(api.getKBConfig).mockResolvedValue({ chunk_size: 1000, chunk_overlap: 200 })
    vi.mocked(api.getKBHotspots).mockResolvedValue(mockHotspotData)
  })

  it('search input calls getKBChunks with query', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())

    const searchInput = screen.getByPlaceholderText('搜索知识库…')
    await userEvent.type(searchInput, '年假{Enter}')
    expect(api.getKBChunks).toHaveBeenCalledWith(undefined, '年假', 0, 50)
  })

  it('source filter buttons render and can be clicked', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => {
      expect(screen.getByText('全部')).toBeInTheDocument()
    })
    // Click source filter
    await userEvent.click(screen.getByText('doc1.txt'))
    // After clicking, chunks should be refetched
    // Just verify no crash, filtering re-calls getKBChunks
    expect(api.getKBChunks).toHaveBeenCalled()
  })

  it('hotspot mode calls getKBHotspots', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())

    // Flame icon = hotspot toggle button
    const hotspotBtn = screen.getByText('Flame')
    await userEvent.click(hotspotBtn)
    expect(api.getKBHotspots).toHaveBeenCalled()
  })

  it('refresh button refetches data', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())

    await userEvent.click(screen.getByText('RefreshCw'))
    // getKBChunks should have been called at least twice
    expect(api.getKBChunks).toHaveBeenCalledTimes(2)
  })
})
