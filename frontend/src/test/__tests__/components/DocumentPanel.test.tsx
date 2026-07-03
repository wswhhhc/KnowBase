import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DocumentPanel from '@/components/sidebar/DocumentPanel'
import * as api from '@/lib/api'

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@/lib/api', () => ({
  checkSource: vi.fn().mockResolvedValue({ exists: false }),
  uploadDocumentStream: vi.fn().mockImplementation((_file, _mode, callbacks) => {
    callbacks.onDone?.({
      chunk_count: 1,
      existing_version: false,
      suggested_questions: ['这份资料的核心结论是什么？'],
      imported_sources: ['demo.md'],
    })
    return { abort: vi.fn() }
  }),
  ingestUrlStream: vi.fn(),
  importDemoDocuments: vi.fn().mockResolvedValue({
    chunk_count: 3,
    total_docs: 9,
    message: '已导入 3 份示例资料',
    imported_sources: ['contract_notice.md', 'meeting_notes.md', 'tech_manual.md'],
    suggested_questions: ['这组示例资料分别覆盖了什么主题？'],
  }),
  deleteSource: vi.fn(),
  clearKnowledgeBase: vi.fn(),
}))

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
      expect(api.uploadDocumentStream).toHaveBeenCalledWith(
        expect.any(File),
        undefined,
        expect.objectContaining({
          onProgress: expect.any(Function),
          onDone: expect.any(Function),
          onError: expect.any(Function),
        }),
        '',
      )
    })
  })
})
