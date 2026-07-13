import { useEffect, useState } from 'react'
import * as api from '@/shared/api'
import type { QueryLogEntry, QueryLogsResponse } from '@/shared/api'
import { normalizeQueryLogs } from '@/features/dashboard/model/dashboardMetrics'

export function useDashboardData() {
  const [logs, setLogs] = useState<QueryLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(7)
  const [totalCostSummary, setTotalCostSummary] = useState<number | null>(null)

  useEffect(() => {
    setLoading(true)
    api.queryLogs(days, 1000)
      .then((result: QueryLogsResponse | QueryLogEntry[]) => {
        const normalized = normalizeQueryLogs(result)
        setLogs(normalized.logs)
        setTotalCostSummary(normalized.totalCostSummary)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [days])

  return { logs, loading, days, setDays, totalCostSummary }
}
