import { AnimatePresence, motion } from 'framer-motion'
import type { Source } from '@/lib/api'
import type { PinnedSource } from '@/hooks/useChat'
import SourceCard from './SourceCard'

interface SourcePanelProps {
  open: boolean
  sources?: Source[]
  pinnedSources?: PinnedSource[]
  onCitationClick?: (source: Source) => void
  onSendQuestion?: (question: string) => void
  onPinToggle?: (chunkId: string, action: 'pin' | 'unpin' | 'exclude' | 'unexclude') => void
}

export default function SourcePanel({
  open,
  sources,
  pinnedSources,
  onCitationClick,
  onSendQuestion,
  onPinToggle,
}: SourcePanelProps) {
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
                onCitationClick={onCitationClick}
                onSendQuestion={onSendQuestion}
                onPinToggle={onPinToggle}
              />
            ))}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
