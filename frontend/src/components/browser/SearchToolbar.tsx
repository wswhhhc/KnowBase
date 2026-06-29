import { Input } from '@/components/ui'
import { Search, Flame, LayoutGrid, List } from 'lucide-react'

interface SearchToolbarProps {
  searchQuery: string
  setSearchQuery: (v: string) => void
  handleSearch: () => void
  selectedSource: string
  sources: string[]
  onSourceClick: (src: string) => void
  chunkView: 'grid' | 'slice'
  setChunkView: (v: 'grid' | 'slice') => void
  hotspotMode: boolean
  toggleHotspotMode: () => void
  kbConfig: { chunk_size: number; chunk_overlap: number } | null
  showViewControls: boolean
}

export default function SearchToolbar({
  searchQuery, setSearchQuery, handleSearch,
  selectedSource, sources, onSourceClick,
  chunkView, setChunkView, hotspotMode, toggleHotspotMode, kbConfig, showViewControls,
}: SearchToolbarProps) {
  return (
    <>
      <div className="flex items-center gap-3 border-b border-border px-5 py-2.5 bg-surface/30">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/50" />
          <Input
            placeholder="搜索文档内容…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSearch() }}
            className="pl-9 h-8 text-xs"
          />
        </div>
        <div className="flex gap-1 flex-wrap flex-1">
          <button onClick={() => onSourceClick('')}
            className={`px-2.5 py-1 text-2xs font-medium rounded-md transition-colors ${
              !selectedSource ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground bg-muted/50'
            }`}>
            全部
          </button>
          {sources.slice(0, 8).map((s) => (
            <button key={s} onClick={() => onSourceClick(s)}
              className={`px-2.5 py-1 text-2xs font-medium rounded-md transition-colors max-w-[120px] truncate ${
                selectedSource === s ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground bg-muted/50'
              }`}>
              {s}
            </button>
          ))}
          {sources.length > 8 && (
            <span className="px-2 py-1 text-2xs text-muted-foreground">+{sources.length - 8}</span>
          )}
        </div>
      </div>

      {showViewControls && (
        <div className="flex items-center gap-2 border-b border-border px-5 py-1.5 bg-surface/20">
          <div className="flex items-center gap-0.5 rounded-md border border-border p-0.5">
            <button onClick={() => setChunkView('grid')}
              className={`p-1 rounded-sm transition-colors ${chunkView === 'grid' ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
              <LayoutGrid className="h-3 w-3" />
            </button>
            <button onClick={() => setChunkView('slice')}
              className={`p-1 rounded-sm transition-colors ${chunkView === 'slice' ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
              <List className="h-3 w-3" />
            </button>
          </div>
          <span className="text-2xs text-muted-foreground/50">
            {chunkView === 'grid' ? '网格视图' : '切片视图'}
          </span>
          <div className="h-3 w-px bg-border mx-1" />
          <button onClick={toggleHotspotMode}
            className={`flex items-center gap-1 px-2 py-1 text-2xs font-medium rounded-md transition-colors ${
              hotspotMode ? 'bg-orange-500/15 text-orange-400' : 'text-muted-foreground hover:text-foreground bg-muted/30'
            }`}>
            <Flame className="h-3 w-3" />
            热点
          </button>
          {kbConfig && (
            <span className="text-2xs text-muted-foreground/30 ml-auto font-mono">
              chunk: {kbConfig.chunk_size} · overlap: {kbConfig.chunk_overlap}
            </span>
          )}
        </div>
      )}
    </>
  )
}
