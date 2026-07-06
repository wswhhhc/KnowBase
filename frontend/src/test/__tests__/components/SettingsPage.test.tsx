import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SettingsPage from '@/pages/settings/SettingsPage'
import { MASKED_SECRET_VALUE } from '@/shared/api'
import * as api from '@/shared/api'

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

vi.mock('lucide-react', () => {
  const icons: Record<string, string> = {
    PanelRightOpen: 'PanelRightOpen',
    Save: 'Save',
    AlertTriangle: 'AlertTriangle',
    Check: 'Check',
    Loader2: 'Loader2',
    RefreshCw: 'RefreshCw',
    X: 'X',
  }
  return Object.fromEntries(
    Object.keys(icons).map((name) => [name, () => <span>{name}</span>]),
  )
})

vi.mock('@/shared/api', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api')>('@/shared/api')
  return {
    ...actual,
    MASKED_SECRET_VALUE: '__KEEP_EXISTING_SECRET__',
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    listAdminUsers: vi.fn(),
    listAdminAuditLogs: vi.fn(),
    createAdminUser: vi.fn(),
    updateAdminUser: vi.fn(),
    deleteAdminUser: vi.fn(),
    getWorkspaces: vi.fn(),
    getWorkspaceMembers: vi.fn(),
    replaceWorkspaceMembers: vi.fn(),
  }
})

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    vi.mocked(api.getSettings).mockResolvedValue({
      siliconflow_api_key: '',
      tavily_api_key: '',
      api_key: '',
      llm_model: 'deepseek-ai/DeepSeek-V4-Flash',
      embedding_model: 'BAAI/bge-m3',
      llm_temperature: 0.3,
      siliconflow_base_url: 'https://api.siliconflow.cn/v1',
      chunk_size: 1500,
      chunk_overlap: 50,
      top_k_retrieval: 5,
      top_k_rerank: 3,
      enable_quality_check: true,
      enable_contextual_retrieval: true,
    } as any)
    vi.mocked(api.updateSettings).mockResolvedValue({ updated: true, warnings: [], message: '' })
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: 'user-1',
        username: 'admin',
        role: 'admin',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 'user-2',
        username: 'viewer',
        role: 'viewer',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    vi.mocked(api.listAdminAuditLogs).mockResolvedValue([
      {
        id: 1,
        actor_user_id: 'user-2',
        action: 'job.queued',
        target_type: 'job',
        target_id: 'job-1',
        metadata: { job_type: 'ingest_url', workspace_id: 'ws-1' },
        created_at: '2026-01-01T08:30:00Z',
      },
      {
        id: 2,
        actor_user_id: 'user-2',
        action: 'document.url_import_queued',
        target_type: 'job',
        target_id: 'job-url-1',
        metadata: {
          job_type: 'ingest_url',
          workspace_id: 'ws-1',
          stream: false,
          scheme: 'https',
          host: 'example.com',
          url: 'https://example.com/page',
        },
        created_at: '2026-01-01T08:31:00Z',
      },
      {
        id: 3,
        actor_user_id: 'user-2',
        action: 'job.canceled',
        target_type: 'job',
        target_id: 'job-cancel-1',
        metadata: { job_type: 'ingest_url', workspace_id: 'ws-1' },
        created_at: '2026-01-01T08:32:00Z',
      },
    ])
    vi.mocked(api.createAdminUser).mockResolvedValue({
      id: 'user-3',
      username: 'editor',
      role: 'editor',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    vi.mocked(api.updateAdminUser).mockImplementation(async (_token, userId, body) => ({
      id: userId,
      username: 'admin',
      role: body.role ?? 'admin',
      is_active: body.is_active ?? true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }))
    vi.mocked(api.deleteAdminUser).mockResolvedValue({} as any)
    vi.mocked(api.getWorkspaces).mockResolvedValue([
      { id: 'ws-1', name: 'Alpha', description: '', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
    ])
    vi.mocked(api.getWorkspaceMembers).mockResolvedValue([])
    vi.mocked(api.replaceWorkspaceMembers).mockImplementation(async (_token, workspaceId, body) =>
      (body.members ?? []).map((member, index) => ({
        id: index + 1,
        workspace_id: workspaceId,
        user_id: member.user_id,
        username: member.user_id === 'user-2' ? 'viewer' : 'admin',
        role: member.role,
        created_at: '2026-01-01T00:00:00Z',
      })),
    )
  })

  it('shows provider information derived from current model settings', async () => {
    render(<SettingsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText(/当前供应商/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/SiliconFlow/)).toBeInTheDocument()
    expect(screen.getByText(/DeepSeek/)).toBeInTheDocument()
  })

  it('saves one settings group at a time', async () => {
    render(<SettingsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByDisplayValue('1500')).toBeInTheDocument()
    })

    const chunkSize = screen.getByDisplayValue('1500')
    fireEvent.change(chunkSize, { target: { value: '2048' } })

    await userEvent.click(screen.getByRole('button', { name: /保存检索设置/ }))

    await waitFor(() => {
      expect(api.updateSettings).toHaveBeenCalledWith({
        chunk_size: 2048,
        chunk_overlap: 50,
        top_k_retrieval: 5,
        top_k_rerank: 3,
      })
    })
  })

  it('allows saving chunk overlap as zero', async () => {
    render(<SettingsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByDisplayValue('50')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByDisplayValue('50'), { target: { value: '0' } })
    await userEvent.click(screen.getByRole('button', { name: /保存检索设置/ }))

    await waitFor(() => {
      expect(api.updateSettings).toHaveBeenCalledWith({
        chunk_size: 1500,
        chunk_overlap: 0,
        top_k_retrieval: 5,
        top_k_rerank: 3,
      })
    })
  })

  it('syncs the browser api key after saving the api settings group', async () => {
    render(<SettingsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByLabelText('系统 API Key')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('系统 API Key'), { target: { value: 'local-auth-key' } })
    await userEvent.click(screen.getByRole('button', { name: /保存API 密钥设置/ }))

    await waitFor(() => {
      expect(localStorage.getItem('knowbase_api_key')).toBe('local-auth-key')
    })
  })

  it('does not overwrite browser api key when the masked placeholder is saved unchanged', async () => {
    vi.mocked(api.getSettings).mockResolvedValueOnce({
      siliconflow_api_key: MASKED_SECRET_VALUE,
      tavily_api_key: MASKED_SECRET_VALUE,
      api_key: MASKED_SECRET_VALUE,
      llm_model: 'deepseek-ai/DeepSeek-V4-Flash',
      embedding_model: 'BAAI/bge-m3',
      llm_temperature: 0.3,
      siliconflow_base_url: 'https://api.siliconflow.cn/v1',
      chunk_size: 1500,
      chunk_overlap: 50,
      top_k_retrieval: 5,
      top_k_rerank: 3,
      enable_quality_check: true,
      enable_contextual_retrieval: true,
    } as any)
    localStorage.setItem('knowbase_api_key', 'existing-local-key')

    render(<SettingsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByLabelText('系统 API Key')).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /保存API 密钥设置/ }))

    await waitFor(() => {
      expect(localStorage.getItem('knowbase_api_key')).toBe('existing-local-key')
    })
  })

  it('loads and creates admin-managed users', async () => {
    render(<SettingsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await waitFor(() => {
      expect(api.listAdminUsers).toHaveBeenCalled()
      expect(screen.getAllByText('admin').length).toBeGreaterThan(0)
    })

    await userEvent.type(screen.getByLabelText('新用户用户名'), 'editor')
    await userEvent.type(screen.getByLabelText('新用户密码'), 'initial-pass')
    await userEvent.selectOptions(screen.getByLabelText('新用户角色'), 'editor')
    await userEvent.click(screen.getByRole('button', { name: '创建用户' }))

    await waitFor(() => {
      expect(api.createAdminUser).toHaveBeenCalledWith(undefined, {
        username: 'editor',
        password: 'initial-pass',
        role: 'editor',
        is_active: true,
      })
      expect(screen.getByText('editor')).toBeInTheDocument()
    })
  })

  it('updates a user role inline', async () => {
    render(<SettingsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByLabelText('admin 角色')).toBeInTheDocument()
    })

    await userEvent.selectOptions(screen.getByLabelText('admin 角色'), 'viewer')

    await waitFor(() => {
      expect(api.updateAdminUser).toHaveBeenCalledWith(undefined, 'user-1', { role: 'viewer' })
    })
  })

  it('adds and saves workspace members', async () => {
    render(<SettingsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await waitFor(() => {
      expect(api.getWorkspaceMembers).toHaveBeenCalledWith(undefined, 'ws-1')
      expect(screen.getByText('当前工作区暂无授权成员')).toBeInTheDocument()
    })

    await userEvent.selectOptions(screen.getByLabelText('添加工作区成员'), 'user-2')
    await userEvent.click(screen.getByRole('button', { name: '添加成员' }))
    await userEvent.selectOptions(screen.getByLabelText('viewer 工作区角色'), 'editor')
    await userEvent.click(screen.getByRole('button', { name: '保存授权' }))

    await waitFor(() => {
      expect(api.replaceWorkspaceMembers).toHaveBeenCalledWith(undefined, 'ws-1', {
        members: [{ user_id: 'user-2', role: 'editor' }],
      })
    })
  })

  it('lists and filters admin audit logs', async () => {
    render(<SettingsPage onOpenSidebar={vi.fn()} sidebarOpen onNavigate={vi.fn()} />)

    await waitFor(() => {
      expect(api.listAdminAuditLogs).toHaveBeenCalledWith(undefined, {
        actorUserId: undefined,
        limit: 50,
      })
      expect(screen.getByText('任务入队')).toBeInTheDocument()
      expect(screen.getByText('job.queued')).toBeInTheDocument()
      expect(screen.getByText('URL 导入入队')).toBeInTheDocument()
      expect(screen.getByText('document.url_import_queued')).toBeInTheDocument()
      expect(screen.getByText('任务取消')).toBeInTheDocument()
      expect(screen.getByText('job.canceled')).toBeInTheDocument()
    })

    await userEvent.selectOptions(screen.getByLabelText('审计日志用户过滤'), 'user-2')

    await waitFor(() => {
      expect(api.listAdminAuditLogs).toHaveBeenLastCalledWith(undefined, {
        actorUserId: 'user-2',
        limit: 50,
      })
    })
  })
})
