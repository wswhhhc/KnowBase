import { req } from '@/shared/api/client'
import type { Job } from '@/shared/api/types'

export const listJobs = () => req<Job[]>('/jobs')

export const getJob = (jobId: string) =>
  req<Job>(`/jobs/${encodeURIComponent(jobId)}`)

export const cancelJob = (jobId: string) =>
  req<Job>(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' })
