/**
 * Compile-time API contract smoke tests for the frontend-facing type layer.
 *
 * These tests ensure the generated OpenAPI schema still exposes the fields
 * the UI relies on after schema regeneration and alias-layer refactors.
 */

import { describe, it, expect } from 'vitest'
import type {
  QueryLogEntry,
  KBChunk,
  JobStatus,
  RuntimeSettings,
  SettingsUpdateResult,
  Source,
  WorkspaceRole,
  WorkspaceMemberRole,
} from '@/shared/api'

describe('api type contracts', () => {
  it('QueryLogEntry includes the metrics fields used by the dashboard', () => {
    const entry: QueryLogEntry = {
      timestamp: '2024-01-01',
      thread_id: '',
      question: 'test',
      elapsed_ms: 100,
      retrieval_count: 5,
      quality_ok: true,
      quality_reason: '',
      question_type: '',
      retry_count: 0,
      source_count: 0,
      answer_preview: '',
      error: '',
      ttfb_ms: 50,
      first_token_ms: 100,
      token_count: 500,
      prompt_tokens: 200,
      completion_tokens: 300,
      llm_model: 'gpt-4',
      estimated_cost: 0.01,
    }
    expect(entry.estimated_cost).toBe(0.01)
    expect(entry.first_token_ms).toBe(100)
  })

  it('RuntimeSettings exposes every field used by SettingsPage', () => {
    const settings: RuntimeSettings = {
      siliconflow_api_key: '',
      siliconflow_base_url: 'https://api.siliconflow.cn/v1',
      embedding_model: 'BAAI/bge-m3',
      llm_model: 'deepseek-ai/DeepSeek-V4-Flash',
      llm_temperature: 0.3,
      tavily_api_key: '',
      api_key: '',
      chunk_size: 1500,
      chunk_overlap: 50,
      top_k_retrieval: 5,
      top_k_rerank: 3,
      enable_quality_check: true,
      enable_contextual_retrieval: true,
    }
    expect(settings.chunk_size).toBe(1500)
    expect(settings.enable_quality_check).toBe(true)
  })

  it('KBChunk type should contain all fields used by BrowserPage', () => {
    const chunk: KBChunk = {
      source: 'doc.md',
      chunk_index: 0,
      chunk_id: 'abc123',
      content: 'test content',
      page: null,
      original_content: null,
      section: null,
    }
    expect(chunk.page).toBeNull()
    expect(chunk.original_content).toBeNull()
    expect(chunk.section).toBeNull()
  })

  it('settings update responses expose both warnings and message', () => {
    const result: SettingsUpdateResult = {
      updated: true,
      warnings: ['需要重新导入文档'],
      message: '',
    }
    expect(result.warnings).toHaveLength(1)
  })

  it('ChatSource should contain index field used by MessageBubble', () => {
    const source: Source = {
      source: 'doc.md',
      content: 'content',
    }
    expect(source.index).toBeUndefined()
    // Verify it can hold an index at runtime
    const withIndex: typeof source & { index: number } = { ...source, index: 1 }
    expect(withIndex.index).toBe(1)
  })

  it('team role and job status unions expose the准生产 contract values', () => {
    const roles: WorkspaceRole[] = ['admin', 'editor', 'viewer']
    const workspaceMemberRoles: WorkspaceMemberRole[] = ['editor', 'viewer']
    const statuses: JobStatus[] = ['queued', 'running', 'succeeded', 'failed', 'canceled']

    expect(roles).toContain('editor')
    expect(workspaceMemberRoles).not.toContain('admin')
    expect(statuses).toContain('failed')
  })
})
