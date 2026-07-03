import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import BookmarkPanel from '@/components/sidebar/BookmarkPanel'
import * as api from '@/lib/api'

vi.mock('lucide-react', () => {
  const icons: Record<string, string> = {
    Bookmark: 'Bookmark',
    BookmarkCheck: 'BookmarkCheck',
    Search: 'Search',
    Tag: 'Tag',
    X: 'X',
    Trash2: 'Trash2',
  }
  return Object.fromEntries(
    Object.keys(icons).map((name) => [name, () => <span>{name}</span>]),
  )
})

vi.mock('@/lib/api', () => ({
  getBookmarks: vi.fn(),
  updateBookmark: vi.fn(),
  deleteBookmark: vi.fn(),
}))

const mockBookmarks = [
  {
    id: 1,
    workspace_id: 'ws-1',
    conversation_id: '',
    message_id: 0,
    chunk_id: 'doc.txt:1:abc',
    note: '',
    content: '第一条书签',
    source: 'doc.txt',
    tags: 'alpha,beta',
    created_at: '2026-06-16T08:00:00Z',
  },
  {
    id: 2,
    workspace_id: 'ws-1',
    conversation_id: '',
    message_id: 0,
    chunk_id: 'doc.txt:2:def',
    note: '',
    content: '第二条书签',
    source: 'doc.txt',
    tags: 'beta',
    created_at: '2026-06-16T08:05:00Z',
  },
]

describe('BookmarkPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    vi.mocked(api.getBookmarks).mockResolvedValue(mockBookmarks as any)
  })

  it('filters bookmarks by selected tag', async () => {
    render(<BookmarkPanel workspaceId="ws-1" />)

    await waitFor(() => {
      expect(screen.getByText('第一条书签')).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /alpha/i }))

    expect(screen.getByText('第一条书签')).toBeInTheDocument()
    expect(screen.queryByText('第二条书签')).not.toBeInTheDocument()
  })

  it('navigates to browser and stores highlight chunk id', async () => {
    const onNavigate = vi.fn()

    render(<BookmarkPanel workspaceId="ws-1" onNavigate={onNavigate} />)

    await waitFor(() => {
      expect(screen.getByText('第一条书签')).toBeInTheDocument()
    })

    await userEvent.click(screen.getByText('第一条书签'))

    expect(sessionStorage.getItem('highlightChunkId')).toBe('doc.txt:1:abc')
    expect(onNavigate).toHaveBeenCalledWith('browser')
  })

  it('updates bookmark note and tags together', async () => {
    vi.mocked(api.updateBookmark).mockResolvedValue(mockBookmarks[0] as any)

    render(<BookmarkPanel workspaceId="ws-1" />)

    await waitFor(() => {
      expect(screen.getByText('第一条书签')).toBeInTheDocument()
    })

    const bookmarkCard = screen.getByText('第一条书签').closest('.group') as HTMLElement
    await userEvent.click(within(bookmarkCard).getByText('Tag'))

    const tagsInput = screen.getByPlaceholderText('逗号分隔标签')
    await userEvent.clear(tagsInput)
    await userEvent.type(tagsInput, 'gamma')

    const noteInput = screen.getByPlaceholderText('备注（可选）')
    await userEvent.type(noteInput, ' 需要重点复习')

    const saveButtons = screen.getAllByText('BookmarkCheck')
    await userEvent.click(saveButtons[0])

    await waitFor(() => {
      expect(api.updateBookmark).toHaveBeenCalledWith(1, {
        tags: 'gamma',
        note: ' 需要重点复习',
      })
    })
  })

  it('opens the editor from the context menu gesture', async () => {
    render(<BookmarkPanel workspaceId="ws-1" />)

    await waitFor(() => {
      expect(screen.getByText('第一条书签')).toBeInTheDocument()
    })

    fireEvent.contextMenu(screen.getByText('第一条书签'))

    expect(screen.getByPlaceholderText('逗号分隔标签')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('备注（可选）')).toBeInTheDocument()
  })

  it('shows an explicit delete action while editing a bookmark', async () => {
    render(<BookmarkPanel workspaceId="ws-1" />)

    await waitFor(() => {
      expect(screen.getByText('第一条书签')).toBeInTheDocument()
    })

    fireEvent.contextMenu(screen.getByText('第一条书签'))

    expect(screen.getByRole('button', { name: '删除书签' })).toBeInTheDocument()
  })

  it('clears stale bookmarks when the workspace changes', async () => {
    const ws2Bookmarks = [
      {
        ...mockBookmarks[0],
        id: 9,
        workspace_id: 'ws-2',
        content: '第二工作区书签',
      },
    ]
    let resolveWs2Bookmarks: ((value: typeof ws2Bookmarks) => void) | undefined

    vi.mocked(api.getBookmarks).mockImplementation((workspaceId?: string) => {
      if (workspaceId === 'ws-2') {
        return new Promise((resolve) => {
          resolveWs2Bookmarks = resolve
        }) as ReturnType<typeof api.getBookmarks>
      }
      return Promise.resolve(mockBookmarks as any)
    })

    const { rerender } = render(<BookmarkPanel workspaceId="ws-1" />)

    await waitFor(() => {
      expect(screen.getByText('第一条书签')).toBeInTheDocument()
    })

    rerender(<BookmarkPanel workspaceId="ws-2" />)

    expect(screen.queryByText('第一条书签')).not.toBeInTheDocument()

    await act(async () => {
      resolveWs2Bookmarks?.(ws2Bookmarks as any)
    })

    await waitFor(() => {
      expect(screen.getByText('第二工作区书签')).toBeInTheDocument()
    })
  })
})
