import { useCallback, type RefObject } from 'react'
import { toast } from 'sonner'

import * as api from '@/shared/api'
import { useBrowserImportState } from '@/features/knowledge-browser/hooks/useBrowserImportState'

type VersionMode = 'replace' | 'append'

export type BrowserVersionPrompt =
  | { kind: 'file'; file: File; sourceName: string }
  | { kind: 'url'; url: string; sourceName: string }

interface UseBrowserImportArgs {
  browserWsId: string
  fileInputRef: RefObject<HTMLInputElement | null>
  refreshData: () => Promise<void>
  focusSource: (sourceName: string) => Promise<void>
  isScopeCurrent: (token: number) => boolean
  getScopeToken: () => number
}

function createSuccessCopy(type: '文档' | '网页', versionMode?: VersionMode) {
  if (versionMode === 'replace') return `${type}已替换为新版本`
  if (versionMode === 'append') return `${type}已追加新版本`
  return `${type}已${type === '文档' ? '上传' : '导入'}`
}

export function useBrowserImport({
  browserWsId,
  fileInputRef,
  refreshData,
  focusSource,
  isScopeCurrent,
  getScopeToken,
}: UseBrowserImportArgs) {
  const {
    clearFileInput,
    ingesting,
    lastImportedSource,
    resetImportState,
    resetProgress,
    setIngesting,
    setUploadPercent,
    setUploadPhase,
    setUploading,
    setUrlInput,
    setVersionPrompted,
    setShowPostUploadGuide,
    showImportedSourceGuide,
    showPostUploadGuide,
    uploadPercent,
    uploadPhase,
    uploading,
    urlInput,
    versionPrompted,
  } = useBrowserImportState(fileInputRef)

  const startUpload = useCallback(async (file: File, versionMode?: VersionMode) => {
    const scopeToken = getScopeToken()
    setUploading(true)
    setUploadPhase('loading')
    setUploadPercent(0)
    setVersionPrompted(null)
    try {
      const probe = await api.checkSource(file.name, browserWsId)
      if (!isScopeCurrent(scopeToken)) return
      if (probe.exists && !versionMode) {
        setVersionPrompted({ kind: 'file', file, sourceName: file.name })
        resetProgress()
        return
      }
    } catch {
      if (isScopeCurrent(scopeToken)) {
        toast.error('上传前检查失败')
        resetProgress()
      }
      return
    }

    api.uploadDocumentStream(file, versionMode, {
      onProgress: (phase, pct) => {
        if (!isScopeCurrent(scopeToken)) return
        setUploadPhase(phase)
        setUploadPercent(pct)
      },
      onDone: async (result) => {
        if (!isScopeCurrent(scopeToken)) return
        if (result.existing_version && !versionMode) {
          setVersionPrompted({ kind: 'file', file, sourceName: file.name })
          resetProgress()
          return
        }
        await refreshData()
        if (!isScopeCurrent(scopeToken)) return
        await focusSource(file.name)
        if (!isScopeCurrent(scopeToken)) return
        showImportedSourceGuide(file.name)
        toast.success(createSuccessCopy('文档', versionMode), { description: file.name })
        resetProgress()
        clearFileInput()
      },
      onError: (msg) => {
        if (!isScopeCurrent(scopeToken)) return
        toast.error('上传失败', { description: msg })
        resetProgress()
        clearFileInput()
      },
    }, browserWsId)
  }, [
    browserWsId,
    clearFileInput,
    focusSource,
    getScopeToken,
    isScopeCurrent,
    refreshData,
    resetProgress,
    showImportedSourceGuide,
  ])

  const startUrlIngest = useCallback(async (url: string, versionMode?: VersionMode) => {
    const scopeToken = getScopeToken()
    setIngesting(true)
    setUploadPhase('loading')
    setUploadPercent(0)
    setVersionPrompted(null)
    try {
      const probe = await api.checkSource(url, browserWsId)
      if (!isScopeCurrent(scopeToken)) return
      if (probe.exists && !versionMode) {
        setVersionPrompted({ kind: 'url', url, sourceName: url })
        resetProgress()
        return
      }
    } catch {
      if (isScopeCurrent(scopeToken)) {
        toast.error('导入前检查失败')
        resetProgress()
      }
      return
    }

    api.ingestUrlStream(url, versionMode, {
      onProgress: (phase, pct) => {
        if (!isScopeCurrent(scopeToken)) return
        setUploadPhase(phase)
        setUploadPercent(pct)
      },
      onDone: async (result) => {
        if (!isScopeCurrent(scopeToken)) return
        if (result.existing_version && !versionMode) {
          setVersionPrompted({ kind: 'url', url, sourceName: url })
          resetProgress()
          return
        }
        setUrlInput('')
        await refreshData()
        if (!isScopeCurrent(scopeToken)) return
        await focusSource(url)
        if (!isScopeCurrent(scopeToken)) return
        showImportedSourceGuide(url)
        toast.success(createSuccessCopy('网页', versionMode))
        resetProgress()
      },
      onError: (msg) => {
        if (!isScopeCurrent(scopeToken)) return
        toast.error('导入失败', { description: msg })
        resetProgress()
      },
    }, browserWsId)
  }, [
    browserWsId,
    focusSource,
    getScopeToken,
    isScopeCurrent,
    refreshData,
    resetProgress,
    showImportedSourceGuide,
  ])

  return {
    urlInput,
    setUrlInput,
    ingesting,
    uploading,
    uploadPhase,
    uploadPercent,
    versionPrompted,
    setVersionPrompted,
    showPostUploadGuide,
    setShowPostUploadGuide,
    lastImportedSource,
    resetImportState,
    startUpload,
    startUrlIngest,
  }
}
