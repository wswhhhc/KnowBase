import type { Source } from '@/lib/api'
import { useChatContext } from './ChatContext'

interface CitationTextProps {
  text: string
  sources?: Source[]
}

export default function CitationText({ text, sources }: CitationTextProps) {
  const { onCitationClick } = useChatContext()
  const parts = text.split(/(\[\d+(?:,\d+)*\])/g)
  const sourceMap = new Map(sources?.map((source) => [source.index, source]) ?? [])

  return (
    <span>
      {parts.map((part, index) => {
        const match = part.match(/\[(\d+(?:,\d+)*)\]/)
        if (!match) {
          return <span key={index}>{part}</span>
        }

        const indices = match[1].split(',').map(Number)
        const firstSource = sourceMap.get(indices[0])

        return (
          <sup
            key={index}
            onClick={() => firstSource && onCitationClick?.(firstSource)}
            className={`inline-flex items-center justify-center min-w-[1.1em] h-3.5 px-0.5 rounded text-2xs font-medium bg-primary/15 text-primary transition-colors ${
              onCitationClick ? 'cursor-pointer hover:bg-primary/30' : 'cursor-help hover:bg-primary/25'
            }`}
            title={indices.map((citationIndex) => {
              const source = sourceMap.get(citationIndex)
              return source ? `${source.source}${source.chunk_index != null ? ` #${source.chunk_index}` : ''}` : `来源 ${citationIndex}`
            }).join('、')}
          >
            {match[1]}
          </sup>
        )
      })}
    </span>
  )
}
