import type {
  ChatStreamDonePayload,
  ChatStreamSourcesPayload,
  DebugInfo,
  DebugNodeInfo,
} from '@/shared/api/api-types'
import type { components } from '@/shared/api/api-types.openapi'

type Schemas = components['schemas']

export type Source = Schemas['ChatSource']
export type Conversation = Schemas['ConversationOut']
export type ApiMessage = Schemas['MessageOut']
export type KBStats = Schemas['KBStats']
export type QueryLogEntry = Schemas['QueryLogEntry']
export type QueryLogsResponse = Schemas['QueryLogsResponse']
export type DocSource = Schemas['SourceOut']
export type HotspotEntry = Schemas['HotspotEntry']
export type KBConfig = Schemas['KBConfig']
export type IngestResponse = Schemas['IngestResponse']
export type DemoImportResponse = Schemas['DemoImportResponse']
export type KBChunk = Schemas['KBChunk']
export type RuntimeSettings = Schemas['RuntimeSettingsOut']
export type RuntimeSettingsUpdate = Schemas['RuntimeSettingsUpdate']
export type SettingsUpdateResult = Schemas['SettingsUpdateResult']
export type Workspace = Schemas['WorkspaceOut']
export type Bookmark = Schemas['BookmarkOut']
export type DebugSearchHit = Schemas['DebugSearchResult']
export type DebugSearchResponse = Schemas['DebugSearchResponse']
export type PinStateResponse = Schemas['PinStateOut']
export type User = Schemas['UserOut']
export type AuthSession = Schemas['AuthSessionOut']
export type LoginRequest = Schemas['LoginRequest']
export type RefreshRequest = Schemas['RefreshRequest']
export type LogoutRequest = Schemas['LogoutRequest']

export type {
  ChatStreamDonePayload,
  ChatStreamSourcesPayload,
  DebugInfo,
  DebugNodeInfo,
}

export interface Message extends ApiMessage {
  role: 'user' | 'assistant'
}

export interface KBChunkResponse {
  items: KBChunk[]
  total: number
}

export interface ChatStreamCallbacks {
  onNode?: (label: string, nodes: string[]) => void
  onToken?: (text: string) => void
  onDebug?: (data: DebugInfo) => void
  onSources?: (data: ChatStreamSourcesPayload) => void
  onDone?: (data: ChatStreamDonePayload) => void
  onError?: (message: string) => void
}
