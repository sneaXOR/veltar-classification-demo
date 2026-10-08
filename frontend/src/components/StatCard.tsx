import type { LucideIcon } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from './ui/card'

export function StatCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string
  value: string | number
  detail: string
  icon?: LucideIcon
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0 border-b border-border/70 bg-[linear-gradient(180deg,hsl(210_22%_99%),hsl(214_24%_96%))] pb-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">{label}</p>
          <CardTitle className="mt-2 text-3xl tracking-tight">{value}</CardTitle>
        </div>
        {Icon ? (
          <div className="rounded-2xl border border-border bg-surface p-2.5 text-[hsl(24_50%_42%)] shadow-sm">
            <Icon className="h-4 w-4" />
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="pt-4">
        <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  )
}
