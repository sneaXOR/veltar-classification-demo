import * as React from 'react'
import * as ProgressPrimitive from '@radix-ui/react-progress'

import { cn } from '../../lib/utils'

export function Progress({
  className,
  value,
  indeterminate = false,
  ...props
}: React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & { indeterminate?: boolean }) {
  return (
    <ProgressPrimitive.Root
      className={cn('relative h-2 w-full overflow-hidden rounded-full bg-secondary', className)}
      value={value}
      {...props}
    >
      {indeterminate ? (
        <div className="absolute inset-y-0 left-0 animate-indeterminate-bar rounded-full bg-[linear-gradient(90deg,hsl(24_40%_42%),hsl(24_55%_58%))]" />
      ) : (
        <ProgressPrimitive.Indicator
          className="h-full w-full flex-1 bg-[linear-gradient(90deg,hsl(24_40%_42%),hsl(24_55%_58%))] transition-all"
          style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
        />
      )}
    </ProgressPrimitive.Root>
  )
}
