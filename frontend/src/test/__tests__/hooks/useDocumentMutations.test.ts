import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import * as api from '@/shared/api'
import { useDocumentMutations } from '@/features/documents/hooks/useDocumentMutations'

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

vi.mock('@/shared/api', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api')>('@/shared/api')
  return { ...actual, deleteSource: vi.fn(), clearKnowledgeBase: vi.fn(), waitForImportJob: vi.fn() }
})

describe('useDocumentMutations', () => {
  const onRefresh = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    onRefresh.mockResolvedValue(true)
  })

  it('deletes a source and refreshes before showing success', async () => {
    vi.mocked(api.deleteSource).mockResolvedValue({} as any)
    const { result } = renderHook(() => useDocumentMutations({ workspaceId: 'ws-a', onRefresh }))

    await act(async () => {
      await result.current.deleteSource('policy.md')
    })

    expect(api.deleteSource).toHaveBeenCalledWith('policy.md', 'ws-a')
    expect(onRefresh).toHaveBeenCalledOnce()
    expect(toast.success).toHaveBeenCalledWith('已删除引用文档')
  })

  it('waits for the clear job before refreshing', async () => {
    vi.mocked(api.clearKnowledgeBase).mockResolvedValue({ job_id: 'job-clear', job: {} as api.Job })
    vi.mocked(api.waitForImportJob).mockResolvedValue(null)
    const { result } = renderHook(() => useDocumentMutations({ workspaceId: 'ws-a', onRefresh }))

    await act(async () => {
      await result.current.clearKnowledgeBase()
    })

    expect(api.waitForImportJob).toHaveBeenCalledWith(expect.objectContaining({ job_id: 'job-clear' }), expect.any(Function))
    expect(onRefresh).toHaveBeenCalledOnce()
  })
})
