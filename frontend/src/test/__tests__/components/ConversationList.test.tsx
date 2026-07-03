import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConversationList from '@/components/sidebar/ConversationList'
import type { Conversation } from '@/lib/api'

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    deleteConversations: vi.fn(),
  }
})

describe('ConversationList', () => {
  function renderList(conversations: Conversation[]) {
    return render(
      <ConversationList
        conversations={conversations}
        activeId={null}
        loading={false}
        onSwitch={vi.fn()}
        onNew={vi.fn()}
        onRename={vi.fn()}
        onDelete={vi.fn()}
        onBatchDelete={vi.fn()}
        setActiveId={vi.fn()}
        clearMessages={vi.fn()}
      />,
    )
  }

  it('groups conversations into 今天、昨天 and 更早 buckets', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-03T12:00:00.000Z'))

    renderList([
      {
        id: 'conv-today',
        thread_id: 'thread-today',
        title: '今天的对话',
        created_at: '2026-07-03T08:00:00.000Z',
        updated_at: '2026-07-03T09:30:00.000Z',
        last_message_preview: '今天的摘要',
      },
      {
        id: 'conv-yesterday',
        thread_id: 'thread-yesterday',
        title: '昨天的对话',
        created_at: '2026-07-02T08:00:00.000Z',
        updated_at: '2026-07-02T09:30:00.000Z',
        last_message_preview: '昨天的摘要',
      },
      {
        id: 'conv-earlier',
        thread_id: 'thread-earlier',
        title: '更早的对话',
        created_at: '2026-06-29T08:00:00.000Z',
        updated_at: '2026-06-29T09:30:00.000Z',
        last_message_preview: '更早的摘要',
      },
    ] as Conversation[])

    expect(screen.getByText('今天')).toBeInTheDocument()
    expect(screen.getByText('昨天')).toBeInTheDocument()
    expect(screen.getByText('更早')).toBeInTheDocument()
    expect(screen.getByText('今天的对话')).toBeInTheDocument()
    expect(screen.getByText('昨天的对话')).toBeInTheDocument()
    expect(screen.getByText('更早的对话')).toBeInTheDocument()

    vi.useRealTimers()
  })

  it('matches search against both title and last message preview, and reveals the preview on hover', async () => {
    const user = userEvent.setup()

    renderList([
      {
        id: 'conv-1',
        thread_id: 'thread-1',
        title: '项目同步',
        created_at: '2026-07-01T08:00:00.000Z',
        updated_at: '2026-07-01T09:30:00.000Z',
        last_message_preview: '整理软件许可证和采购信息',
      },
      {
        id: 'conv-2',
        thread_id: 'thread-2',
        title: '周会记录',
        created_at: '2026-07-03T08:00:00.000Z',
        updated_at: '2026-07-03T09:30:00.000Z',
        last_message_preview: '确认演示环境',
      },
    ] as Conversation[])

    await user.type(screen.getByLabelText('搜索对话'), '许可证')

    expect(screen.getByText('项目同步')).toBeInTheDocument()
    expect(screen.queryByText('周会记录')).not.toBeInTheDocument()

    const titleButton = screen.getByRole('button', { name: '项目同步' })
    await user.hover(titleButton)

    expect(screen.getByRole('tooltip')).toHaveTextContent('整理软件许可证和采购信息')

    const group = titleButton.closest('section')
    expect(group).not.toBeNull()
    if (group) {
      expect(within(group).getByText('项目同步')).toBeInTheDocument()
    }
  })
})
