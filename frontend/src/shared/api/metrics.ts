import { req } from '@/shared/api/client'
import type { QueryLogsResponse } from '@/shared/api/types'

export const queryLogs = (days: number = 7, limit: number = 500) =>
  req<QueryLogsResponse>(`/metrics/logs?days=${days}&limit=${limit}`)
