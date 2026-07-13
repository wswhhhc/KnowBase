import type { QueryLogEntry, QueryLogsResponse } from '@/shared/api'

export interface DashboardStats {
  total: number
  answeredTotal: number
  qualityPassed: number
  qualityFailed: number
  webSearchCount: number
  avgElapsed: number
  qualityRate: number
  webSearchRate: number
  errorCount: number
  avgRetrieval: number
  last24h: number
}

export interface HourlyDashboardData {
  hour: number
  count: number
  tokens: number
  avgMs: number
}

export interface DashboardMetrics {
  stats: DashboardStats
  avgTtfb: number
  avgFirstToken: number
  totalTokens: number
  totalPromptTokens: number
  totalCompletionTokens: number
  effectiveCost: number
  totalTokenCost: string
  usesBackendTotalCost: boolean
  hourlyData: HourlyDashboardData[]
  maxHourlyCount: number
  maxHourlyTokens: number
  tokenLinePoints: string
}

export interface DashboardMetricsOptions {
  now: Date
  totalCostSummary: number | null
}

export interface NormalizedQueryLogs {
  logs: QueryLogEntry[]
  totalCostSummary: number | null
}

const EMPTY_STATS: DashboardStats = {
  total: 0,
  answeredTotal: 0,
  qualityPassed: 0,
  qualityFailed: 0,
  webSearchCount: 0,
  avgElapsed: 0,
  qualityRate: 0,
  webSearchRate: 0,
  errorCount: 0,
  avgRetrieval: 0,
  last24h: 0,
}

function hasError(log: QueryLogEntry): boolean {
  return Boolean(log.error?.trim())
}

export function normalizeQueryLogs(result: QueryLogsResponse | QueryLogEntry[]): NormalizedQueryLogs {
  if (Array.isArray(result)) {
    return { logs: result, totalCostSummary: null }
  }
  return {
    logs: result.logs ?? [],
    totalCostSummary: result.total_cost ?? null,
  }
}

export function buildDashboardMetrics(
  logs: QueryLogEntry[],
  { now, totalCostSummary }: DashboardMetricsOptions,
): DashboardMetrics {
  const answeredLogs = logs.filter((log) => !hasError(log))
  const qualityPassed = answeredLogs.filter((log) => log.quality_ok).length
  const qualityFailed = answeredLogs.filter((log) => !log.quality_ok).length
  const webSearchCount = answeredLogs.filter((log) => log.used_web_search).length
  const stats: DashboardStats = logs.length > 0
    ? {
        total: logs.length,
        answeredTotal: answeredLogs.length,
        qualityPassed,
        qualityFailed,
        webSearchCount,
        avgElapsed: Math.round(logs.reduce((sum, log) => sum + log.elapsed_ms, 0) / logs.length),
        qualityRate: answeredLogs.length > 0 ? qualityPassed / answeredLogs.length : 0,
        webSearchRate: answeredLogs.length > 0 ? webSearchCount / answeredLogs.length : 0,
        errorCount: logs.filter(hasError).length,
        avgRetrieval: Math.round(logs.reduce((sum, log) => sum + (log.retrieval_count || 0), 0) / logs.length),
        last24h: logs.filter((log) => now.getTime() - new Date(log.timestamp).getTime() < 86_400_000).length,
      }
    : EMPTY_STATS

  const ttfbValues = logs.map((log) => log.ttfb_ms || 0).filter(Boolean)
  const firstTokenValues = logs.map((log) => log.first_token_ms || 0).filter(Boolean)
  const avgTtfb = ttfbValues.length
    ? Math.round(ttfbValues.reduce((sum, value) => sum + value, 0) / ttfbValues.length)
    : 0
  const avgFirstToken = firstTokenValues.length
    ? Math.round(firstTokenValues.reduce((sum, value) => sum + value, 0) / firstTokenValues.length)
    : 0
  const totalTokens = logs.reduce((sum, log) => sum + (log.token_count || 0), 0)
  const totalPromptTokens = logs.reduce((sum, log) => sum + (log.prompt_tokens || 0), 0)
  const totalCompletionTokens = logs.reduce((sum, log) => sum + (log.completion_tokens || 0), 0)
  const hasPerLogCost = logs.some((log) => log.estimated_cost != null)
  const fallbackEstimatedCost = hasPerLogCost
    ? logs.reduce((sum, log) => sum + (log.estimated_cost || 0), 0)
    : (totalTokens / 1_000_000) * 0.5
  const effectiveCost = totalCostSummary ?? fallbackEstimatedCost
  const totalTokenCost = effectiveCost > 0
    ? (effectiveCost < 0.01 ? '<¥0.01' : `¥${effectiveCost.toFixed(2)}`)
    : 'N/A'
  const hourlyData = Array.from({ length: 24 }, (_, hour): HourlyDashboardData => {
    const hourLogs = logs.filter((log) => new Date(log.timestamp).getHours() === hour)
    return {
      hour,
      count: hourLogs.length,
      tokens: hourLogs.reduce((sum, log) => sum + (log.token_count || 0), 0),
      avgMs: hourLogs.length
        ? Math.round(hourLogs.reduce((sum, log) => sum + log.elapsed_ms, 0) / hourLogs.length)
        : 0,
    }
  })
  const maxHourlyCount = Math.max(...hourlyData.map((hour) => hour.count), 1)
  const maxHourlyTokens = Math.max(...hourlyData.map((hour) => hour.tokens), 1)
  const tokenLinePoints = hourlyData
    .map((hour, index) => {
      const x = (index / (hourlyData.length - 1)) * 100
      const y = 100 - (hour.tokens / maxHourlyTokens) * 100
      return `${x},${y}`
    })
    .join(' ')

  return {
    stats,
    avgTtfb,
    avgFirstToken,
    totalTokens,
    totalPromptTokens,
    totalCompletionTokens,
    effectiveCost,
    totalTokenCost,
    usesBackendTotalCost: totalCostSummary !== null,
    hourlyData,
    maxHourlyCount,
    maxHourlyTokens,
    tokenLinePoints,
  }
}
