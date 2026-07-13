import { Button } from '@/components/ui'
import { PHASE_COPY, type useDocumentImport } from '@/features/documents/hooks/useDocumentImport'

type DocumentImportController = ReturnType<typeof useDocumentImport>

interface DocumentImportFeedbackProps {
  controller: DocumentImportController
  onSendQuestion?: (question: string) => void
  onOpenKnowledgeBase?: () => void
  onContinueImport: () => void
}

export function DocumentImportProgressCopy({ uploadPhase }: { uploadPhase: string }) {
  const copy = PHASE_COPY[uploadPhase] ?? { title: '正在处理资料…', detail: '请稍候，系统正在准备可检索内容。' }
  return (
    <>
      <p className="font-medium text-foreground">{copy.title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{copy.detail}</p>
    </>
  )
}

export default function DocumentImportFeedback({
  controller,
  onSendQuestion,
  onOpenKnowledgeBase,
  onContinueImport,
}: DocumentImportFeedbackProps) {
  return (
    <>
      {controller.uploading && (
        <div className="mt-1.5 space-y-1">
          <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${controller.uploadPercent}%` }} />
          </div>
          <p className="text-right text-2xs text-muted-foreground/60">{controller.uploadPercent}%</p>
        </div>
      )}

      {controller.postImportGuide && (
        <div className="mt-3 rounded-xl border border-primary/15 bg-primary/5 p-3">
          <p className="text-sm font-medium text-foreground">{controller.postImportGuide.title}</p>
          <p className="mt-1 text-xs text-muted-foreground">{controller.postImportGuide.description}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {onOpenKnowledgeBase && <Button size="sm" variant="outline" onClick={onOpenKnowledgeBase}>去知识库核对来源</Button>}
            <Button size="sm" variant="outline" onClick={() => {
              controller.setPostImportGuide(null)
              onContinueImport()
            }}>
              继续导入
            </Button>
          </div>
          {controller.postImportGuide.suggestedQuestions.length > 0 && (
            <div className="mt-3 rounded-lg border border-primary/10 bg-background/70 p-2.5">
              <p className="mb-2 text-2xs font-medium tracking-wide text-primary/80">推荐直接追问</p>
              <div className="space-y-1">
                {controller.postImportGuide.suggestedQuestions.map((question, index) => (
                  <button
                    key={index}
                    onClick={() => {
                      onSendQuestion?.(question)
                      controller.setPostImportGuide(null)
                    }}
                    className="block w-full rounded px-2 py-1.5 text-left text-xs text-foreground/75 transition-colors hover:bg-primary/10 hover:text-foreground"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {controller.versionPrompt && (
        <div className="mt-2 rounded-lg border border-primary/15 bg-primary/5 p-3">
          <p className="mb-2 text-2xs font-medium tracking-wide text-primary/80">该来源已存在，请选择操作方式</p>
          <div className="space-y-1">
            <button onClick={() => void controller.selectVersionMode('replace')} className="block w-full rounded px-2 py-1.5 text-left text-xs text-foreground/80 transition-colors hover:bg-primary/10">
              替换为新版本（删除旧内容后重新导入）
            </button>
            <button onClick={() => void controller.selectVersionMode('append')} className="block w-full rounded px-2 py-1.5 text-left text-xs text-foreground/80 transition-colors hover:bg-primary/10">
              保留两者（新旧版本共存）
            </button>
            <button onClick={() => {
              controller.skipVersionPrompt()
            }} className="block w-full rounded px-2 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:bg-muted/50">
              取消，不重复导入
            </button>
          </div>
        </div>
      )}
    </>
  )
}
