import { Upload, Search, Globe, Zap, ArrowRight, LibraryBig, MessageSquareText, History } from 'lucide-react'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui'

export type EmptyStateMode = 'onboarding' | 'first-question' | 'returning'

interface EmptyStateProps {
  mode?: EmptyStateMode
  workspaceName?: string
  documentCount?: number
  conversationCount?: number
  onPrimaryAction?: () => void
  onSecondaryAction?: () => void
}

interface StateCopy {
  status: string
  title: string
  description: string
  primaryLabel: string
  secondaryLabel?: string
  primaryIcon: typeof Upload
  suggestions: Array<{ icon: typeof Search; title: string; text: string }>
  verificationHint: string
}

const STATE_COPY: Record<EmptyStateMode, StateCopy> = {
  onboarding: {
    status: '未导入资料',
    title: '当前工作区还没有资料',
    description: '先导入文档、公开网页或示例资料，再开始问答与来源核对。',
    primaryLabel: '打开资料面板',
    primaryIcon: Upload,
    suggestions: [
      { icon: Upload, title: '先导入资料', text: '支持拖拽上传文件、导入公开网页，也可以一键导入示例资料。' },
      { icon: MessageSquareText, title: '再问第一个问题', text: '先问结论性问题，例如“这份资料的重点是什么？”' },
      { icon: LibraryBig, title: '需要核对时再验证', text: '回答给出引用后，再去知识库查看原文片段和真实来源。' },
    ],
    verificationHint: '导入完成后，如果你想先确认内容，再去知识库核对来源。',
  },
  'first-question': {
    status: '已导入资料',
    title: '资料已导入，还没开始提问',
    description: '当前工作区已经有资料，建议先问结论，再按引用回到知识库核对来源。',
    primaryLabel: '问第一个问题',
    secondaryLabel: '去知识库核对来源',
    primaryIcon: ArrowRight,
    suggestions: [
      { icon: MessageSquareText, title: '先问结论', text: '例如“这组资料主要在讲什么？”或“先给我一版摘要”。' },
      { icon: LibraryBig, title: '需要先验证来源', text: '如果你想先确认内容，可以先去知识库浏览当前来源与原文片段。' },
      { icon: Zap, title: '再按复杂度提问', text: '问题范围变大后，再切换到更严谨或更深度的检索策略。' },
    ],
    verificationHint: '需要先去知识库验证来源时，先核对原文，再回来继续提问。',
  },
  returning: {
    status: '已有历史对话',
    title: '已有历史对话，可继续推进',
    description: '资料和上下文都在，可以继续追问、补充结论，或回到知识库核对新的引用。',
    primaryLabel: '继续当前问题',
    secondaryLabel: '去知识库核对来源',
    primaryIcon: ArrowRight,
    suggestions: [
      { icon: History, title: '延续上一轮问题', text: '继续追问上一轮结论、限定范围，或要求补充对比与依据。' },
      { icon: LibraryBig, title: '回知识库核对引用', text: '当回答里出现关键结论或引用时，可以回知识库逐段验证。' },
      { icon: Search, title: '重新梳理问题', text: '如果方向变了，先重述你的目标，再让系统重新检索。' },
    ],
    verificationHint: '需要先去知识库验证来源时，优先核对当前引用，再继续推进对话。',
  },
}

export default function EmptyState({
  mode = 'onboarding',
  workspaceName = '默认工作区',
  documentCount = 0,
  conversationCount = 0,
  onPrimaryAction,
  onSecondaryAction,
}: EmptyStateProps) {
  const copy = STATE_COPY[mode]
  const PrimaryIcon = copy.primaryIcon
  const summaryItems = [
    { label: '当前工作区', value: workspaceName },
    { label: '已导入资料', value: `${documentCount} 份` },
    { label: '历史对话', value: `${conversationCount} 个` },
  ]

  return (
    <div className="mx-auto flex min-h-[55vh] w-full max-w-4xl flex-col justify-center text-left">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      >
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border/70 bg-surface/70 px-3 py-1 text-2xs text-muted-foreground/80">
          <span className="font-medium text-foreground/80">{copy.status}</span>
          <span>{workspaceName}</span>
        </div>

        <div className="mb-6 grid gap-3 md:grid-cols-[1.15fr_0.85fr] md:items-start">
          <div>
            <div className="mb-4">
              <span className="font-heading text-[96px] leading-none gradient-text select-none">K</span>
            </div>
            <h2 className="mb-2 font-heading text-3xl tracking-tight text-foreground">{copy.title}</h2>
            <p className="max-w-xl text-sm text-muted-foreground">
              {copy.description}
            </p>
          </div>

          <div className="grid gap-2 sm:grid-cols-3 md:grid-cols-1">
            {summaryItems.map((item) => (
              <div key={item.label} className="rounded-2xl border border-border/70 bg-surface/60 px-4 py-3">
                <p className="text-2xs uppercase tracking-[0.18em] text-muted-foreground/60">{item.label}</p>
                <p className="mt-1 text-sm font-medium text-foreground">{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      <div className="grid w-full gap-3 md:grid-cols-3">
        {copy.suggestions.map((suggestion, index) => (
          <motion.div
            key={suggestion.title}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + index * 0.08, duration: 0.35 }}
            className="rounded-2xl border border-border/80 bg-background/70 px-4 py-4 transition-colors hover:border-primary/20 hover:bg-muted/20"
          >
            <div className="mb-3 inline-flex rounded-full bg-primary/10 p-2 text-primary/80">
              <suggestion.icon className="h-4 w-4 flex-shrink-0" />
            </div>
            <p className="text-sm font-medium text-foreground">{suggestion.title}</p>
            <p className="mt-1 text-sm text-muted-foreground">{suggestion.text}</p>
          </motion.div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.3 }}
        className="mt-4 rounded-2xl border border-border/70 bg-surface/55 px-4 py-3 text-sm text-muted-foreground"
      >
        <span className="font-medium text-foreground/80">来源核对提示：</span> {copy.verificationHint}
      </motion.div>

      {onPrimaryAction && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45, duration: 0.3 }}
          className="mt-6 flex flex-wrap items-center gap-3"
        >
          <Button onClick={onPrimaryAction} size="lg" className="gap-2" aria-label={copy.primaryLabel}>
            <PrimaryIcon className="h-4 w-4" />
            {copy.primaryLabel}
          </Button>
          {copy.secondaryLabel && onSecondaryAction && (
            <Button onClick={onSecondaryAction} size="lg" variant="outline" className="gap-2">
              <LibraryBig className="h-4 w-4" />
              {copy.secondaryLabel}
            </Button>
          )}
        </motion.div>
      )}
    </div>
  )
}
