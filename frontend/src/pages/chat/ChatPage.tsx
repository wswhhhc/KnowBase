import { Button } from '@/components/ui'
import { BarChart3, BookOpen, PanelRightOpen, Sparkles } from 'lucide-react'
import type { ViewType } from '@/app/navigation'
import type { Source } from '@/shared/api'
import type { PinnedSource } from '@/hooks/useChat'
import { useChat } from '@/hooks/useChat'
import { OPEN_DOCUMENTS_PANEL_EVENT } from '@/lib/ui-events'
import type { WorkspaceSummary } from '@/types/workspace-summary'
import ChatComposer from '@/components/chat/ChatComposer'
import ChatMessageList from '@/components/chat/ChatMessageList'
import SearchPreferencesPanel from '@/components/chat/SearchPreferencesPanel'
import { useChatComposer } from '@/features/chat/hooks/useChatComposer'
import { useSearchPreferences } from '@/features/chat/hooks/useSearchPreferences'

interface ChatPageProps {
  chat: ReturnType<typeof useChat>
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (view: ViewType) => void
  isLoadingMessages?: boolean
  onCitationClick?: (source: Source) => void
  onSendQuestion?: (question: string) => void
  workspaceSummary: WorkspaceSummary
  isMobile?: boolean
  canManageApp?: boolean
}

export default function ChatPage({
  chat,
  onOpenSidebar,
  sidebarOpen,
  onNavigate,
  isLoadingMessages,
  onCitationClick,
  onSendQuestion,
  workspaceSummary,
  isMobile = false,
  canManageApp = true,
}: ChatPageProps) {
  const { webSearch, setWebSearch, searchStrategy, setSearchStrategy } = useSearchPreferences()
  const composer = useChatComposer({
    isStreaming: chat.isStreaming,
    onSend: (question) => chat.sendMessage(question, webSearch, searchStrategy),
  })
  const activeTitle = chat.messages[0]?.role === 'user'
    ? chat.messages[0].content.slice(0, 28)
    : 'KnowBase'

  const focusComposer = () => {
    requestAnimationFrame(() => composer.inputRef.current?.focus())
  }

  const openDocumentPanel = () => {
    onOpenSidebar()
    window.dispatchEvent(new Event(OPEN_DOCUMENTS_PANEL_EVENT))
  }

  const handlePinToggle = (chunkId: string, action: 'pin' | 'unpin' | 'exclude' | 'unexclude') => {
    chat.setPinnedSources((previous: PinnedSource[]) =>
      previous.map((source) =>
        source.chunk_id === chunkId
          ? { ...source, pinned: action === 'pin', excluded: action === 'exclude' }
          : source,
      ),
    )
  }

  const composerPlaceholder = workspaceSummary.documentCount <= 0
    ? '先导入资料，或直接输入你想验证的问题…'
    : `基于“${workspaceSummary.workspaceName}”提问，例如：这份资料的重点是什么？`

  return (
    <>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background/80 px-5 py-3 backdrop-blur-sm">
        <div className="flex min-w-0 items-center gap-3">
          {!sidebarOpen && (
            <Button variant="ghost" size="sm" onClick={onOpenSidebar}>
              <PanelRightOpen className="h-4 w-4" />
            </Button>
          )}
          <div className="min-w-0">
            <h1 className={`truncate font-heading text-lg text-foreground tracking-tight ${isMobile ? 'max-w-[11rem]' : 'max-w-[18rem]'}`}>{activeTitle}</h1>
            <p className="truncate text-2xs text-muted-foreground/60">
              当前工作区：{workspaceSummary.workspaceName} · {workspaceSummary.documentCount} 份资料
            </p>
          </div>
        </div>

        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
          <div className="hidden xl:flex items-center gap-0.5 rounded-md border border-border p-0.5">
            <button onClick={() => onNavigate('chat')}
              className="flex items-center gap-1 rounded-sm bg-primary/15 px-2.5 py-1 text-xs font-medium text-primary">
              <Sparkles className="h-3 w-3" />聊天
            </button>
            <button onClick={() => onNavigate('browser')}
              className="flex items-center gap-1 rounded-sm px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
              <BookOpen className="h-3 w-3" />知识库
            </button>
            {canManageApp && (
              <button onClick={() => onNavigate('dashboard')}
                className="flex items-center gap-1 rounded-sm px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
                <BarChart3 className="h-3 w-3" />指标
              </button>
            )}
          </div>

          <div className="hidden h-4 w-px bg-border xl:block" />
          <SearchPreferencesPanel
            variant={isMobile ? 'mobile' : 'desktop'}
            webSearch={webSearch}
            onWebSearchChange={setWebSearch}
            searchStrategy={searchStrategy}
            onSearchStrategyChange={setSearchStrategy}
          />
        </div>
      </header>

      <ChatMessageList
        messages={chat.messages}
        isStreaming={chat.isStreaming}
        streamingNodes={chat.streamingNodes}
        isLoadingMessages={isLoadingMessages}
        threadId={chat.threadId}
        workspaceId={chat.workspaceId}
        workspaceSummary={workspaceSummary}
        pinnedSources={chat.pinnedSources}
        onCitationClick={onCitationClick}
        onSendQuestion={onSendQuestion}
        onOpenDocuments={openDocumentPanel}
        onFocusComposer={focusComposer}
        onNavigateBrowser={() => onNavigate('browser')}
        onPinToggle={handlePinToggle}
      />

      <ChatComposer
        input={composer.input}
        inputRef={composer.inputRef}
        placeholder={composerPlaceholder}
        isStreaming={chat.isStreaming}
        onInputChange={composer.setInput}
        onKeyDown={composer.handleKeyDown}
        onSend={composer.send}
        onStopStreaming={chat.stopStreaming}
      />
    </>
  )
}
