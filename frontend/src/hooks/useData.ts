import { useEffect, useState } from 'react'
import * as api from '@/lib/api'
import type { Conversation, DocSource } from '@/lib/api'

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    try {
      const list = await api.getConversations()
      setConversations(list)
      return list
    } catch (e) {
      console.error('加载对话列表失败:', e)
      return []
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const create = async () => {
    const conv = await api.createConversation()
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

export function useSources() {
  const [sources, setSources] = useState<DocSource[]>([])
  const [sourceError, setSourceError] = useState<string | null>(null)
  const refresh = async (): Promise<boolean> => {
    try {
      setSources(await api.getSources())
      setSourceError(null)
      return true
    } catch (e) {
      console.error('加载来源列表失败:', e)
      setSourceError(e instanceof Error ? e.message : '未知错误')
      return false
    }
  }
  useEffect(() => { refresh() }, [])
  return { sources, sourceError, refresh }
}
