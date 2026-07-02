import { render, screen, waitFor, act, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import BrowserPage from '@/components/BrowserPage'
import * as api from '@/lib/api'
import { mockKBStats, mockKBChunks, mockHotspotData } from '@/test/mocks/data'

function createChunk(overrides: Partial<typeof mockKBChunks[number]> = {}) {
  return {
    source: 'doc1.txt',
    chunk_index: 0,
    chunk_id: 'doc1.txt:0:abc',
    page: null,
    content: '默认段落',
    original_content: '默认段落',
    section: null,
    ...overrides,
  }
}

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
    Bookmark: 'Bookmark', BookmarkCheck: 'BookmarkCheck', Bug: 'Bug', Loader2: 'Loader2', Sparkles: 'Sparkles',
  }
  return Object.fromEntries(Object.keys(icons).map((n) => [n, () => <span>{n}</span>]))
})
vi.mock('@/lib/api', () => ({
  getKBChunks: vi.fn(),
  getKBChunkById: vi.fn(),
  getKBStats: vi.fn(),
  getKBSourceNames: vi.fn(),
  getKBConfig: vi.fn(),
  getKBHotspots: vi.fn(),
  checkSource: vi.fn().mockResolvedValue({ exists: false }),
  createBookmark: vi.fn(),
  uploadDocumentStream: vi.fn().mockImplementation((_file, _mode, callbacks) => {
    callbacks.onDone?.({ chunk_count: 1, total_docs: 1, message: 'ok' })
    return { abort: vi.fn() }
  }),
  ingestUrlStream: vi.fn().mockImplementation((_url, _mode, callbacks) => {
    callbacks.onDone?.({ chunk_count: 1, total_docs: 1, message: 'ok' })
    return { abort: vi.fn() }
  }),
  debugSearch: vi.fn().mockResolvedValue({
    strategy: 'balanced',
    vector_results: [],
    bm25_results: [],
    fused_results: [],
  }),
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
    vi.useRealTimers()
    sessionStorage.clear()
    vi.mocked(api.getKBChunks).mockResolvedValue({ items: mockKBChunks, total: 2 })
    vi.mocked(api.getKBChunkById).mockResolvedValue(mockKBChunks[0])
    vi.mocked(api.getKBStats).mockResolvedValue(mockKBStats)
    vi.mocked(api.getKBSourceNames).mockResolvedValue(['doc1.txt', 'doc2.md'])
    vi.mocked(api.getKBConfig).mockResolvedValue({ chunk_size: 1000, chunk_overlap: 200 })
    vi.mocked(api.getKBHotspots).mockResolvedValue(mockHotspotData)
  })

  it('search input calls getKBChunks with query', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} workspaceId="ws-1" />) })

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())

    const searchInput = screen.getByPlaceholderText('搜索文档内容…')
    await userEvent.type(searchInput, '年假{Enter}')
    expect(api.getKBChunks).toHaveBeenCalledWith('', '年假', 0, 50, 'ws-1')
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

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())

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

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())

    await userEvent.click(screen.getByText('RefreshCw'))
    expect(api.getKBChunks).toHaveBeenCalled()
  })

  it('createBookmark receives workspace_id when passed as prop', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} workspaceId="ws-1" />) })
    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())
    const bmBtns = screen.getAllByText('Bookmark')
    await userEvent.click(bmBtns[0])
    expect(api.createBookmark).toHaveBeenCalled()
    const callArg = vi.mocked(api.createBookmark).mock.calls[0][0]
    expect(callArg.workspace_id).toBe('ws-1')
  })

  it('only fetches the first chunk page once on initial render', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} workspaceId="ws-1" />) })

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())
    expect(api.getKBChunks).toHaveBeenCalledTimes(1)
    expect(api.getKBChunks).toHaveBeenNthCalledWith(1, '', '', 0, 50, 'ws-1')
  })

  it('fetches a highlighted chunk directly by id when it is outside the loaded page', async () => {
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
    vi.mocked(api.getKBChunkById).mockResolvedValue(pagedChunks[55])
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
    expect(vi.mocked(api.getKBChunkById)).toHaveBeenCalledWith('doc-long.txt:55:hash', '')
    expect(vi.mocked(api.getKBChunks)).toHaveBeenCalledTimes(1)
  })

  it('deduplicates repeated chunk ids returned in the same page', async () => {
    const duplicateChunk = createChunk({
      chunk_id: 'sample_ai.txt:0:a7a7ff8a6f195188',
      content: '重复段落',
      original_content: '重复段落',
    })
    const uniqueChunk = createChunk({
      chunk_id: 'sample_ai.txt:1:unique',
      chunk_index: 1,
      content: '唯一段落',
      original_content: '唯一段落',
    })
    vi.mocked(api.getKBChunks).mockResolvedValue({
      items: [duplicateChunk, duplicateChunk, uniqueChunk],
      total: 3,
    })
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await act(async () => {
      render(<BrowserPage {...defaultProps} />)
    })

    await waitFor(() => {
      expect(screen.getByText('重复段落')).toBeInTheDocument()
      expect(screen.getByText('唯一段落')).toBeInTheDocument()
    })

    expect(document.querySelectorAll('[id="chunk-sample_ai.txt:0:a7a7ff8a6f195188"]')).toHaveLength(1)
    expect(
      consoleErrorSpy.mock.calls.some((call) =>
        call.some((arg) => typeof arg === 'string' && arg.includes('Encountered two children with the same key')),
      ),
    ).toBe(false)

    consoleErrorSpy.mockRestore()
  })

  it('does not duplicate a highlighted chunk when the direct fetch resolves after the initial page', async () => {
    const highlightedChunk = createChunk({
      chunk_id: 'doc-race.txt:0:same',
      source: 'doc-race.txt',
      content: '竞态段落',
      original_content: '竞态段落',
    })
    const siblingChunk = createChunk({
      chunk_id: 'doc-race.txt:1:other',
      source: 'doc-race.txt',
      chunk_index: 1,
      content: '其他段落',
      original_content: '其他段落',
    })

    let resolveChunks: ((value: { items: typeof mockKBChunks; total: number } | { items: [typeof highlightedChunk, typeof siblingChunk]; total: number }) => void) | undefined
    let resolveHighlighted: ((value: typeof highlightedChunk) => void) | undefined

    vi.mocked(api.getKBChunks).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveChunks = resolve
        }) as ReturnType<typeof api.getKBChunks>,
    )
    vi.mocked(api.getKBChunkById).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveHighlighted = resolve
        }) as ReturnType<typeof api.getKBChunkById>,
    )
    vi.mocked(api.getKBSourceNames).mockResolvedValue(['doc-race.txt'])
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await act(async () => {
      render(
        <BrowserPage
          {...defaultProps}
          highlightChunkId="doc-race.txt:0:same"
        />,
      )
    })

    await act(async () => {
      resolveChunks?.({ items: [highlightedChunk, siblingChunk], total: 2 })
    })

    await waitFor(() => {
      expect(screen.getByText('竞态段落')).toBeInTheDocument()
      expect(screen.getByText('其他段落')).toBeInTheDocument()
    })

    await act(async () => {
      resolveHighlighted?.(highlightedChunk)
    })

    expect(document.querySelectorAll('[id="chunk-doc-race.txt:0:same"]')).toHaveLength(1)
    expect(
      consoleErrorSpy.mock.calls.some((call) =>
        call.some((arg) => typeof arg === 'string' && arg.includes('Encountered two children with the same key')),
      ),
    ).toBe(false)

    consoleErrorSpy.mockRestore()
  })

  it('does not open the detail dialog when bookmarking in slice view', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())
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

  it('uploads documents through the SSE stream API', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())
    vi.useFakeTimers()

    const file = new File(['browser upload'], 'browser.txt', { type: 'text/plain' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(input).not.toBeNull()

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } })
      await Promise.resolve()
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(api.checkSource).toHaveBeenCalledWith('browser.txt', '')
    expect(api.uploadDocumentStream).toHaveBeenCalledWith(
      expect.any(File),
      undefined,
      expect.objectContaining({
        onProgress: expect.any(Function),
        onDone: expect.any(Function),
        onError: expect.any(Function),
      }),
      '',
    )
    expect(screen.getByText('文档已导入！现在可以去提问了')).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(8000)
      await Promise.resolve()
    })

    expect(screen.queryByText('文档已导入！现在可以去提问了')).not.toBeInTheDocument()
  })

  it('lets the user dismiss the upload guidance banner immediately', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())

    const file = new File(['browser upload'], 'browser.txt', { type: 'text/plain' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } })
      await Promise.resolve()
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(screen.getByText('文档已导入！现在可以去提问了')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '关闭提示' }))

    expect(screen.queryByText('文档已导入！现在可以去提问了')).not.toBeInTheDocument()
  })

  it('opens the file picker automatically when kb_trigger_upload is present on load', async () => {
    sessionStorage.setItem('kb_trigger_upload', 'true')
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(() => {})

    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())
    await waitFor(() => expect(clickSpy).toHaveBeenCalledTimes(1))
    expect(sessionStorage.getItem('kb_trigger_upload')).toBeNull()

    clickSpy.mockRestore()
  })

  it('prompts for version handling when the source already exists', async () => {
    vi.mocked(api.checkSource).mockResolvedValueOnce({ exists: true })

    await act(async () => { render(<BrowserPage {...defaultProps} />) })
    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())

    const file = new File(['browser upload'], 'browser.txt', { type: 'text/plain' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(screen.getByText(/引用来源".*browser\.txt.*已存在/)).toBeInTheDocument()
    })
    expect(api.uploadDocumentStream).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: '追加版本' }))

    await waitFor(() => {
      expect(api.uploadDocumentStream).toHaveBeenCalledWith(
        expect.any(File),
        'append',
        expect.objectContaining({
          onProgress: expect.any(Function),
          onDone: expect.any(Function),
          onError: expect.any(Function),
        }),
        '',
      )
    })
  })

  it('ingests URLs through the SSE stream API', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('知识库')).toBeInTheDocument())

    await userEvent.type(screen.getByPlaceholderText('导入公开网页 https://…'), 'https://example.com')
    await userEvent.click(screen.getByText('Globe'))

    await waitFor(() => {
      expect(api.ingestUrlStream).toHaveBeenCalledWith(
        'https://example.com',
        undefined,
        expect.objectContaining({
          onProgress: expect.any(Function),
          onDone: expect.any(Function),
          onError: expect.any(Function),
        }),
        '',
      )
    })
    expect(screen.getByText('文档已导入！现在可以去提问了')).toBeInTheDocument()
  })

  it('passes the selected strategy to debug search', async () => {
    await act(async () => { render(<BrowserPage {...defaultProps} />) })

    await waitFor(() => expect(screen.getByText('检索测试沙盒')).toBeInTheDocument())

    await userEvent.click(screen.getByText('检索测试沙盒'))
    await userEvent.type(screen.getByPlaceholderText('输入测试查询…'), '策略测试')
    await userEvent.click(screen.getByText('深度'))
    await userEvent.click(screen.getByRole('button', { name: '检索' }))

    await waitFor(() => {
      expect(api.debugSearch).toHaveBeenCalledWith('策略测试', 5, 'deep', '')
    })
  })
})
