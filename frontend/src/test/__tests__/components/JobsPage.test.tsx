import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import JobsPage from '@/pages/jobs/JobsPage'
import * as api from '@/shared/api'
import type { Job } from '@/shared/api'

vi.mock('@/shared/api', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api')>('@/shared/api')
  return {
    ...actual,
    listJobs: vi.fn(),
    cancelJob: vi.fn(),
    retryJob: vi.fn(),
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

  afterEach(() => {
    vi.useRealTimers()
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

  it('cancels queued jobs and updates the rendered status', async () => {
    vi.mocked(api.listJobs).mockResolvedValue([
      job({
        id: 'job-cancel-1',
        job_type: 'ingest_file',
        status: 'queued',
        progress: { phase: 'queued', percent: 0, message: '等待执行' },
      }),
    ])
    vi.mocked(api.cancelJob).mockResolvedValue(job({
      id: 'job-cancel-1',
      job_type: 'ingest_file',
      status: 'canceled',
      progress: { phase: 'canceled', percent: 0, message: '已取消' },
    }))

    render(<JobsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await userEvent.click(await screen.findByRole('button', { name: '取消任务 job-cancel-1' }))

    expect(api.cancelJob).toHaveBeenCalledWith('job-cancel-1')
    expect(await screen.findAllByText('已取消')).toHaveLength(2)
    expect(screen.queryByRole('button', { name: '取消任务 job-cancel-1' })).not.toBeInTheDocument()
  })

  it('does not show cancel actions for finished jobs', async () => {
    vi.mocked(api.listJobs).mockResolvedValue([
      job({
        id: 'job-done-1',
        status: 'succeeded',
        progress: { phase: 'done', percent: 100, message: '完成' },
      }),
    ])

    render(<JobsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    expect(await screen.findByText('已完成')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '取消任务 job-done-1' })).not.toBeInTheDocument()
  })

  it('shows a row-level error when canceling fails', async () => {
    vi.mocked(api.listJobs).mockResolvedValue([
      job({
        id: 'job-cancel-fail',
        status: 'queued',
        progress: { phase: 'queued', percent: 0, message: '等待执行' },
      }),
    ])
    vi.mocked(api.cancelJob).mockRejectedValue(new Error('任务已开始，无法取消'))

    render(<JobsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await userEvent.click(await screen.findByRole('button', { name: '取消任务 job-cancel-fail' }))

    expect(await screen.findByText('任务已开始，无法取消')).toBeInTheDocument()
    expect(screen.getByText('排队中')).toBeInTheDocument()
  })

  it('retries failed jobs and updates the rendered status', async () => {
    vi.mocked(api.listJobs).mockResolvedValue([
      job({
        id: 'job-retry-1',
        job_type: 'ingest_url',
        status: 'failed',
        progress: { phase: 'fetching', percent: 25, message: 'URL 下载失败' },
        error: 'URL 下载失败',
      }),
    ])
    vi.mocked(api.retryJob).mockResolvedValue(job({
      id: 'job-retry-1',
      job_type: 'ingest_url',
      status: 'queued',
      progress: { phase: 'queued', percent: 0, message: '任务已重新排队' },
      error: '',
    }))

    render(<JobsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await userEvent.click(await screen.findByRole('button', { name: '重试任务 job-retry-1' }))

    expect(api.retryJob).toHaveBeenCalledWith('job-retry-1')
    expect(await screen.findByText('任务已重新排队')).toBeInTheDocument()
    expect(screen.getByText('排队中')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '重试任务 job-retry-1' })).not.toBeInTheDocument()
  })

  it('shows a row-level error when retrying fails', async () => {
    vi.mocked(api.listJobs).mockResolvedValue([
      job({
        id: 'job-retry-fail',
        job_type: 'ingest_url',
        status: 'failed',
        error: 'URL 下载失败',
      }),
    ])
    vi.mocked(api.retryJob).mockRejectedValue(new Error('文件导入任务无法直接重试'))

    render(<JobsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await userEvent.click(await screen.findByRole('button', { name: '重试任务 job-retry-fail' }))

    expect(await screen.findByText('文件导入任务无法直接重试')).toBeInTheDocument()
    expect(screen.getByText('失败')).toBeInTheDocument()
  })

  it('does not offer direct retry for failed file imports', async () => {
    vi.mocked(api.listJobs).mockResolvedValue([
      job({
        id: 'job-file-failed',
        job_type: 'ingest_file',
        status: 'failed',
        error: '任务队列不可用',
      }),
    ])

    render(<JobsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    expect(await screen.findByText('任务队列不可用')).toBeInTheDocument()
    expect(screen.getByText('请重新上传文件')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '重试任务 job-file-failed' })).not.toBeInTheDocument()
  })

  it('auto refreshes while jobs are still active', async () => {
    vi.useFakeTimers()
    vi.mocked(api.listJobs)
      .mockResolvedValueOnce([
        job({
          id: 'job-auto-1',
          status: 'running',
          progress: { phase: 'embedding', percent: 45, message: '正在向量化' },
        }),
      ])
      .mockResolvedValueOnce([
        job({
          id: 'job-auto-1',
          status: 'succeeded',
          progress: { phase: 'done', percent: 100, message: '完成' },
        }),
      ])

    render(<JobsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByText('正在向量化')).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })

    expect(screen.getByText('已完成')).toBeInTheDocument()
    expect(api.listJobs).toHaveBeenCalledTimes(2)
  })
})
