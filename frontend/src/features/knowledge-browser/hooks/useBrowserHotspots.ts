import { useCallback, useState } from 'react'
import { toast } from 'sonner'

import * as api from '@/shared/api'

export function useBrowserHotspots(
  browserWsId: string,
  isScopeCurrent: (token: number) => boolean,
  getScopeToken: () => number,
) {
  const [hotspotMode, setHotspotMode] = useState(false)
  const [hotspots, setHotspots] = useState<Map<string, number>>(new Map())

  const toggleHotspotMode = useCallback(async () => {
    const scopeToken = getScopeToken()
    const next = !hotspotMode
    setHotspotMode(next)
    if (!next) {
      setHotspots(new Map())
      return
    }
    try {
      const data = await api.getKBHotspots(browserWsId)
      if (!isScopeCurrent(scopeToken)) return
      setHotspots(new Map(data.map((h) => [h.chunk_id, h.hits] as [string, number])))
    } catch (e) {
      if (isScopeCurrent(scopeToken)) {
        toast.error('热点数据加载失败', { description: String(e) })
      }
    }
  }, [browserWsId, getScopeToken, hotspotMode, isScopeCurrent])

  const hotspotCount = useCallback((chunkId: string) => hotspots.get(chunkId) || 0, [hotspots])

  return {
    hotspotMode,
    setHotspotMode,
    hotspots,
    setHotspots,
    toggleHotspotMode,
    hotspotCount,
  }
}
