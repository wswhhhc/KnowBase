import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import JobsPage from '@/pages/jobs/JobsPage'
import * as api from '@/shared/api'
import type { Job } from '@/shared/api'

vi.mock('@/shared/api', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api')>('@/shared/api')
  return {
    ...actual,
    listJobs: vi.fn(),
  }
})

describe('JobsPage', () => {
  function job(overrides: Partial<Job>): Job {
    return {
      id: 'job-1',
      job_type: 'ingest_file',
      status: 'queued',
      workspace_id: '',
      progress: { phase: '', percent: 0, message: '' },
      error: '',
      attempts: 0,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      ...overrides,
    }
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders queued and failed jobs with progress and errors', async () => {
    vi.mocked(api.listJobs).mockResolvedValue([
      job({
        id: 'job-1',
        job_type: 'ingest_file',
        status: 'running',
        workspace_id: 'ws-a',
        progress: { phase: 'embedding', percent: 45, message: '正在向量化' },
      }),
      job({
        id: 'job-2',
        job_type: 'ingest_url',
        status: 'failed',
        workspace_id: '',
        progress: { phase: 'fetching', percent: 10, message: '' },
        error: 'URL 下载失败',
        created_at: '2026-01-02T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      }),
    ])

    render(<JobsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    expect(await screen.findByText('文件导入')).toBeInTheDocument()
    expect(screen.getByText('URL 导入')).toBeInTheDocument()
    expect(screen.getByText('正在向量化')).toBeInTheDocument()
    expect(screen.getByText('URL 下载失败')).toBeInTheDocument()
    expect(screen.getByText('1 个任务仍在处理中')).toBeInTheDocument()
  })

  it('shows an empty state when no jobs exist', async () => {
    vi.mocked(api.listJobs).mockResolvedValue([])

    render(<JobsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    expect(await screen.findByText('暂无后台任务')).toBeInTheDocument()
  })

  it('reloads jobs when refresh is clicked', async () => {
    vi.mocked(api.listJobs)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        job({
          id: 'job-3',
          job_type: 'ingest_file',
          status: 'succeeded',
          workspace_id: '',
          progress: { phase: 'done', percent: 100, message: '' },
          created_at: '2026-01-03T00:00:00Z',
          updated_at: '2026-01-03T00:00:00Z',
        }),
      ])

    render(<JobsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)
    expect(await screen.findByText('暂无后台任务')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /刷新/ }))

    expect(await screen.findByText('文件导入')).toBeInTheDocument()
    expect(api.listJobs).toHaveBeenCalledTimes(2)
  })

  it('shows an error state and retries loading', async () => {
    vi.mocked(api.listJobs)
      .mockRejectedValueOnce(new Error('network error'))
      .mockResolvedValueOnce([])

    render(<JobsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    expect(await screen.findByText('任务列表加载失败')).toBeInTheDocument()
    expect(screen.getByText('network error')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '重试' }))

    await waitFor(() => {
      expect(api.listJobs).toHaveBeenCalledTimes(2)
    })
    expect(await screen.findByText('暂无后台任务')).toBeInTheDocument()
  })
})
