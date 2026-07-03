import type { components } from './api-types.openapi'

type ChatSource = components['schemas']['ChatSource']

// Manually maintained SSE-only payload types. These models are streamed over
// chat events and are not described by the FastAPI OpenAPI responses.
// Keep them aligned with backend/src/api/models.py.

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
  context_sources: ChatSource[]
  token_count: number | null
  prompt_tokens: number | null
  completion_tokens: number | null
}

export interface ChatStreamSourcesPayload {
  sources: ChatSource[]
  quality_reason: string
  evidence_level: string
  evidence_summary: string
  outcome_category: string
}

export interface ChatStreamDonePayload extends ChatStreamSourcesPayload {
  thread_id: string
  conv_id: string
  assistant_msg_id: number
  answer: string
  elapsed_ms: number
}
