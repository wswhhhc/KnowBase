import { cn } from '@/lib/utils'

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-muted', className)}
      {...props}
    />
  )
}

/** Single card skeleton — for list/grid placeholders. */
export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-lg border border-border bg-surface/30 p-4 animate-pulse', className)}>
      <div className="h-3 bg-muted rounded w-2/3 mb-3" />
      <div className="h-2 bg-muted rounded w-full mb-2" />
      <div className="h-2 bg-muted rounded w-5/6 mb-2" />
      <div className="h-2 bg-muted rounded w-4/6" />
    </div>
  )
}

/** Grid skeleton — responsive N-column placeholder grid. */
export function SkeletonGrid({ count = 6, className }: { count?: number; className?: string }) {
  return (
    <div className={cn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4', className)}>
      {Array.from({ length: count }).map((_, i) => <SkeletonCard key={i} />)}
    </div>
  )
}
