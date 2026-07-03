import { evidenceLabel } from '@/lib/utils'
import type { ChatMessage } from '@/hooks/useChat'
import type { WorkspaceSummary } from '@/types/workspace-summary'
import type { OutcomeGuidance } from './types'

export const FEEDBACK_OPTIONS = [
  { key: 'off_topic', label: '答非所问' },
  { key: 'insufficient_evidence', label: '证据不足' },
  { key: 'too_long', label: '回答太长' },
  { key: 'factual_error', label: '事实错误' },
  { key: 'other', label: '其他' },
] as const

export const STRATEGY_LABELS: Record<string, string> = {
  fast: '快速',
  balanced: '标准',
  high_quality: '严谨',
  deep: '深度',
}

export function formatElapsed(elapsedMs?: number, nodeElapsedMs?: number) {
  const total = elapsedMs ?? nodeElapsedMs
  if (!total || total <= 0) return '未知'
  if (total < 1000) return `${total}ms`
  return `${(total / 1000).toFixed(1)}s`
}

export function formatBooleanEcho(value?: boolean) {
  if (value == null) return '未知'
  return value ? '是' : '否'
}

export function getEvidenceTooltip(message: ChatMessage) {
  if (message.evidence_summary) {
    return message.evidence_summary
  }

  switch (message.evidence_level) {
    case 'strong':
      return '多个相关文档片段支持该回答，可信度较高'
    case 'moderate':
      return '少量相关文档片段支持该回答'
    case 'weak':
      return '仅少数文档片段触及问题，证据不够充分'
    default:
      return '没有找到直接相关的文档证据'
  }
}

export function getEvidenceBadgeClass(level?: string) {
  switch (level) {
    case 'strong':
      return 'bg-emerald-500/20 text-emerald-300'
    case 'moderate':
      return 'bg-yellow-500/20 text-yellow-300'
    case 'weak':
      return 'bg-orange-500/20 text-orange-300'
    default:
      return 'bg-red-500/20 text-red-300'
  }
}

export function getEvidenceLabel(level?: string) {
  return level ? evidenceLabel(level) : '未知'
}

export function getOutcomeGuidance(
  message: ChatMessage,
  workspaceSummary: WorkspaceSummary | undefined,
  questionContext: string,
): OutcomeGuidance | null {
  const documentCount = workspaceSummary?.documentCount ?? 0
  const workspaceName = workspaceSummary?.workspaceName || '当前工作区'

  switch (message.outcome_category) {
    case 'no_docs':
      if (documentCount <= 0) {
        return {
          badge: '当前工作区暂无资料',
          badgeClass: 'bg-red-500/10 text-red-400',
          title: `${workspaceName} 里还没有可用资料`,
          description: '先导入一份文档或网页，再回到聊天页提问；导入后也可以先去知识库核对原文。',
          primaryLabel: '去导入资料',
          secondaryLabel: questionContext ? '帮我改写问题' : undefined,
          followUpPrompt: questionContext ? `请帮我把这个问题改写成更具体、便于检索的版本：${questionContext}` : undefined,
        }
      }
      return {
        badge: '当前工作区未命中',
        badgeClass: 'bg-red-500/10 text-red-400',
        title: `${workspaceName} 里没有找到直接相关的内容`,
        description: '先去知识库核对当前来源范围，再决定是补充资料，还是换一种更具体的问法。',
        primaryLabel: '去验证来源',
        secondaryLabel: questionContext ? '换个问法' : undefined,
        followUpPrompt: questionContext ? `请基于当前工作区，帮我把这个问题改写得更具体：${questionContext}` : undefined,
      }
    case 'web_empty':
      return {
        badge: '当前无结果',
        badgeClass: 'bg-red-500/10 text-red-400',
        title: '当前工作区和联网结果都不足以回答',
        description: '建议先核对当前工作区里的来源范围，再补充资料或换一个更明确的问题。',
        primaryLabel: '去验证来源',
        secondaryLabel: questionContext ? '换个问法' : undefined,
        followUpPrompt: questionContext ? `请帮我把这个问题改写得更明确，并指出缺少哪些关键信息：${questionContext}` : undefined,
      }
    case 'weak_evidence':
      return {
        badge: '证据偏弱',
        badgeClass: 'bg-orange-500/10 text-orange-400',
        title: '当前证据不足以支撑可靠回答',
        description: message.evidence_summary
          ? `${message.evidence_summary}。先去核对来源，再决定是否补充资料。`
          : '先去核对当前工作区里的来源片段，再决定是否补充更相关的资料。',
        primaryLabel: '去验证来源',
        secondaryLabel: questionContext ? '帮我缩小问题范围' : undefined,
        followUpPrompt: questionContext ? `请帮我把这个问题缩小范围，并改写成更容易命中文档的问题：${questionContext}` : undefined,
      }
    case 'vague_question':
      return {
        badge: '问题不够具体',
        badgeClass: 'bg-orange-500/10 text-orange-400',
        title: '问题还不够具体',
        description: '补充对象、时间、范围或你想验证的结论后，当前工作区更容易给出可核对的回答。',
        secondaryLabel: questionContext ? '帮我改写问题' : undefined,
        followUpPrompt: questionContext ? `请把这个问题改写得更具体，并保留原意：${questionContext}` : undefined,
      }
    default:
      return null
  }
}
