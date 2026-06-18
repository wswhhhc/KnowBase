import { Search, Globe, Zap } from 'lucide-react'
import { motion } from 'framer-motion'

export default function EmptyState() {
  const suggestions = [
    { icon: Search, text: '上传一份文档，然后问一个关于它的问题' },
    { icon: Globe, text: '导入一个公开网页的内容' },
    { icon: Zap, text: '开启联网搜索获取最新信息' },
  ]

  return (
    <div className="flex flex-col items-center justify-center min-h-[55vh] text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      >
        <div className="mb-6">
          <span className="font-heading text-[140px] leading-none gradient-text select-none">K</span>
        </div>
        <h2 className="font-heading text-3xl text-foreground mb-2 tracking-tight">知识库问答助手</h2>
        <p className="text-sm text-muted-foreground mb-10 max-w-md mx-auto">
          上传文档或导入网页，让 AI 基于你的知识库回答问题
        </p>
      </motion.div>

      <div className="grid gap-3 w-full max-w-sm">
        {suggestions.map((s, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 + i * 0.12, duration: 0.4 }}
            className="flex items-center gap-3 rounded-lg border border-border px-4 py-3 text-sm text-muted-foreground hover:border-primary/20 hover:bg-muted/30 transition-colors cursor-default"
          >
            <s.icon className="h-4 w-4 text-primary/60 flex-shrink-0" />
            <span>{s.text}</span>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
