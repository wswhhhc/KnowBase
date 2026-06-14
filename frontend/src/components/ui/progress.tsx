import { cn } from '@/lib/utils'

type ProgressColor = 'primary' | 'emerald' | 'amber' | 'violet' | 'red'

interface ProgressProps {
  value: number
  max?: number
  className?: string
  barClassName?: string
  color?: ProgressColor
}

const colorMap: Record<ProgressColor, string> = {
  primary: 'bg-primary',
  emerald: 'bg-emerald-500',
  amber: 'bg-amber-500',
  violet: 'bg-violet-500',
  red: 'bg-red-500',
}

export function Progress({ value, max = 100, className, barClassName, color = 'primary' }: ProgressProps) {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100)
  return (
    <div className={cn('progress-bar', className)}>
      <div className={cn('progress-bar-fill', colorMap[color], barClassName)} style={{ width: `${pct}%` }} />
    </div>
  )
}
