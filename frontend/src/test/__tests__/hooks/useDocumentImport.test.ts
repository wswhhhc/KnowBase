import { act, renderHook } from '@testing-library/react'
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
})
