// Auto-generated type aliases — maps Pydantic model names to TS interfaces.
// Generated from backend/openapi.json by openapi-typescript.
// Run `cd frontend && npm run gen-api-types` to regenerate.
// Depends on backend/openapi.json (export from a running backend).
import type { components } from './api-types'

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

// Manually maintained — these Pydantic models are used inside SSE events
// (not FastAPI JSON responses), so openapi-typescript cannot infer them.
// Keep in sync with backend/src/api/models.py.
//
// When you add/change fields in the Pydantic model, update these interfaces
// to match.  There is no automated check for this.

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
}
