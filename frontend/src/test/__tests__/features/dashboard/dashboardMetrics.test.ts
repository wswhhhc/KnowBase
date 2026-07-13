import { describe, expect, it } from 'vitest'
import type { QueryLogEntry, QueryLogsResponse } from '@/shared/api'
import { buildDashboardMetrics, normalizeQueryLogs } from '@/features/dashboard/model/dashboardMetrics'

const now = new Date('2026-07-13T12:00:00Z')

const logs: QueryLogEntry[] = [
  {
    timestamp: '2026-07-13T11:00:00Z',
    thread_id: 'thread-1',
    question: '已回答且通过',
    elapsed_ms: 1200,
    retrieval_count: 2,
    quality_ok: true,
    quality_reason: 'PASS',
    used_web_search: true,
    used_rerank: false,
    question_type: 'knowledge_base',
    retry_count: 0,
    source_count: 1,
    answer_preview: 'answer',
    error: '',
    token_count: 1000,
    prompt_tokens: 600,
    completion_tokens: 400,
    llm_model: 'model-a',
    estimated_cost: 0.02,
    ttfb_ms: 100,
    first_token_ms: 150,
  },
  {
    timestamp: '2026-07-12T10:00:00Z',
    thread_id: 'thread-2',
    question: '已回答但未通过',
    elapsed_ms: 800,
    retrieval_count: 0,
    quality_ok: false,
    quality_reason: 'FAIL',
    used_web_search: false,
    used_rerank: false,
    question_type: 'knowledge_base',
    retry_count: 0,
    source_count: 0,
    answer_preview: 'answer',
    error: '',
    token_count: 2000,
    prompt_tokens: 1200,
    completion_tokens: 800,
    llm_model: 'model-a',
    estimated_cost: 0.03,
    ttfb_ms: null,
    first_token_ms: null,
  },
  {
    timestamp: '2026-07-11T09:00:00Z',
    thread_id: 'thread-3',
    question: '错误查询',
    elapsed_ms: 400,
    retrieval_count: 3,
    quality_ok: false,
    quality_reason: 'ERROR',
    used_web_search: false,
    used_rerank: false,
    question_type: 'knowledge_base',
    retry_count: 0,
    source_count: 0,
    answer_preview: '',
    error: 'upstream failed',
    token_count: 0,
    prompt_tokens: 0,
    completion_tokens: 0,
    llm_model: null,
    estimated_cost: null,
    ttfb_ms: null,
    first_token_ms: null,
  },
]

describe('dashboardMetrics', () => {
  it('normalizes legacy arrays and API response objects without losing the backend cost summary', () => {
    expect(normalizeQueryLogs(logs)).toEqual({ logs, totalCostSummary: null })

    const response: QueryLogsResponse = { logs, total_cost: 1.23 }
    expect(normalizeQueryLogs(response)).toEqual({ logs, totalCostSummary: 1.23 })
  })

  it('derives dashboard counts, rates, token values, and hourly data from the current log rules', () => {
    const metrics = buildDashboardMetrics(logs, { now, totalCostSummary: null })

    expect(metrics.stats).toMatchObject({
      total: 3,
      answeredTotal: 2,
      qualityPassed: 1,
      qualityFailed: 1,
      webSearchCount: 1,
      avgElapsed: 800,
      qualityRate: 0.5,
      webSearchRate: 0.5,
      errorCount: 1,
      avgRetrieval: 2,
      last24h: 1,
    })
    expect(metrics.totalTokens).toBe(3000)
    expect(metrics.totalPromptTokens).toBe(1800)
    expect(metrics.totalCompletionTokens).toBe(1200)
    expect(metrics.avgTtfb).toBe(100)
    expect(metrics.avgFirstToken).toBe(150)
    expect(metrics.effectiveCost).toBe(0.05)
    expect(metrics.totalTokenCost).toBe('¥0.05')
    const firstLogHour = new Date(logs[0].timestamp).getHours()
    expect(metrics.hourlyData[firstLogHour]).toMatchObject({ count: 1, tokens: 1000, avgMs: 1200 })
  })

  it('prioritizes the backend total cost summary over per-log and fallback estimates', () => {
    const metrics = buildDashboardMetrics(logs, { now, totalCostSummary: 2.5 })

    expect(metrics.effectiveCost).toBe(2.5)
    expect(metrics.totalTokenCost).toBe('¥2.50')
    expect(metrics.usesBackendTotalCost).toBe(true)
  })
})
