import * as React from 'react'
import { cn } from '@/lib/utils'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'secondary' | 'ghost' | 'destructive' | 'outline'
  size?: 'sm' | 'md' | 'lg'
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'md', ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-md font-body text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50',
        {
          'bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20': variant === 'default',
          'bg-secondary text-secondary-foreground hover:bg-secondary/80': variant === 'secondary',
          'hover:bg-muted text-foreground': variant === 'ghost',
          'bg-destructive text-destructive-foreground hover:bg-destructive/90': variant === 'destructive',
          'border border-border bg-transparent hover:bg-muted text-foreground': variant === 'outline',
        },
        {
          'h-8 px-3 text-xs': size === 'sm',
          'h-9 px-4 text-sm': size === 'md',
          'h-11 px-6 text-base': size === 'lg',
        },
        className,
      )}
      {...props}
    />
  ),
)
Button.displayName = 'Button'
