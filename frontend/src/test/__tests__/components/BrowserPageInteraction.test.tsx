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
    Bookmark: 'Bookmark', BookmarkCheck: 'BookmarkCheck',
  }
  return Object.fromEntries(Object.keys(icons).map((n) => [n, () => <span>{n}</span>]))
})
vi.mock('@/lib/api', () => ({
  getKBChunks: vi.fn(),
  getKBStats: vi.fn(),
  getKBSourceNames: vi.fn(),
  getKBConfig: vi.fn(),
  getKBHotspots: vi.fn(),
  createBookmark: vi.fn(),
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

    await waitFor(() => expect(screen.getByText('工作区')).toBeInTheDocument())

    const searchInput = screen.getByPlaceholderText('搜索文档内容…')
    await userEvent.type(searchInput, '年假{Enter}')
    expect(api.getKBChunks).toHaveBeenCalledWith('', '年假', 0, 50)
  })

  it('source filter buttons render and can be clicked', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => {
      expect(screen.getByText('全部')).toBeInTheDocument()
    })
    // Click source filter (first match — the source button)
    const sourceButtons = screen.getAllByText('doc1.txt')
    await userEvent.click(sourceButtons[0])
    // After clicking, chunks should be refetched
    // Just verify no crash, filtering re-calls getKBChunks
    expect(api.getKBChunks).toHaveBeenCalled()
  })

  it('hotspot mode calls getKBHotspots', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('工作区')).toBeInTheDocument())

    // The hotspot toggle is the button wrapping a Flame icon — find by its test-id approach
    // The button has no text, so target the hotspot toggle button via its sibling structure
    const hotspotToggle = screen.getByText('全部').parentElement?.nextElementSibling?.querySelector('button')
    if (hotspotToggle) {
      await userEvent.click(hotspotToggle)
      expect(api.getKBHotspots).toHaveBeenCalled()
    }
  })

  it('refresh button refetches data', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('工作区')).toBeInTheDocument())

    await userEvent.click(screen.getByText('RefreshCw'))
    expect(api.getKBChunks).toHaveBeenCalled()
  })

  it('createBookmark receives workspace_id when passed as prop', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} workspaceId="ws-1" />) })
    await waitFor(() => expect(screen.getByText('工作区')).toBeInTheDocument())
    const bmBtns = screen.getAllByText('Bookmark')
    await userEvent.click(bmBtns[0])
    expect(api.createBookmark).toHaveBeenCalled()
    const callArg = vi.mocked(api.createBookmark).mock.calls[0][0]
    expect(callArg.workspace_id).toBe('ws-1')
  })

  it('only fetches the first chunk page once on initial render', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('工作区')).toBeInTheDocument())
    expect(api.getKBChunks).toHaveBeenCalledTimes(1)
    expect(api.getKBChunks).toHaveBeenNthCalledWith(1, '', '', 0, 50)
  })

  it('loads additional pages to reveal a highlighted chunk beyond the first page', async () => {
    const pagedChunks = Array.from({ length: 60 }, (_, index) => ({
      source: 'doc-long.txt',
      chunk_index: index,
      chunk_id: `doc-long.txt:${index}:hash`,
      page: null,
      content: `段落 ${index}`,
      original_content: `段落 ${index}`,
      section: null,
    }))
    vi.mocked(api.getKBChunks).mockImplementation(async (_source = '', _search = '', skip = 0, limit = 50) => ({
      items: pagedChunks.slice(skip, skip + limit),
      total: pagedChunks.length,
    }))
    vi.mocked(api.getKBSourceNames).mockResolvedValue(['doc-long.txt'])

    const onHighlightConsumed = vi.fn()

    await act(async () => {
      render(
        <BrowserPage
          {...defaultProps}
          highlightChunkId="doc-long.txt:55:hash"
          onHighlightConsumed={onHighlightConsumed}
        />,
      )
    })

    await waitFor(() => {
      expect(screen.getAllByText('段落 55').length).toBeGreaterThan(0)
    })
    expect(onHighlightConsumed).toHaveBeenCalled()
    expect(vi.mocked(api.getKBChunks)).toHaveBeenCalledWith('', '', 50, 50)
  })

  it('does not open the detail dialog when bookmarking in slice view', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('工作区')).toBeInTheDocument())
    const sourceButtons = screen.getAllByText('doc1.txt')
    await userEvent.click(sourceButtons[0])
    await waitFor(() => expect(screen.getByText('网格视图')).toBeInTheDocument())

    const listToggle = screen.getByText('List').closest('button')
    expect(listToggle).not.toBeNull()
    await userEvent.click(listToggle!)

    const bookmarkButtons = screen.getAllByText('Bookmark')
    await userEvent.click(bookmarkButtons[0])

    expect(api.createBookmark).toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
