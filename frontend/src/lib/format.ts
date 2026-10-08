const PLACEHOLDER = '-'

export function formatDateTime(value: string | Date | null | undefined) {
  if (!value) return PLACEHOLDER
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return PLACEHOLDER
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function formatDurationMs(value: number | null | undefined) {
  if (value === null || value === undefined) return PLACEHOLDER
  if (!Number.isFinite(value)) return PLACEHOLDER
  if (value < 1000) return `${Math.round(value)} ms`

  const totalSeconds = Math.max(0, Math.round(value / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  if (hours > 0) {
    return `${hours} h ${String(minutes).padStart(2, '0')} min`
  }
  if (minutes > 0) {
    return `${minutes} min ${String(seconds).padStart(2, '0')} s`
  }
  return `${seconds} s`
}

export function formatCount(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '0'
  return new Intl.NumberFormat('fr-FR').format(value)
}

export function shortId(value: string | null | undefined, length = 8) {
  if (!value) return PLACEHOLDER
  return value.slice(0, length)
}
