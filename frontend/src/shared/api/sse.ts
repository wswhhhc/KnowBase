import type { ChatStreamCallbacks } from '@/shared/api/types'

export class SSEParser {
  private buffer = ''
  private currentEvent = 'message'
  private currentData: string[] = []

  feed(chunk: string): Array<{ event: string; data: string }> {
    this.buffer += chunk.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
    const events: Array<{ event: string; data: string }> = []
    const lines = this.buffer.split('\n')
    this.buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        this.currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        this.currentData.push(line.slice(6))
      } else if (line === '') {
        if (this.currentData.length > 0) {
          events.push({
            event: this.currentEvent,
            data: this.currentData.join('\n'),
          })
        }
        this.currentEvent = 'message'
        this.currentData = []
      }
    }
    return events
  }

  flush(): Array<{ event: string; data: string }> {
    if (this.currentData.length > 0) {
      const events = [{
        event: this.currentEvent,
        data: this.currentData.join('\n'),
      }]
      this.currentEvent = 'message'
      this.currentData = []
      return events
    }
    return []
  }
}

export function handleSSEEvent(
  event: string,
  data: string,
  callbacks: {
    onProgress?: (phase: string, percent: number) => void
    onDone?: (result: any) => void
    onError?: (message: string) => void
  },
) {
  try {
    const parsed = JSON.parse(data)
    switch (event) {
      case 'progress':
        callbacks.onProgress?.(parsed.phase, parsed.percent)
        break
      case 'done':
        callbacks.onDone?.(parsed)
        break
      case 'error':
        callbacks.onError?.(parsed.message)
        break
    }
  } catch {
    // Ignore malformed SSE payloads so the stream can continue.
  }
}

export function createChatStreamAdapter(callbacks: ChatStreamCallbacks) {
  return (event: string, data: string) => {
    try {
      const parsed = JSON.parse(data)
      switch (event) {
        case 'node':
          callbacks.onNode?.(parsed.label, parsed.nodes)
          break
        case 'token':
          callbacks.onToken?.(parsed.text)
          break
        case 'debug':
          callbacks.onDebug?.(parsed)
          break
        case 'sources':
          callbacks.onSources?.(parsed)
          break
        case 'done':
          callbacks.onDone?.(parsed)
          break
        case 'error':
          callbacks.onError?.(parsed.message)
          break
      }
    } catch {
      // Ignore malformed SSE payloads so the stream can continue.
    }
  }
}
