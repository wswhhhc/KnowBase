import { useState } from 'react'
import { toast } from 'sonner'
import * as api from '@/shared/api'

export type VersionPrompt =
  | { kind: 'file'; file: File; sourceName: string }
  | { kind: 'url'; url: string; sourceName: string }

export interface PostImportGuide {
  title: string
  description: string
  suggestedQuestions: string[]
}

export const PHASE_COPY: Record<string, { title: string; detail: string }> = {
  loading: {
    title: '正在读取资料并检查来源…',
    detail: '先确认文件或网页是否可解析，以及当前工作区里是否已经存在同名来源。',
  },
  splitting: {
    title: '正在切分为可检索片段…',
    detail: '把内容拆成更适合检索和引用的段落片段。',
  },
  embedding: {
    title: '正在写入向量索引…',
    detail: '生成检索向量并准备上传完成后的推荐问题。',
  },
  done: {
    title: '资料已处理完成',
    detail: '现在可以直接提问，或先去知识库核对原文来源。',
  },
}

interface UseDocumentImportOptions {
  workspaceId?: string
  workspaceName: string
  onRefresh: () => Promise<boolean>
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export function useDocumentImport({ workspaceId, workspaceName, onRefresh }: UseDocumentImportOptions) {
  const [urlInput, setUrlInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadPhase, setUploadPhase] = useState('')
  const [uploadPercent, setUploadPercent] = useState(0)
  const [postImportGuide, setPostImportGuide] = useState<PostImportGuide | null>(null)
  const [versionPrompt, setVersionPrompt] = useState<VersionPrompt | null>(null)
  const [demoImporting, setDemoImporting] = useState(false)

  const resetUploadState = () => {
    setUploading(false)
    setUploadPhase('')
    setUploadPercent(0)
  }

  const showGuide = (guide: PostImportGuide) => setPostImportGuide(guide)

  const importFile = async (file: File, versionMode?: string) => {
    setUploading(true)
    setUploadPhase('loading')
    setUploadPercent(0)
    setPostImportGuide(null)
    setVersionPrompt(null)
    try {
      const probe = await api.checkSource(file.name, workspaceId)
      if (probe.exists && !versionMode) {
        setVersionPrompt({ kind: 'file', file, sourceName: file.name })
        resetUploadState()
        return
      }

      const result = await api.uploadDocument(file, versionMode, workspaceId)
      if (!api.isJobCreateResponse(result) && result.existing_version && !versionMode) {
        setVersionPrompt({ kind: 'file', file, sourceName: file.name })
        resetUploadState()
        return
      }
      const importResult = await api.waitForImportJob(result, (phase, percent) => {
        setUploadPhase(phase)
        setUploadPercent(percent)
      })
      if (await onRefresh()) {
        const message = versionMode === 'replace' ? '文档已替换为新版本' : versionMode === 'append' ? '文档已追加新版本' : '文档已上传'
        toast.success(message, { description: file.name })
        showGuide({
          title: `资料已进入“${workspaceName}”`,
          description: `当前来源是“${file.name}”。可以直接发起第一个问题，或先去知识库核对原文。`,
          suggestedQuestions: importResult?.suggested_questions ?? [],
        })
      }
      resetUploadState()
    } catch (error) {
      toast.error('上传失败', { description: getErrorMessage(error) })
      resetUploadState()
    }
  }

  const importUrl = async (url: string, versionMode?: string) => {
    setUploading(true)
    setUploadPhase('loading')
    setUploadPercent(0)
    setVersionPrompt(null)
    try {
      const probe = await api.checkSource(url, workspaceId)
      if (probe.exists && !versionMode) {
        setVersionPrompt({ kind: 'url', url, sourceName: url })
        resetUploadState()
        return
      }
    } catch (error) {
      toast.error('导入前检查失败', { description: String(error) })
      resetUploadState()
      return
    }

    try {
      const result = await api.ingestUrl(url, versionMode, workspaceId)
      if (!api.isJobCreateResponse(result) && result.existing_version && !versionMode) {
        setVersionPrompt({ kind: 'url', url, sourceName: url })
        resetUploadState()
        return
      }
      const importResult = await api.waitForImportJob(result, (phase, percent) => {
        setUploadPhase(phase)
        setUploadPercent(percent)
      })
      setUrlInput('')
      if (await onRefresh()) {
        const message = versionMode === 'replace' ? '网页已替换为新版本' : versionMode === 'append' ? '网页已追加新版本' : '网页已导入'
        toast.success(message)
        showGuide({
          title: `资料已进入“${workspaceName}”`,
          description: `当前来源是“${url}”。你可以先去知识库核对原文，或直接基于这份资料发问。`,
          suggestedQuestions: importResult?.suggested_questions ?? [],
        })
      }
      resetUploadState()
    } catch (error) {
      toast.error('导入失败', { description: getErrorMessage(error) })
      resetUploadState()
    }
  }

  const importUrlInput = async () => {
    const url = urlInput.trim()
    if (url) await importUrl(url)
  }

  const importDemoDocuments = async () => {
    setDemoImporting(true)
    setPostImportGuide(null)
    try {
      const result = await api.importDemoDocuments(workspaceId)
      const importedSources = result.imported_sources ?? []
      if (await onRefresh()) {
        toast.success(result.message, { description: `${importedSources.length} 份示例资料` })
        showGuide({
          title: `示例资料已进入“${workspaceName}”`,
          description: `已导入 ${importedSources.join('、')}。你现在可以直接提问，或先去知识库确认来源。`,
          suggestedQuestions: result.suggested_questions ?? [],
        })
      }
    } catch (error) {
      toast.error('导入示例资料失败', { description: String(error) })
    } finally {
      setDemoImporting(false)
    }
  }

  const selectVersionMode = async (mode: 'replace' | 'append') => {
    if (!versionPrompt) return
    if (versionPrompt.kind === 'file') {
      await importFile(versionPrompt.file, mode)
      return
    }
    await importUrl(versionPrompt.url, mode)
  }

  const skipVersionPrompt = () => {
    setVersionPrompt(null)
    toast.info('已跳过，未重复导入')
  }

  return {
    urlInput,
    setUrlInput,
    uploading,
    uploadPhase,
    uploadPercent,
    postImportGuide,
    setPostImportGuide,
    versionPrompt,
    demoImporting,
    importFile,
    importUrl,
    importUrlInput,
    importDemoDocuments,
    selectVersionMode,
    skipVersionPrompt,
  }
}
