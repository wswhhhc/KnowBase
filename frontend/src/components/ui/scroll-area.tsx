import * as React from 'react'
import * as ScrollAreaPrimitive from '@radix-ui/react-scroll-area'
import { cn } from '@/lib/utils'

interface ScrollAreaProps extends React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Viewport> {
  className?: string
  children: React.ReactNode
}

export const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ className, children, ...props }, ref) => (
    <ScrollAreaPrimitive.Root className={cn('overflow-hidden', className)}>
      <ScrollAreaPrimitive.Viewport
        ref={ref}
        className="h-full w-full rounded-[inherit] [&>div]:!block"
        {...props}
      >
        {children}
      </ScrollAreaPrimitive.Viewport>
      <ScrollAreaPrimitive.Scrollbar
        orientation="vertical"
        className="flex touch-none select-none py-1 transition-colors w-1.5"
      >
        <ScrollAreaPrimitive.Thumb className="relative flex-1 rounded-full bg-muted-foreground/20" />
      </ScrollAreaPrimitive.Scrollbar>
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  ),
)
ScrollArea.displayName = 'ScrollArea'
