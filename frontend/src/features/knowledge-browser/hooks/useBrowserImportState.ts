import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'

import type { BrowserVersionPrompt } from '@/features/knowledge-browser/hooks/useBrowserImport'

export function useBrowserImportState(fileInputRef: RefObject<HTMLInputElement | null>) {
  const guideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [urlInput, setUrlInput] = useState('')
  const [ingesting, setIngesting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadPhase, setUploadPhase] = useState('')
  const [uploadPercent, setUploadPercent] = useState(0)
  const [versionPrompted, setVersionPrompted] = useState<BrowserVersionPrompt | null>(null)
  const [showPostUploadGuide, setShowPostUploadGuide] = useState(false)
  const [lastImportedSource, setLastImportedSource] = useState<string | null>(null)

  const clearGuideTimer = useCallback(() => {
    if (guideTimerRef.current) {
      clearTimeout(guideTimerRef.current)
      guideTimerRef.current = null
    }
  }, [])

  const clearFileInput = useCallback(() => {
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [fileInputRef])

  const resetProgress = useCallback(() => {
    setUploading(false)
    setIngesting(false)
    setUploadPhase('')
    setUploadPercent(0)
  }, [])

  const showImportedSourceGuide = useCallback((sourceName: string) => {
    setLastImportedSource(sourceName)
    setShowPostUploadGuide(true)
    clearGuideTimer()
    guideTimerRef.current = setTimeout(() => setShowPostUploadGuide(false), 8000)
  }, [clearGuideTimer])

  const resetImportState = useCallback(() => {
    clearGuideTimer()
    setUrlInput('')
    setVersionPrompted(null)
    setShowPostUploadGuide(false)
    setLastImportedSource(null)
    resetProgress()
    clearFileInput()
  }, [clearFileInput, clearGuideTimer, resetProgress])

  useEffect(() => () => {
    clearGuideTimer()
  }, [clearGuideTimer])

  return {
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
  }
}
