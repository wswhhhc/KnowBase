// Frontend-facing API type layer.
// Depends on the generated OpenAPI types in api-types.openapi.ts and adds:
// - short aliases for commonly used response schemas
// - hand-maintained SSE-only payload types that OpenAPI cannot infer
import type { components } from './api-types.openapi'

type Schemas = components['schemas']

export type Source = Schemas['ChatSource']
export type Conversation = Schemas['ConversationOut']
export type ApiMessage = Schemas['MessageOut']
export type KBStats = Schemas['KBStats']
export type QueryLogEntry = Schemas['QueryLogEntry']
export type DocSource = Schemas['SourceOut']
export type HotspotEntry = Schemas['HotspotEntry']
export type KBConfig = Schemas['KBConfig']
export type IngestResponse = Schemas['IngestResponse']
export type RuntimeSettings = Schemas['RuntimeSettingsOut']
export type RuntimeSettingsUpdate = Schemas['RuntimeSettingsUpdate']
export type SettingsUpdateResult = Schemas['SettingsUpdateResult']

// Manually maintained — these Pydantic models are used inside SSE events
// (not FastAPI JSON responses), so openapi-typescript cannot infer them.
// Keep in sync with backend/src/api/models.py.
//
// When you add/change fields in the Pydantic model, update these interfaces
// to match. They are checked by backend/tests/test_sse_type_sync.py.

export interface KBChunk {
  source: string
  chunk_index: number
  chunk_id: string
  page: number | null
  content: string
  original_content: string | null
  section: string | null
}

export interface DebugNodeInfo {
  name: string
  label: string
  elapsed_ms: number
  summary: string
}

export interface DebugInfo {
  nodes: DebugNodeInfo[]
  rewritten_question: string
  retrieval_k: number
  candidates_before: number
  candidates_after: number
  after_rerank: number
  used_rerank: boolean
  used_rewrite: boolean
  quality_passed: boolean
  quality_reason: string
  retry_count: number
  used_web_search: boolean
  web_results_count: number
  context_sources: Source[]
  token_count: number | null
  prompt_tokens: number | null
  completion_tokens: number | null
}
