/**
 * Compile-time type drift checks for manually-maintained frontend API types.
 *
 * These tests verify that the manual extensions in api.ts (which augment
 * the auto-generated OpenAPI types) remain compatible with the actual
 * backend response shapes, catching drift between generator output and
 * hand-written type definitions.
 */

import { describe, it, expect } from 'vitest'
import type { QueryLogEntry as ManualQueryLogEntry } from '@/lib/api'
import type { QueryLogEntry as GeneratedQueryLogEntry } from '@/lib/api-types.generated'

// The fields added manually in api.ts on top of the generated type
interface ExpectedQueryLogEntryExtensions {
  ttfb_ms?: number
  first_token_ms?: number
  token_count?: number | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  llm_model?: string | null
  estimated_cost?: number | null
}

type Assert<T extends true> = T
type IsEqual<A, B> =
  (<T>() => T extends A ? 1 : 2) extends (<T>() => T extends B ? 1 : 2)
    ? ((<T>() => T extends B ? 1 : 2) extends (<T>() => T extends A ? 1 : 2) ? true : false)
    : false

type ManualOnlyQueryLogEntryKeys = Exclude<keyof ManualQueryLogEntry, keyof GeneratedQueryLogEntry>
type GeneratedOnlyQueryLogEntryKeys = Exclude<keyof GeneratedQueryLogEntry, keyof ManualQueryLogEntry>

type _generatedQueryLogEntryStaysAssignableToManual =
  Assert<GeneratedQueryLogEntry extends ManualQueryLogEntry ? true : false>
type _manualQueryLogEntryAddsOnlyExpectedKeys =
  Assert<IsEqual<ManualOnlyQueryLogEntryKeys, keyof ExpectedQueryLogEntryExtensions>>
type _manualQueryLogEntryKeepsAllGeneratedKeys =
  Assert<IsEqual<GeneratedOnlyQueryLogEntryKeys, never>>
type _manualQueryLogEntryExtensionShapeMatches =
  Assert<IsEqual<Pick<ManualQueryLogEntry, ManualOnlyQueryLogEntryKeys>, ExpectedQueryLogEntryExtensions>>

describe('api type drift', () => {
  it('QueryLogEntry manual extension should exactly match the generated type gap', () => {
    // The compile-time assertions above are the real guardrail. This runtime
    // check keeps the test visible in Vitest output and documents the intended shape.
    const entry: GeneratedQueryLogEntry = {
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
    }
    expect(entry.timestamp).toBe('2024-01-01')
    expect(entry.question).toBe('test')

    const manualOnlyFields: Pick<ManualQueryLogEntry, ManualOnlyQueryLogEntryKeys> = {
      ttfb_ms: 50,
      first_token_ms: 100,
      token_count: 500,
      prompt_tokens: 200,
      completion_tokens: 300,
      llm_model: 'gpt-4',
      estimated_cost: 0.01,
    }
    expect(manualOnlyFields.ttfb_ms).toBe(50)
  })

  it('KBChunk type should contain all fields used by BrowserPage', () => {
    // This is a compile-time check: if KBChunk is missing any field
    // used in BrowserPage, TypeScript will fail the build.
    const chunk: import('@/lib/api-types.generated').components['schemas']['KBChunk'] = {
      source: 'doc.md',
      chunk_index: 0,
      chunk_id: 'abc123',
      content: 'test content',
    }
    // Fields that may be null
    expect(chunk.page).toBeUndefined()
    expect(chunk.original_content).toBeUndefined()
    expect(chunk.section).toBeUndefined()
  })

  it('ChatSource should contain index field used by MessageBubble', () => {
    const source: import('@/lib/api-types.generated').components['schemas']['ChatSource'] = {
      source: 'doc.md',
      content: 'content',
    }
    expect(source.index).toBeUndefined()
    // Verify it can hold an index at runtime
    const withIndex: typeof source & { index: number } = { ...source, index: 1 }
    expect(withIndex.index).toBe(1)
  })
})
