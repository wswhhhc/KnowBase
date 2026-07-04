import { apiUrl, authHeaders, createApiErrorFromResponse } from '@/shared/api/client'
import { createChatStreamAdapter, SSEParser } from '@/shared/api/sse'
import type { ChatStreamCallbacks } from '@/shared/api/types'

export function chatStream(
  question: string,
  threadId: string | null,
  webSearchEnabled: boolean,
  searchStrategy: string,
  callbacks: ChatStreamCallbacks,
  pinnedChunkIds?: string[],
  excludedChunkIds?: string[],
  workspaceId?: string,
): AbortController {
  const controller = new AbortController()

  fetch(apiUrl('/chat/stream'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      question,
      thread_id: threadId,
      web_search_enabled: webSearchEnabled,
      search_strategy: searchStrategy,
      pinned_chunk_ids: pinnedChunkIds || [],
      excluded_chunk_ids: excludedChunkIds || [],
      workspace_id: workspaceId || '',
    }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        callbacks.onError?.((await createApiErrorFromResponse(res)).message)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      const parser = new SSEParser()
      const processSSEEvent = createChatStreamAdapter(callbacks)

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          for (const parsed of parser.flush()) {
            processSSEEvent(parsed.event, parsed.data)
          }
          break
        }

        const text = decoder.decode(value, { stream: true })
        for (const parsed of parser.feed(text)) {
          processSSEEvent(parsed.event, parsed.data)
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        callbacks.onError?.(err.message)
      }
    })

  return controller
}
