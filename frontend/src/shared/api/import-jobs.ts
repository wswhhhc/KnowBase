import { pollJob } from '@/shared/api/jobs'
import type { IngestResponse, Job, JobCreateResponse } from '@/shared/api/types'

export type ImportJobProgressHandler = (phase: string, percent: number) => void

export function isJobCreateResponse(result: IngestResponse | JobCreateResponse): result is JobCreateResponse {
  return 'job_id' in result
}

export async function waitForImportJob(
  result: IngestResponse | JobCreateResponse,
  onProgress: ImportJobProgressHandler,
): Promise<IngestResponse | null> {
  if (!isJobCreateResponse(result)) return result

  const applyJobProgress = (job: Job) => {
    onProgress(job.progress?.phase || job.status, job.progress?.percent ?? 0)
  }

  applyJobProgress(result.job)
  const finished = await pollJob(result.job_id, {
    intervalMs: 1000,
    onUpdate: applyJobProgress,
  })

  if (finished.status === 'failed') {
    throw new Error(finished.error || '后台导入任务失败')
  }
  if (finished.status === 'canceled') {
    throw new Error('后台导入任务已取消')
  }

  onProgress('done', 100)
  return null
}
