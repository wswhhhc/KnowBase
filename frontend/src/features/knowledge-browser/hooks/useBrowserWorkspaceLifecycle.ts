import { useEffect, type RefObject } from 'react'
import { toast } from 'sonner'

import { UPLOAD_TRIGGER_EVENT } from '@/lib/ui-events'

interface UseBrowserWorkspaceLifecycleArgs {
  browserWsId: string
  fileInputRef: RefObject<HTMLInputElement | null>
  isScopeCurrent: (scopeToken: number) => boolean
  loadInitialCatalogData: (scopeToken: number) => Promise<boolean>
  nextScopeToken: () => number
  resetCatalogState: () => void
  resetImportState: () => void
  setError: (value: string | null) => void
  setHotspotMode: (value: boolean) => void
  setHotspots: (value: Map<string, number>) => void
  setLoading: (value: boolean) => void
}

function triggerPendingUpload(fileInputRef: RefObject<HTMLInputElement | null>) {
  if (sessionStorage.getItem('kb_trigger_upload') !== 'true') return
  sessionStorage.removeItem('kb_trigger_upload')
  requestAnimationFrame(() => fileInputRef.current?.click())
}

export function useBrowserWorkspaceLifecycle({
  browserWsId,
  fileInputRef,
  isScopeCurrent,
  loadInitialCatalogData,
  nextScopeToken,
  resetCatalogState,
  resetImportState,
  setError,
  setHotspotMode,
  setHotspots,
  setLoading,
}: UseBrowserWorkspaceLifecycleArgs) {
  useEffect(() => {
    const scopeToken = nextScopeToken()
    resetCatalogState()
    setHotspotMode(false)
    setHotspots(new Map())
    resetImportState()
    setLoading(true)

    loadInitialCatalogData(scopeToken)
      .catch((errorValue) => {
        if (!isScopeCurrent(scopeToken)) return
        setError(String(errorValue))
        toast.error('加载失败', { description: String(errorValue) })
      })
      .finally(() => {
        if (!isScopeCurrent(scopeToken)) return
        triggerPendingUpload(fileInputRef)
        setLoading(false)
      })
  }, [
    browserWsId,
    fileInputRef,
    isScopeCurrent,
    loadInitialCatalogData,
    nextScopeToken,
    resetCatalogState,
    resetImportState,
    setError,
    setHotspotMode,
    setHotspots,
    setLoading,
  ])

  useEffect(() => {
    const handler = () => triggerPendingUpload(fileInputRef)
    window.addEventListener(UPLOAD_TRIGGER_EVENT, handler)
    return () => window.removeEventListener(UPLOAD_TRIGGER_EVENT, handler)
  }, [fileInputRef])
}
