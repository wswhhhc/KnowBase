import { useCallback, useState } from 'react'
import type { PinState } from './types'
import type { ChatMessage, PinnedSource } from './types'

export function usePinnedSourcesState() {
  const [pinnedByConversation, setPinnedByConversation] = useState<Record<string, PinnedSource[]>>({})

  const getPinnedSources = useCallback(
    (threadId: string | null) => (threadId ? pinnedByConversation[threadId] ?? [] : []),
    [pinnedByConversation],
  )

  const setCurrentPinnedSources = useCallback(
    (threadId: string | null, updater: PinnedSource[] | ((previous: PinnedSource[]) => PinnedSource[])) => {
      if (!threadId) return
      setPinnedByConversation((previous) => {
        const current = previous[threadId] ?? []
        const next = typeof updater === 'function' ? updater(current) : updater
        return { ...previous, [threadId]: next }
      })
    },
    [],
  )

  const mergeSourcesForConversation = useCallback((threadId: string, sources: Array<Record<string, any>>) => {
    setPinnedByConversation((previous) => {
      const current = previous[threadId] ?? []
      const existingByChunkId = new Map(current.map((source) => [source.chunk_id, source]))
      const nextEntries = sources
        .filter((source) => source.chunk_id && !existingByChunkId.has(source.chunk_id))
        .map((source) => ({
          chunk_id: source.chunk_id,
          source: source.source || '',
          content: source.content || '',
          pinned: false,
          excluded: false,
          score: source.score ?? 0,
          index: source.index ?? 0,
        }))

      return nextEntries.length > 0
        ? { ...previous, [threadId]: [...current, ...nextEntries] }
        : previous
    })
  }, [])

  const hydrateConversationPinnedSources = useCallback((threadId: string, messages: ChatMessage[], pinState?: PinState) => {
    const hasExplicitPinState = pinState !== undefined
    const explicitPinnedIds = new Set<string>(pinState?.pinned_chunk_ids || [])
    const explicitExcludedIds = new Set<string>(pinState?.excluded_chunk_ids || [])
    const loaded: PinnedSource[] = []
    const seen = new Set<string>()

    for (const message of messages) {
      const debugData = message.debugData as Record<string, any> | undefined
      const legacyPinnedIds = new Set<string>(debugData?.pinned || [])
      const legacyExcludedIds = new Set<string>(debugData?.excluded || [])

      for (const source of message.sources || []) {
        if (source.chunk_id && !seen.has(source.chunk_id)) {
          seen.add(source.chunk_id)
          loaded.push({
            chunk_id: source.chunk_id,
            source: source.source || '',
            content: source.content || '',
            pinned: hasExplicitPinState ? explicitPinnedIds.has(source.chunk_id) : legacyPinnedIds.has(source.chunk_id),
            excluded: hasExplicitPinState ? explicitExcludedIds.has(source.chunk_id) : legacyExcludedIds.has(source.chunk_id),
            score: source.score ?? 0,
            index: source.index ?? 0,
          })
        }
      }
    }

    setPinnedByConversation((previous) => ({ ...previous, [threadId]: loaded }))
  }, [])

  return {
    getPinnedSources,
    setCurrentPinnedSources,
    mergeSourcesForConversation,
    hydrateConversationPinnedSources,
  }
}
