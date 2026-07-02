import { useEffect, useState } from 'react'
import * as api from '@/lib/api'
import type { Conversation, DocSource, Workspace } from '@/lib/api'

export function useConversations(workspaceId?: string) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    try {
      const list = await api.getConversations(workspaceId)
      setConversations(list)
      return list
    } catch (e) {
      console.error('加载对话列表失败:', e)
      return []
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [workspaceId])

  const create = async () => {
    const conv = await api.createConversation('新对话', workspaceId)
    await refresh()
    setActiveId(conv.id)
    return conv
  }

  const remove = async (id: string) => {
    await api.deleteConversation(id)
    await refresh()
    if (activeId === id) setActiveId(null)
  }

  const rename = async (id: string, title: string) => {
    await api.renameConversation(id, title)
    await refresh()
  }

  return { conversations, activeId, setActiveId, create, remove, rename, refresh, loading }
}

export function useWorkspaces() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string>('')
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    try {
      const list = await api.getWorkspaces()
      setWorkspaces(list)
      // Auto-select default workspace ("") if no selection
      if (list.length > 0 && !activeWorkspaceId) {
        const defaultWs = list.find((ws) => ws.id === '') || list[0]
        setActiveWorkspaceId(defaultWs.id)
      }
      return list
    } catch (e) {
      console.error('加载工作区列表失败:', e)
      return []
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const create = async (name?: string) => {
    const ws = await api.createWorkspace(name)
    await refresh()
    setActiveWorkspaceId(ws.id)
    return ws
  }

  const remove = async (id: string) => {
    await api.deleteWorkspace(id)
    if (activeWorkspaceId === id) setActiveWorkspaceId('')
    await refresh()
  }

  const rename = async (id: string, name: string) => {
    await api.renameWorkspace(id, name)
    await refresh()
  }

  return { workspaces, activeWorkspaceId, setActiveWorkspaceId, create, remove, rename, refresh, loading }
}

export function useSources(workspaceId?: string) {
  const [sources, setSources] = useState<DocSource[]>([])
  const [sourceError, setSourceError] = useState<string | null>(null)
  const refresh = async (): Promise<boolean> => {
    try {
      setSources(await api.getSources(workspaceId))
      setSourceError(null)
      return true
    } catch (e) {
      console.error('加载来源列表失败:', e)
      setSourceError(e instanceof Error ? e.message : '未知错误')
      return false
    }
  }
  useEffect(() => { refresh() }, [workspaceId])
  return { sources, sourceError, refresh }
}
