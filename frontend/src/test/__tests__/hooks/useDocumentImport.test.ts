import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import * as api from '@/shared/api'
import { useDocumentImport } from '@/features/documents/hooks/useDocumentImport'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/shared/api', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api')>('@/shared/api')
  return {
    ...actual,
    checkSource: vi.fn(),
    uploadDocument: vi.fn(),
    ingestUrl: vi.fn(),
    waitForImportJob: vi.fn(),
    importDemoDocuments: vi.fn(),
  }
})

describe('useDocumentImport', () => {
  const onRefresh = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    onRefresh.mockResolvedValue(true)
  })

  it('prompts for a version mode before submitting an existing file source', async () => {
    vi.mocked(api.checkSource).mockResolvedValue({ exists: true })
    const { result } = renderHook(() => useDocumentImport({ workspaceId: 'ws-a', workspaceName: 'Alpha', onRefresh }))

    await act(async () => {
      await result.current.importFile(new File(['content'], 'policy.md', { type: 'text/plain' }))
    })

    expect(result.current.versionPrompt).toEqual({ kind: 'file', file: expect.any(File), sourceName: 'policy.md' })
    expect(api.uploadDocument).not.toHaveBeenCalled()
  })

  it('does not show a success guide when refresh fails after a URL import', async () => {
    vi.mocked(api.checkSource).mockResolvedValue({ exists: false })
    vi.mocked(api.ingestUrl).mockResolvedValue({ job_id: 'job-1', job: {} as api.Job })
    vi.mocked(api.waitForImportJob).mockResolvedValue({ suggested_questions: ['问题'] } as any)
    onRefresh.mockResolvedValue(false)
    const { result } = renderHook(() => useDocumentImport({ workspaceId: 'ws-a', workspaceName: 'Alpha', onRefresh }))

    await act(async () => {
      await result.current.importUrl('https://example.com/page')
    })

    expect(result.current.postImportGuide).toBeNull()
    expect(toast.success).not.toHaveBeenCalled()
  })

  it('submits the retained file with append mode after a version prompt', async () => {
    vi.mocked(api.checkSource).mockResolvedValue({ exists: true })
    vi.mocked(api.uploadDocument).mockResolvedValue({ job_id: 'job-append', job: {} as api.Job })
    vi.mocked(api.waitForImportJob).mockResolvedValue(null)
    const file = new File(['content'], 'policy.md', { type: 'text/plain' })
    const { result } = renderHook(() => useDocumentImport({ workspaceId: 'ws-a', workspaceName: 'Alpha', onRefresh }))

    await act(async () => {
      await result.current.importFile(file)
    })
    await act(async () => {
      await result.current.selectVersionMode('append')
    })

    expect(api.uploadDocument).toHaveBeenCalledWith(file, 'append', 'ws-a')
    expect(toast.success).toHaveBeenCalledWith('文档已追加新版本', { description: 'policy.md' })
  })

  it('clears the version prompt when the duplicate import is skipped', async () => {
    vi.mocked(api.checkSource).mockResolvedValue({ exists: true })
    const { result } = renderHook(() => useDocumentImport({ workspaceId: 'ws-a', workspaceName: 'Alpha', onRefresh }))

    await act(async () => {
      await result.current.importFile(new File(['content'], 'policy.md', { type: 'text/plain' }))
    })
    act(() => result.current.skipVersionPrompt())

    expect(result.current.versionPrompt).toBeNull()
    expect(toast.info).toHaveBeenCalledWith('已跳过，未重复导入')
  })

  it('exposes queued progress updates in callback order before resetting', async () => {
    vi.mocked(api.checkSource).mockResolvedValue({ exists: false })
    vi.mocked(api.uploadDocument).mockResolvedValue({ job_id: 'job-progress', job: {} as api.Job })
    let onProgress: ((phase: string, percent: number) => void) | undefined
    let finishJob: ((value: null) => void) | undefined
    vi.mocked(api.waitForImportJob).mockImplementation((_job, callback) => {
      onProgress = callback
      return new Promise((resolve) => { finishJob = resolve })
    })
    const { result } = renderHook(() => useDocumentImport({ workspaceId: 'ws-a', workspaceName: 'Alpha', onRefresh }))

    let importPromise: Promise<void>
    act(() => {
      importPromise = result.current.importFile(new File(['content'], 'policy.md', { type: 'text/plain' }))
    })
    await waitFor(() => expect(onProgress).toBeDefined())

    act(() => onProgress?.('embedding', 60))
    expect(result.current.uploadPhase).toBe('embedding')
    expect(result.current.uploadPercent).toBe(60)

    act(() => onProgress?.('done', 100))
    expect(result.current.uploadPhase).toBe('done')
    expect(result.current.uploadPercent).toBe(100)

    await act(async () => {
      finishJob?.(null)
      await importPromise!
    })
    expect(result.current.uploadPhase).toBe('')
    expect(result.current.uploadPercent).toBe(0)
  })

  it('imports demo documents and exposes the completion guide', async () => {
    vi.mocked(api.importDemoDocuments).mockResolvedValue({
      chunk_count: 3,
      total_docs: 3,
      message: '示例已导入',
      imported_sources: ['demo.md'],
      suggested_questions: ['示例讲了什么？'],
    })
    const { result } = renderHook(() => useDocumentImport({ workspaceId: 'ws-a', workspaceName: 'Alpha', onRefresh }))

    await act(async () => result.current.importDemoDocuments())

    expect(api.importDemoDocuments).toHaveBeenCalledWith('ws-a')
    expect(result.current.postImportGuide?.suggestedQuestions).toEqual(['示例讲了什么？'])
  })
})
