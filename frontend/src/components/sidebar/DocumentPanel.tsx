import { useState } from 'react'
import { ConfirmDialog, Separator } from '@/components/ui'
import type { DocSource } from '@/shared/api'
import DocumentImportSection from '@/components/sidebar/document-panel/DocumentImportSection'
import DocumentSourceList from '@/components/sidebar/document-panel/DocumentSourceList'
import { useDocumentImport } from '@/features/documents/hooks/useDocumentImport'
import { useDocumentMutations } from '@/features/documents/hooks/useDocumentMutations'

interface DocumentPanelProps {
  sources: DocSource[]
  onRefresh: () => Promise<boolean>
  workspaceId?: string
  workspaceName?: string
  onSendQuestion?: (question: string) => void
  onOpenKnowledgeBase?: () => void
  canManageKnowledgeBase?: boolean
}

export default function DocumentPanel({
  sources,
  onRefresh,
  workspaceId,
  workspaceName = '默认工作区',
  onSendQuestion,
  onOpenKnowledgeBase,
  canManageKnowledgeBase = true,
}: DocumentPanelProps) {
  const [deleteSourceTarget, setDeleteSourceTarget] = useState<string | null>(null)
  const [clearOpen, setClearOpen] = useState(false)
  const importController = useDocumentImport({ workspaceId, workspaceName, onRefresh })
  const mutations = useDocumentMutations({ workspaceId, onRefresh })

  return (
    <div className="space-y-4">
      {canManageKnowledgeBase ? (
        <DocumentImportSection
          controller={importController}
          workspaceName={workspaceName}
          onSendQuestion={onSendQuestion}
          onOpenKnowledgeBase={onOpenKnowledgeBase}
        />
      ) : (
        <div className="rounded-xl border border-border/70 bg-muted/20 p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground/80">当前账号为只读权限</p>
          <p className="mt-1">可以浏览引用文档并发起问答，导入、删除和清空知识库需要编辑者或管理员权限。</p>
        </div>
      )}

      {canManageKnowledgeBase && <Separator />}
      <DocumentSourceList
        sources={sources}
        canManageKnowledgeBase={canManageKnowledgeBase}
        onClear={() => setClearOpen(true)}
        onDelete={setDeleteSourceTarget}
      />

      <ConfirmDialog
        open={Boolean(deleteSourceTarget)}
        onOpenChange={(open) => { if (!open) setDeleteSourceTarget(null) }}
        title="删除引用文档"
        description={`确定要删除"${deleteSourceTarget ?? ''}"吗？关联的段落将被移除。`}
        onConfirm={async () => {
          if (deleteSourceTarget) await mutations.deleteSource(deleteSourceTarget)
        }}
      />
      <ConfirmDialog
        open={clearOpen}
        onOpenChange={setClearOpen}
        title="清空知识库"
        description="确定要清空整个知识库中的所有文档和段落吗？此操作不可撤销。"
        onConfirm={mutations.clearKnowledgeBase}
      />
    </div>
  )
}
