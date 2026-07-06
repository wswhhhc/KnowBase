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
    createAdminUser: vi.fn(),
    updateAdminUser: vi.fn(),
    deleteAdminUser: vi.fn(),
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
    ])
    vi.mocked(api.createAdminUser).mockResolvedValue({
      id: 'user-2',
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
      expect(screen.getByText('admin')).toBeInTheDocument()
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
})
