import { Upload, Search, Globe, Zap, ArrowRight, LibraryBig } from 'lucide-react'
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
  eyebrow: string
  title: string
  description: string
  primaryLabel: string
  secondaryLabel?: string
  primaryIcon: typeof Upload
  suggestions: Array<{ icon: typeof Search; text: string }>
}

const STATE_COPY: Record<EmptyStateMode, StateCopy> = {
  onboarding: {
    eyebrow: '从资料开始',
    title: '工作区问答助手',
    description: '先把资料放进当前工作区，再回来提问或验证来源。',
    primaryLabel: '开始导入资料',
    primaryIcon: Upload,
    suggestions: [
      { icon: Search, text: '上传一份文档，然后问一个关于它的问题' },
      { icon: Globe, text: '导入一个公开网页的内容' },
      { icon: Zap, text: '开启联网搜索获取最新信息' },
    ],
  },
  'first-question': {
    eyebrow: '资料已就绪',
    title: '基于当前工作区开始提问',
    description: '资料已经准备好。先问一个结论性问题，必要时再去知识库核对原文。',
    primaryLabel: '基于当前工作区提问',
    secondaryLabel: '查看知识库',
    primaryIcon: ArrowRight,
    suggestions: [
      { icon: Search, text: '先问一个结论性问题，例如“这份资料的重点是什么？”' },
      { icon: LibraryBig, text: '如果想先确认内容，可以先到知识库浏览原文片段' },
      { icon: Zap, text: '需要更全面覆盖时，再切换到更高质量的检索策略' },
    ],
  },
  returning: {
    eyebrow: '继续推进',
    title: '继续当前工作区',
    description: '你已经有资料和历史对话，可以继续追问、复盘，或回到知识库验证引用。',
    primaryLabel: '继续提问',
    secondaryLabel: '查看知识库',
    primaryIcon: ArrowRight,
    suggestions: [
      { icon: Search, text: '继续追问上一轮回答中的结论或引用来源' },
      { icon: LibraryBig, text: '需要核实依据时，点击来源跳转到对应原文片段' },
      { icon: Zap, text: '问题范围变大时，再切换更深入的检索策略' },
    ],
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

  return (
    <div className="flex flex-col items-center justify-center min-h-[55vh] text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      >
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-border/70 bg-surface/70 px-3 py-1 text-2xs text-muted-foreground/80">
          <span className="font-medium text-foreground/70">{copy.eyebrow}</span>
          {mode !== 'onboarding' && (
            <span>
              {workspaceName} · {documentCount} 份资料{conversationCount > 0 ? ` · ${conversationCount} 个对话` : ''}
            </span>
          )}
        </div>

        <div className="mb-6">
          <span className="font-heading text-[120px] leading-none gradient-text select-none">K</span>
        </div>
        <h2 className="font-heading text-3xl text-foreground mb-2 tracking-tight">{copy.title}</h2>
        <p className="text-sm text-muted-foreground mb-10 max-w-md mx-auto">
          {copy.description}
        </p>
      </motion.div>

      <div className="grid gap-3 w-full max-w-md">
        {copy.suggestions.map((suggestion, index) => (
          <motion.div
            key={suggestion.text}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + index * 0.08, duration: 0.35 }}
            className="flex items-center gap-3 rounded-lg border border-border px-4 py-3 text-sm text-muted-foreground hover:border-primary/20 hover:bg-muted/30 transition-colors cursor-default text-left"
          >
            <suggestion.icon className="h-4 w-4 text-primary/60 flex-shrink-0" />
            <span>{suggestion.text}</span>
          </motion.div>
        ))}
      </div>

      {onPrimaryAction && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45, duration: 0.3 }}
          className="mt-6 flex flex-wrap items-center justify-center gap-3"
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
