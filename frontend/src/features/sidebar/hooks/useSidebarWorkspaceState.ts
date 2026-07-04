import { useCallback, useEffect, useMemo, useState } from 'react'

import { useConversations, useSources, useWorkspaces } from '@/hooks/useData'
import type { WorkspaceSummary } from '@/types/workspace-summary'

export const DEFAULT_WORKSPACE_SELECT_VALUE = '__default_workspace__'

interface UseSidebarWorkspaceStateArgs {
  convs: ReturnType<typeof useConversations>
  onWorkspaceChange?: (workspaceId: string) => void
  onWorkspaceSummaryChange?: (summary: WorkspaceSummary) => void
  srcs: ReturnType<typeof useSources>
  wss: ReturnType<typeof useWorkspaces>
}

export function useSidebarWorkspaceState({
  convs,
  onWorkspaceChange,
  onWorkspaceSummaryChange,
  srcs,
  wss,
}: UseSidebarWorkspaceStateArgs) {
  const [createOpen, setCreateOpen] = useState(false)
  const [createName, setCreateName] = useState('')
  const [deleteWsOpen, setDeleteWsOpen] = useState(false)

  const activeWorkspace = useMemo(
    () => wss.workspaces.find((workspace) => workspace.id === wss.activeWorkspaceId),
    [wss.activeWorkspaceId, wss.workspaces],
  )

  const activeWorkspaceName = activeWorkspace?.name || '默认工作区'
  const workspaceScopeKey = wss.activeWorkspaceId || DEFAULT_WORKSPACE_SELECT_VALUE
  const workspaceSelectValue = wss.activeWorkspaceId || DEFAULT_WORKSPACE_SELECT_VALUE

  useEffect(() => {
    onWorkspaceSummaryChange?.({
      workspaceName: activeWorkspaceName,
      documentCount: srcs.sources.length,
      conversationCount: convs.conversations.length,
    })
  }, [
    activeWorkspaceName,
    convs.conversations.length,
    onWorkspaceSummaryChange,
    srcs.sources.length,
  ])

  useEffect(() => {
    onWorkspaceChange?.(wss.activeWorkspaceId)
  }, [onWorkspaceChange, wss.activeWorkspaceId])

  const handleWorkspaceValueChange = useCallback((value: string) => {
    const workspaceId = value === DEFAULT_WORKSPACE_SELECT_VALUE ? '' : value
    const nextWorkspace = wss.workspaces.find((workspace) => workspace.id === workspaceId)

    wss.setActiveWorkspaceId(workspaceId)
    onWorkspaceSummaryChange?.({
      workspaceName: nextWorkspace?.name || '默认工作区',
      documentCount: 0,
      conversationCount: 0,
    })
    onWorkspaceChange?.(workspaceId)
  }, [onWorkspaceChange, onWorkspaceSummaryChange, wss])

  const openCreateDialog = useCallback(() => {
    setCreateName('')
    setCreateOpen(true)
  }, [])

  const closeCreateDialog = useCallback(() => {
    setCreateOpen(false)
  }, [])

  const submitCreateWorkspace = useCallback(() => {
    const nextName = createName.trim()
    if (!nextName) return
    wss.create(nextName)
    setCreateOpen(false)
  }, [createName, wss])

  const requestDeleteWorkspace = useCallback(() => {
    setDeleteWsOpen(true)
  }, [])

  return {
    activeWorkspaceName,
    createName,
    createOpen,
    deleteWsOpen,
    requestDeleteWorkspace,
    closeCreateDialog,
    openCreateDialog,
    setCreateName,
    setCreateOpen,
    setDeleteWsOpen,
    submitCreateWorkspace,
    workspaceScopeKey,
    workspaceSelectValue,
    handleWorkspaceValueChange,
  }
}
