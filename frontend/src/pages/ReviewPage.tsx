import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

import {
  fetchDocumentClassification,
  fetchDocuments,
  updateReview,
  type ClassificationRecord,
  type DocumentRecord,
  type ReviewRecord,
} from '../lib/api'
import { formatCount } from '../lib/format'
import { useLanguage } from '../lib/language'
import { getLaneLabel, getMarkingLabel, replaceMarkingCodesInText } from '../lib/marking-labels'
import { getReviewStatusTone } from '../lib/presentation'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { EmptyState } from '../components/ui/empty-state'
import { Input } from '../components/ui/input'

type ReviewItem = {
  doc: DocumentRecord
  classification: ClassificationRecord
  review: ReviewRecord
}

function getCopy(uiLanguage: 'en' | 'fr') {
  if (uiLanguage === 'fr') {
    return {
      loadingImpossible: 'Chargement impossible.',
      open: 'Ouvrir',
      approve: 'Approuver',
      info: 'Infos',
      reject: 'Rejeter',
      noReview: 'Aucune revue',
      noReviewDescription: 'Les cas a arbitrer apparaitront ici.',
      queue: 'File',
      total: 'Total',
      pending: 'En attente',
      analystName: 'Nom analyste',
    }
  }

  return {
    loadingImpossible: 'Unable to load reviews.',
    open: 'Open',
    approve: 'Approve',
    info: 'Needs info',
    reject: 'Reject',
    noReview: 'No reviews',
    noReviewDescription: 'Cases requiring arbitration will appear here.',
    queue: 'Queue',
    total: 'Total',
    pending: 'Pending',
    analystName: 'Analyst name',
  }
}

function getErrorMessage(error: unknown, uiLanguage: 'en' | 'fr') {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response
    if (response?.data?.detail) return response.data.detail
  }
  return error instanceof Error ? error.message : getCopy(uiLanguage).loadingImpossible
}

export function ReviewPage() {
  const { uiLanguage } = useLanguage()
  const copy = getCopy(uiLanguage)
  const [items, setItems] = useState<ReviewItem[]>([])
  const [reviewerName, setReviewerName] = useState('')
  const [busyReviewId, setBusyReviewId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const stats = useMemo(
    () => ({
      total: items.length,
      pending: items.filter((item) => item.review.status === 'pending').length,
    }),
    [items],
  )

  async function refresh() {
    try {
      const documents = await fetchDocuments()
      const reviewDocuments = documents.filter((doc) => doc.requires_human_review || doc.review_status === 'pending')
      const nextItems = await Promise.all(
        reviewDocuments.map(async (doc) => {
          try {
            const classification = await fetchDocumentClassification(doc.id)
            if (!classification.review) return null
            return { doc, classification, review: classification.review }
          } catch {
            return null
          }
        }),
      )
      setItems(nextItems.filter((item): item is ReviewItem => Boolean(item)))
      setError(null)
    } catch (nextError) {
      setError(getErrorMessage(nextError, uiLanguage))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [uiLanguage])

  async function handleUpdate(reviewId: string, status: 'approved' | 'needs_info' | 'rejected') {
    setBusyReviewId(reviewId)
    try {
      const updated = await updateReview(reviewId, {
        status,
        reviewer_name: reviewerName || undefined,
      })
      setItems((current) =>
        current.map((item) => (item.review.id === reviewId ? { ...item, review: updated } : item)),
      )
    } finally {
      setBusyReviewId(null)
    }
  }

  if (loading) {
    return (
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div className="app-panel h-[340px] animate-pulse" />
        <div className="app-panel h-[220px] animate-pulse" />
      </div>
    )
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
      <div className="space-y-4">
        {error ? (
          <section className="app-panel border-destructive/25 bg-destructive/5">
            <div className="panel-body flex items-start gap-3">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
          </section>
        ) : null}

        {items.length ? (
          items.map((item) => {
            const tone = getReviewStatusTone(item.review.status, uiLanguage)
            const isBusy = busyReviewId === item.review.id

            return (
              <section key={item.review.id} className="app-panel overflow-hidden">
                <div className="panel-body space-y-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-base font-medium">{item.doc.original_filename}</p>
                        <Badge variant={tone.variant}>{tone.label}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {getMarkingLabel(item.classification.final_marking, uiLanguage)}
                      </p>
                    </div>
                    <Badge variant="outline">{getLaneLabel(item.classification.lane, uiLanguage)}</Badge>
                  </div>

                  {item.classification.reasoning_summary ? (
                    <p className="text-sm leading-7 text-muted-foreground">
                      {replaceMarkingCodesInText(item.classification.reasoning_summary, uiLanguage)}
                    </p>
                  ) : null}

                  <div className="flex flex-wrap gap-2">
                    <Button asChild variant="outline">
                      <Link to={`/documents/${item.doc.id}`}>{copy.open}</Link>
                    </Button>
                    <Button onClick={() => void handleUpdate(item.review.id, 'approved')} disabled={isBusy}>
                      {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                      {copy.approve}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => void handleUpdate(item.review.id, 'needs_info')}
                      disabled={isBusy}
                    >
                      <AlertTriangle className="h-4 w-4" />
                      {copy.info}
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => void handleUpdate(item.review.id, 'rejected')}
                      disabled={isBusy}
                    >
                      <XCircle className="h-4 w-4" />
                      {copy.reject}
                    </Button>
                  </div>
                </div>
              </section>
            )
          })
        ) : (
          <EmptyState
            title={copy.noReview}
            description={copy.noReviewDescription}
          />
        )}
      </div>

      <aside className="sticky-rail">
        <section className="app-panel overflow-hidden">
          <div className="panel-header">
            <h2 className="section-title">{copy.queue}</h2>
          </div>
          <div className="panel-body space-y-4">
            <div className="space-y-2 text-sm text-muted-foreground">
              <div className="flex items-center justify-between gap-3">
                <span>{copy.total}</span>
                <span className="text-foreground">{formatCount(stats.total)}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span>{copy.pending}</span>
                <span className="text-foreground">{formatCount(stats.pending)}</span>
              </div>
            </div>

            <div className="workspace-divider" />

            <Input
              placeholder={copy.analystName}
              value={reviewerName}
              onChange={(event) => setReviewerName(event.target.value)}
              className="h-11 rounded-2xl"
            />
          </div>
        </section>
      </aside>
    </div>
  )
}
