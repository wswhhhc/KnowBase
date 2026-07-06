import { apiUrl, authHeaders, createApiErrorFromResponse, req, withWorkspaceScope } from '@/shared/api/client'
import { handleSSEEvent, SSEParser } from '@/shared/api/sse'
import type { DemoImportResponse, DocSource, IngestResponse, JobCreateResponse } from '@/shared/api/types'

export const checkSource = (sourceName: string, workspaceId?: string) => {
  const params = new URLSearchParams({ source_name: sourceName })
  return req<{ exists: boolean }>(withWorkspaceScope('/documents/check-source', workspaceId, params))
}

export const getSources = (workspaceId?: string) =>
  req<DocSource[]>(withWorkspaceScope('/documents/sources', workspaceId))

export const uploadDocument = async (file: File, versionMode?: string, workspaceId?: string) => {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams()
  if (versionMode) params.set('version_mode', versionMode)
  const res = await fetch(apiUrl(withWorkspaceScope('/documents/upload', workspaceId, params)), {
    method: 'POST',
    body: form,
    headers: authHeaders(),
  })
  if (!res.ok) throw await createApiErrorFromResponse(res)
  return res.json()
}

export function uploadDocumentStream(
  file: File,
  versionMode: string | undefined,
  callbacks: {
    onProgress?: (phase: string, percent: number) => void
    onDone?: (result: any) => void
    onError?: (message: string) => void
  },
  workspaceId?: string,
): AbortController {
  const controller = new AbortController()
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams()
  if (versionMode) params.set('version_mode', versionMode)

  fetch(apiUrl(withWorkspaceScope('/documents/upload-stream', workspaceId, params)), {
    method: 'POST',
    body: form,
    headers: authHeaders(),
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
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          for (const parsed of parser.flush()) {
            handleSSEEvent(parsed.event, parsed.data, callbacks)
          }
          break
        }
        const text = decoder.decode(value, { stream: true })
        for (const parsed of parser.feed(text)) {
          handleSSEEvent(parsed.event, parsed.data, callbacks)
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') callbacks.onError?.(err.message)
    })
  return controller
}

export function ingestUrlStream(
  url: string,
  versionMode: string | undefined,
  callbacks: {
    onProgress?: (phase: string, percent: number) => void
    onDone?: (result: any) => void
    onError?: (message: string) => void
  },
  workspaceId?: string,
): AbortController {
  const controller = new AbortController()
  const params = new URLSearchParams()
  if (versionMode) params.set('version_mode', versionMode)

  fetch(apiUrl(withWorkspaceScope('/documents/ingest-url-stream', workspaceId, params)), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ url }),
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
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          for (const parsed of parser.flush()) {
            handleSSEEvent(parsed.event, parsed.data, callbacks)
          }
          break
        }
        const text = decoder.decode(value, { stream: true })
        for (const parsed of parser.feed(text)) {
          handleSSEEvent(parsed.event, parsed.data, callbacks)
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') callbacks.onError?.(err.message)
    })
  return controller
}

export const ingestUrl = (url: string, versionMode?: string, workspaceId?: string) => {
  const params = new URLSearchParams()
  if (versionMode) params.set('version_mode', versionMode)
  return req<IngestResponse | JobCreateResponse>(withWorkspaceScope('/documents/ingest-url', workspaceId, params), {
    method: 'POST',
    body: JSON.stringify({ url }),
  })
}

export const deleteSource = (source: string, workspaceId?: string) =>
  req(withWorkspaceScope(`/documents/source/${encodeURIComponent(source)}`, workspaceId), { method: 'DELETE' })

export const clearKnowledgeBase = (workspaceId?: string) =>
  req(withWorkspaceScope('/documents/clear', workspaceId), { method: 'POST' })

export const importDemoDocuments = (workspaceId?: string) =>
  req<DemoImportResponse>(withWorkspaceScope('/documents/import-demo', workspaceId), { method: 'POST' })
