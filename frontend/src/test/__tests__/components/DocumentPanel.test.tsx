import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DocumentPanel from '@/components/sidebar/DocumentPanel'
import * as api from '@/shared/api'

function createJob(overrides: Partial<api.Job> = {}): api.Job {
  return {
    id: 'job-document-panel',
    job_type: 'ingest_file',
    status: 'queued',
    workspace_id: '',
    progress: { phase: 'queued', percent: 0, message: '' },
    error: '',
    attempts: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@/shared/api', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api')>('@/shared/api')
  return {
    ...actual,
    checkSource: vi.fn().mockResolvedValue({ exists: false }),
    uploadDocument: vi.fn().mockResolvedValue({
      job_id: 'job-document-panel',
      job: createJob(),
    }),
    uploadDocumentStream: vi.fn().mockImplementation((_file, _mode, callbacks) => {
      callbacks.onDone?.({
        chunk_count: 1,
        existing_version: false,
        suggested_questions: ['这份资料的核心结论是什么？'],
        imported_sources: ['demo.md'],
      })
      return { abort: vi.fn() }
    }),
    ingestUrl: vi.fn(),
    ingestUrlStream: vi.fn(),
    waitForImportJob: vi.fn().mockImplementation((_result, onProgress) => {
      onProgress('embedding', 60)
      onProgress('done', 100)
      return Promise.resolve(null)
    }),
    pollJob: vi.fn().mockImplementation((_jobId, options) => {
      options?.onUpdate?.(createJob({
        status: 'running',
        progress: { phase: 'embedding', percent: 60, message: '正在向量化' },
      }))
      return Promise.resolve(createJob({
        status: 'succeeded',
        progress: { phase: 'done', percent: 100, message: '完成' },
      }))
    }),
    importDemoDocuments: vi.fn().mockResolvedValue({
      chunk_count: 3,
      total_docs: 9,
      message: '已导入 3 份示例资料',
      imported_sources: ['contract_notice.md', 'meeting_notes.md', 'tech_manual.md'],
      suggested_questions: ['这组示例资料分别覆盖了什么主题？'],
    }),
    deleteSource: vi.fn(),
    clearKnowledgeBase: vi.fn(),
  }
})

describe('DocumentPanel', () => {
  const onRefresh = vi.fn().mockResolvedValue(true)
  const onSendQuestion = vi.fn()
  const onOpenKnowledgeBase = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    onRefresh.mockResolvedValue(true)
  })

  it('imports demo documents explicitly for the current workspace', async () => {
    render(
      <DocumentPanel
        sources={[]}
        onRefresh={onRefresh}
        workspaceId="ws-demo"
        workspaceName="演示工作区"
        onSendQuestion={onSendQuestion}
        onOpenKnowledgeBase={onOpenKnowledgeBase}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: '导入示例资料' }))

    await waitFor(() => {
      expect(api.importDemoDocuments).toHaveBeenCalledWith('ws-demo')
    })
    expect(screen.getByText('示例资料已进入“演示工作区”')).toBeInTheDocument()
    expect(screen.getByText('这组示例资料分别覆盖了什么主题？')).toBeInTheDocument()
  })

  it('supports dragging a file into the upload area', async () => {
    render(
      <DocumentPanel
        sources={[]}
        onRefresh={onRefresh}
        workspaceId=""
        workspaceName="默认工作区"
        onSendQuestion={onSendQuestion}
        onOpenKnowledgeBase={onOpenKnowledgeBase}
      />,
    )

    const dropzone = screen.getByText('拖拽文件到这里，或选择文件').closest('label')
    expect(dropzone).not.toBeNull()
    const file = new File(['drag-upload'], 'drag.txt', { type: 'text/plain' })

    fireEvent.drop(dropzone!, {
      dataTransfer: {
        files: [file],
      },
    })

    await waitFor(() => {
      expect(api.checkSource).toHaveBeenCalledWith('drag.txt', '')
      expect(api.uploadDocument).toHaveBeenCalledWith(
        expect.any(File),
        undefined,
        '',
      )
      expect(api.waitForImportJob).toHaveBeenCalledWith(
        expect.objectContaining({ job_id: 'job-document-panel' }),
        expect.any(Function),
      )
      expect(api.uploadDocumentStream).not.toHaveBeenCalled()
    })
  })

  it('shows sources but hides import and delete actions in read-only mode', () => {
    render(
      <DocumentPanel
        sources={[{ source: 'readonly.md', count: 2 } as any]}
        onRefresh={onRefresh}
        workspaceId="ws-viewer"
        workspaceName="只读工作区"
        canManageKnowledgeBase={false}
      />,
    )

    expect(screen.getByText('当前账号为只读权限')).toBeInTheDocument()
    expect(screen.getByText('readonly.md')).toBeInTheDocument()
    expect(screen.queryByText('导入示例资料')).not.toBeInTheDocument()
    expect(screen.queryByText('上传文档')).not.toBeInTheDocument()
    expect(screen.queryByPlaceholderText('https://…')).not.toBeInTheDocument()
    expect(screen.queryByText('清空')).not.toBeInTheDocument()
  })
})
