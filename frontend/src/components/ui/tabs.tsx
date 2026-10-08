import { cn } from '../../lib/utils'

export type TabItem = {
  value: string
  label: string
  description?: string
}

export function TabsBar({
  items,
  value,
  onChange,
  className,
}: {
  items: TabItem[]
  value: string
  onChange: (value: string) => void
  className?: string
}) {
  return (
    <div className={cn('flex flex-wrap gap-2 rounded-2xl border border-border bg-surface/90 p-2 shadow-panel', className)}>
      {items.map((item) => {
        const active = item.value === value
        return (
          <button
            key={item.value}
            type="button"
            onClick={() => onChange(item.value)}
            className={cn(
              'flex min-w-[10rem] flex-1 flex-col items-start gap-0.5 rounded-xl px-3 py-2 text-left transition-all',
              active
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            <span className="text-sm font-semibold">{item.label}</span>
            {item.description ? <span className={cn('text-[11px] leading-4', active ? 'text-primary-foreground/80' : 'text-muted-foreground')}>{item.description}</span> : null}
          </button>
        )
      })}
    </div>
  )
}

