import { useRef, useState } from 'react'
import { Button, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, Switch, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui'
import { Globe, SlidersHorizontal } from 'lucide-react'
import { SEARCH_STRATEGIES, type SearchStrategy } from '@/features/chat/hooks/useSearchPreferences'

interface SearchPreferencesPanelProps {
  variant: 'desktop' | 'mobile'
  webSearch: boolean
  onWebSearchChange: (enabled: boolean) => void
  searchStrategy: SearchStrategy
  onSearchStrategyChange: (strategy: SearchStrategy) => void
}

interface SearchStrategyOptionsProps {
  variant: 'desktop' | 'mobile'
  searchStrategy: SearchStrategy
  onSearchStrategyChange: (strategy: SearchStrategy) => void
  onSelect?: () => void
}

function SearchStrategyOptions({
  variant,
  searchStrategy,
  onSearchStrategyChange,
  onSelect,
}: SearchStrategyOptionsProps) {
  const strategyRefs = useRef<Array<HTMLButtonElement | null>>([])
  const isMobile = variant === 'mobile'

  const focusStrategyAtIndex = (index: number) => {
    const nextIndex = (index + SEARCH_STRATEGIES.length) % SEARCH_STRATEGIES.length
    const nextStrategy = SEARCH_STRATEGIES[nextIndex]
    onSearchStrategyChange(nextStrategy.key)
    strategyRefs.current[nextIndex]?.focus()
  }

  const handleStrategyKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        event.preventDefault()
        focusStrategyAtIndex(index + 1)
        break
      case 'ArrowLeft':
      case 'ArrowUp':
        event.preventDefault()
        focusStrategyAtIndex(index - 1)
        break
      case 'Home':
        event.preventDefault()
        focusStrategyAtIndex(0)
        break
      case 'End':
        event.preventDefault()
        focusStrategyAtIndex(SEARCH_STRATEGIES.length - 1)
        break
    }
  }

  return (
    <div
      className={isMobile ? 'grid gap-2' : 'flex items-center gap-0.5 rounded-md border border-border p-0.5'}
      role="radiogroup"
      aria-label="检索策略"
    >
      {SEARCH_STRATEGIES.map(({ key, icon: Icon, label, description }, index) => {
        const option = (
          <button
            key={key}
            ref={(node) => { strategyRefs.current[index] = node }}
            role="radio"
            aria-label={label}
            aria-checked={searchStrategy === key}
            tabIndex={searchStrategy === key ? 0 : -1}
            onClick={() => {
              onSearchStrategyChange(key)
              onSelect?.()
            }}
            onKeyDown={(event) => handleStrategyKeyDown(event, index)}
            className={isMobile
              ? `rounded-lg border px-3 py-3 text-left transition-colors ${
                searchStrategy === key
                  ? 'border-primary/30 bg-primary/10 text-primary'
                  : 'border-border text-foreground hover:bg-muted/40'
              }`
              : `inline-flex items-center gap-1 rounded-sm px-2 py-1 text-xs font-medium transition-colors ${
                searchStrategy === key ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground'
              }`}
          >
            {isMobile ? (
              <>
                <div className="flex items-center gap-2 text-sm font-medium"><Icon className="h-4 w-4" />{label}</div>
                <p className="mt-1 text-xs text-muted-foreground">{description}</p>
              </>
            ) : (
              <><Icon className="h-3 w-3" />{label}</>
            )}
          </button>
        )

        if (isMobile) return option
        return (
          <TooltipProvider key={key}>
            <Tooltip>
              <TooltipTrigger asChild>{option}</TooltipTrigger>
              <TooltipContent>{description}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )
      })}
    </div>
  )
}

export default function SearchPreferencesPanel({
  variant,
  webSearch,
  onWebSearchChange,
  searchStrategy,
  onSearchStrategyChange,
}: SearchPreferencesPanelProps) {
  const [strategyDialogOpen, setStrategyDialogOpen] = useState(false)
  const isMobile = variant === 'mobile'

  return (
    <div className="flex min-w-0 flex-wrap items-center justify-end gap-1">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
              <Globe className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">搜索</span>
              <Switch checked={webSearch} onCheckedChange={onWebSearchChange} />
            </label>
          </TooltipTrigger>
          <TooltipContent>联网搜索开关</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      {isMobile ? (
        <>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setStrategyDialogOpen(true)}
            aria-label="检索与策略"
            className="gap-1 px-2"
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            {SEARCH_STRATEGIES.find(({ key }) => key === searchStrategy)?.label}
          </Button>
          <Dialog open={strategyDialogOpen} onOpenChange={setStrategyDialogOpen}>
            <DialogContent className="max-w-sm">
              <DialogHeader>
                <DialogTitle>检索与策略</DialogTitle>
                <DialogDescription>按问题复杂度选择检索强度，移动端默认收起以保留主任务空间。</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 pt-2">
                <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
                  <div>
                    <p className="text-sm font-medium text-foreground">联网搜索</p>
                    <p className="text-xs text-muted-foreground">需要最新信息时开启</p>
                  </div>
                  <Switch checked={webSearch} onCheckedChange={onWebSearchChange} />
                </div>
                <SearchStrategyOptions
                  variant="mobile"
                  searchStrategy={searchStrategy}
                  onSearchStrategyChange={onSearchStrategyChange}
                  onSelect={() => setStrategyDialogOpen(false)}
                />
              </div>
            </DialogContent>
          </Dialog>
        </>
      ) : (
        <SearchStrategyOptions
          variant="desktop"
          searchStrategy={searchStrategy}
          onSearchStrategyChange={onSearchStrategyChange}
        />
      )}
    </div>
  )
}
