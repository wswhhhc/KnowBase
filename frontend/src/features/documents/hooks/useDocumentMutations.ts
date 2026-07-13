import { toast } from 'sonner'
import * as api from '@/shared/api'

interface UseDocumentMutationsOptions {
  workspaceId?: string
  onRefresh: () => Promise<boolean>
}

export function useDocumentMutations({ workspaceId, onRefresh }: UseDocumentMutationsOptions) {
  const deleteSource = async (sourceName: string) => {
    try {
      await api.deleteSource(sourceName, workspaceId)
      if (await onRefresh()) toast.success('已删除引用文档')
    } catch (error) {
      toast.error('删除失败', { description: String(error) })
    }
  }

  const clearKnowledgeBase = async () => {
    try {
      const result = await api.clearKnowledgeBase(workspaceId)
      await api.waitForImportJob(result, () => {})
      if (await onRefresh()) toast.success('知识库已清空')
    } catch (error) {
      toast.error('清空失败', { description: String(error) })
    }
  }

  return { deleteSource, clearKnowledgeBase }
}
