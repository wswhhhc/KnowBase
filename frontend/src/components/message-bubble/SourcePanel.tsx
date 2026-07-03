import { AnimatePresence, motion } from 'framer-motion'
import type { Source } from '@/lib/api'
import SourceCard from './SourceCard'
import { useChatContext } from './ChatContext'

interface SourcePanelProps {
  open: boolean
  sources?: Source[]
}

export default function SourcePanel({
  open,
  sources,
}: SourcePanelProps) {
  const { pinnedSources } = useChatContext()
  return (
    <AnimatePresence>
      {open && sources && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="mt-2 space-y-2 overflow-hidden"
        >
          {[...sources]
            .sort((left, right) => (right.score ?? 0) - (left.score ?? 0))
            .map((source, index) => (
              <SourceCard
                key={`${source.chunk_id ?? source.source}-${index}`}
                source={source}
                pinnedState={pinnedSources?.find((item) => item.chunk_id === source.chunk_id)}
              />
            ))}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
