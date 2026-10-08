import type { LucideIcon } from 'lucide-react'

import { Button } from './button'
import { Card, CardContent } from './card'

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: LucideIcon
  title: string
  description: string
  action?: { label: string; onClick: () => void }
}) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center gap-3 px-6 py-12 text-center">
        {Icon ? (
          <div className="rounded-2xl border border-border bg-secondary/60 p-3 text-muted-foreground">
            <Icon className="h-5 w-5" />
          </div>
        ) : null}
        <div className="space-y-1">
          <p className="text-base font-semibold text-foreground">{title}</p>
          <p className="max-w-lg text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
        {action ? (
          <Button variant="outline" size="sm" onClick={action.onClick}>
            {action.label}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}

