import { FileText, Hash, Layers, ArrowLeft, BookOpen, PanelRightOpen } from 'lucide-react'
import type { KBStats } from '@/lib/api'

interface BrowserHeaderProps {
  stats: KBStats | null
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: 'chat' | 'browser' | 'dashboard' | 'settings') => void
  workspaceName?: string
}

export default function BrowserHeader({ stats, onOpenSidebar, sidebarOpen, onNavigate, workspaceName = '默认工作区' }: BrowserHeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-border px-5 py-3 bg-background/80 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        {!sidebarOpen && (
            <button onClick={onOpenSidebar} className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
              <PanelRightOpen className="h-4 w-4" />
            </button>
          )}
        <button onClick={() => onNavigate('chat')}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mr-1">
          <ArrowLeft className="h-3.5 w-3.5" />返回
        </button>
        <div className="h-4 w-px bg-border" />
        <BookOpen className="h-4 w-4 text-primary" />
        <div>
          <h1 className="font-heading text-lg text-foreground tracking-tight">知识库</h1>
          <p className="text-2xs text-muted-foreground/60">当前工作区：{workspaceName}</p>
        </div>
      </div>

      {stats && (
        <div className="hidden md:flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><FileText className="h-3 w-3" />{stats.chunk_count} 段落</span>
          <span className="flex items-center gap-1"><Layers className="h-3 w-3" />{stats.source_count} 引用文档</span>
          <span className="flex items-center gap-1"><Hash className="h-3 w-3" />{(stats.total_chars / 1000).toFixed(0)}k 字符</span>
        </div>
      )}
    </header>
  )
}
