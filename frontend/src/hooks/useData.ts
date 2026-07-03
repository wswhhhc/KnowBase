import { useEffect, useRef, useState } from 'react'
import * as api from '@/lib/api'
import type { Conversation, DocSource, Workspace } from '@/lib/api'

const ACTIVE_WORKSPACE_STORAGE_KEY = 'knowbase-active-workspace'
const ACTIVE_CONVERSATION_STORAGE_PREFIX = 'knowbase-active-conversation:'
const DEFAULT_WORKSPACE_STORAGE_SCOPE = 'default'

function getConversationStorageKey(workspaceId?: string) {
  return `${ACTIVE_CONVERSATION_STORAGE_PREFIX}${workspaceId || DEFAULT_WORKSPACE_STORAGE_SCOPE}`
}

function readActiveWorkspaceId() {
  return localStorage.getItem(ACTIVE_WORKSPACE_STORAGE_KEY) || ''
}

function writeActiveWorkspaceId(workspaceId: string) {
  if (workspaceId) {
    localStorage.setItem(ACTIVE_WORKSPACE_STORAGE_KEY, workspaceId)
    return
  }
  localStorage.removeItem(ACTIVE_WORKSPACE_STORAGE_KEY)
}

function readActiveConversationId(workspaceId?: string) {
  return localStorage.getItem(getConversationStorageKey(workspaceId))
}

function writeActiveConversationId(workspaceId: string | undefined, conversationId: string | null) {
  const storageKey = getConversationStorageKey(workspaceId)
  if (conversationId) {
    localStorage.setItem(storageKey, conversationId)
    return
  }
  localStorage.removeItem(storageKey)
}

export function useConversations(workspaceId?: string) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveIdState] = useState<string | null>(() => readActiveConversationId(workspaceId))
  const [loading, setLoading] = useState(true)
  const requestTokenRef = useRef(0)

  const setActiveId = (nextActiveId: string | null) => {
    setActiveIdState(nextActiveId)
    writeActiveConversationId(workspaceId, nextActiveId)
  }

  const refresh = async (resetBeforeLoad = false) => {
    const requestToken = requestTokenRef.current + 1
    requestTokenRef.current = requestToken
    if (resetBeforeLoad) {
      setConversations([])
      setActiveIdState(null)
      setLoading(true)
    }
    try {
      const list = await api.getConversations(workspaceId)
      if (requestToken !== requestTokenRef.current) return []
      const persistedActiveId = readActiveConversationId(workspaceId)
      const nextActiveId = persistedActiveId && list.some((conversation) => conversation.id === persistedActiveId)
        ? persistedActiveId
        : activeId && list.some((conversation) => conversation.id === activeId)
          ? activeId
          : null
      setConversations(list)
      setActiveId(nextActiveId)
      return list
    } catch (e) {
      if (requestToken !== requestTokenRef.current) return []
      console.error('加载对话列表失败:', e)
      return []
    } finally {
      if (requestToken === requestTokenRef.current) {
        setLoading(false)
      }
    }
  }

  useEffect(() => {
    void refresh(true)
  }, [workspaceId])

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
  const [activeWorkspaceId, setActiveWorkspaceIdState] = useState<string>(() => readActiveWorkspaceId())
  const [loading, setLoading] = useState(true)

  const setActiveWorkspaceId = (nextWorkspaceId: string) => {
    setActiveWorkspaceIdState(nextWorkspaceId)
    writeActiveWorkspaceId(nextWorkspaceId)
  }

  const refresh = async () => {
    try {
      const list = await api.getWorkspaces()
      setWorkspaces(list)
      const persistedWorkspaceId = readActiveWorkspaceId()
      const nextWorkspaceId = persistedWorkspaceId && list.some((ws) => ws.id === persistedWorkspaceId)
        ? persistedWorkspaceId
        : activeWorkspaceId && list.some((ws) => ws.id === activeWorkspaceId)
          ? activeWorkspaceId
          : list.length > 0
            ? (list.find((ws) => ws.id === '') || list[0]).id
            : ''
      setActiveWorkspaceId(nextWorkspaceId)
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
  const requestTokenRef = useRef(0)

  const runRefresh = async (resetBeforeLoad = false): Promise<boolean> => {
    const requestToken = requestTokenRef.current + 1
    requestTokenRef.current = requestToken
    if (resetBeforeLoad) {
      setSources([])
      setSourceError(null)
    }
    try {
      const nextSources = await api.getSources(workspaceId)
      if (requestToken !== requestTokenRef.current) return false
      setSources(nextSources)
      setSourceError(null)
      return true
    } catch (e) {
      if (requestToken !== requestTokenRef.current) return false
      console.error('加载来源列表失败:', e)
      setSourceError(e instanceof Error ? e.message : '未知错误')
      return false
    }
  }

  const refresh = async (): Promise<boolean> => runRefresh(false)

  useEffect(() => {
    void runRefresh(true)
  }, [workspaceId])

  return { sources, sourceError, refresh }
}
