import { req } from '@/shared/api/client'
import type { Job } from '@/shared/api/types'

const TERMINAL_JOB_STATUSES = new Set(['succeeded', 'failed', 'canceled'])

export const listJobs = () => req<Job[]>('/jobs')

export const getJob = (jobId: string) =>
  req<Job>(`/jobs/${encodeURIComponent(jobId)}`)

export const cancelJob = (jobId: string) =>
  req<Job>(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' })

export function isTerminalJob(job: Pick<Job, 'status'>): boolean {
  return TERMINAL_JOB_STATUSES.has(job.status)
}

export async function pollJob(
  jobId: string,
  options: {
    intervalMs?: number
    signal?: AbortSignal
    onUpdate?: (job: Job) => void
  } = {},
): Promise<Job> {
  const intervalMs = options.intervalMs ?? 1000

  while (true) {
    throwIfAborted(options.signal)
    const job = await getJob(jobId)
    options.onUpdate?.(job)
    if (isTerminalJob(job)) return job
    await delay(intervalMs, options.signal)
  }
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(createAbortError())
      return
    }

    const timer = window.setTimeout(() => {
      cleanup()
      resolve()
    }, ms)

    const onAbort = () => {
      window.clearTimeout(timer)
      cleanup()
      reject(createAbortError())
    }

    const cleanup = () => signal?.removeEventListener('abort', onAbort)

    if (signal) {
      signal.addEventListener('abort', onAbort, { once: true })
    }
  })
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw createAbortError()
}

function createAbortError(): DOMException {
  return new DOMException('The operation was aborted.', 'AbortError')
}
