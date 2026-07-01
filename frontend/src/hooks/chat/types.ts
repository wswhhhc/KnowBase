import type { DebugInfo, PinStateResponse } from '@/lib/api'
import type { Source } from '@/lib/api'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  quality_reason?: string
  evidence_level?: string
  evidence_summary?: string
  outcome_category?: string
  streaming?: boolean
  debugData?: DebugInfo
  convId?: string
  assistantMsgId?: number
  originalQuestion?: string
  feedbackCategory?: string
}

export interface PinnedSource {
  chunk_id: string
  source: string
  content: string
  pinned: boolean
  excluded: boolean
  score: number
  index: number
}

export type PinState = PinStateResponse
