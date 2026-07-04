import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSidebarConversations } from '@/features/sidebar/hooks/useSidebarConversations'
import * as api from '@/shared/api'

vi.mock('@/shared/api', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api')>('@/shared/api')
  return {
    ...actual,
    getMessages: vi.fn(),
    getConversationPinState: vi.fn(),
  }
})

function createDeferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

describe('useSidebarConversations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores stale conversation responses after the workspace changes', async () => {
    const messagesDeferred = createDeferred<any[]>()
    const pinStateDeferred = createDeferred<any>()
    vi.mocked(api.getMessages).mockReturnValue(messagesDeferred.promise as ReturnType<typeof api.getMessages>)
    vi.mocked(api.getConversationPinState).mockReturnValue(pinStateDeferred.promise as ReturnType<typeof api.getConversationPinState>)

    const loadMessages = vi.fn()
    const setActiveId = vi.fn()
    const conversation = {
      id: 'conv-1',
      thread_id: 'thread-1',
      title: '测试对话',
      created_at: '2026-07-04T00:00:00Z',
      updated_at: '2026-07-04T00:00:00Z',
      last_message_preview: '',
    }

    const { result, rerender } = renderHook(
      (props: {
        activeWorkspaceId: string
        workspaceScopeKey: string
        chatWorkspaceId: string
      }) => useSidebarConversations({
        chat: {
          loadMessages,
          clearMessages: vi.fn(),
          threadId: null,
          workspaceId: props.chatWorkspaceId,
        },
        convs: {
          conversations: [conversation],
          activeId: null,
          setActiveId,
          create: vi.fn(),
          remove: vi.fn(),
          rename: vi.fn(),
          refresh: vi.fn().mockResolvedValue([conversation]),
          loading: false,
        } as any,
        activeThreadId: null,
        convRefreshKey: 0,
        activeWorkspaceId: props.activeWorkspaceId,
        workspaceScopeKey: props.workspaceScopeKey,
        onNavigate: vi.fn(),
        onClose: vi.fn(),
      }),
      {
        initialProps: {
          activeWorkspaceId: 'ws-1',
          workspaceScopeKey: 'ws-1',
          chatWorkspaceId: 'ws-1',
        },
      },
    )

    let pendingSwitch: Promise<void>
    await act(async () => {
      pendingSwitch = result.current.switchConversation(conversation)
    })

    rerender({
      activeWorkspaceId: 'ws-2',
      workspaceScopeKey: 'ws-2',
      chatWorkspaceId: 'ws-2',
    })

    await act(async () => {
      messagesDeferred.resolve([
        {
          id: 1,
          role: 'assistant',
          content: '旧工作区回答',
          sources: [],
          quality_reason: '',
          debug_info: {},
          feedback: null,
          created_at: '2026-07-04T00:00:00Z',
        },
      ])
      pinStateDeferred.resolve({ thread_id: 'thread-1', pinned_chunk_ids: [], excluded_chunk_ids: [] })
      await pendingSwitch
    })

    expect(setActiveId).not.toHaveBeenCalled()
    expect(loadMessages).not.toHaveBeenCalled()
  })
})
