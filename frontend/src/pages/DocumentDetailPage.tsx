import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  XCircle,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import {
  fetchDocumentClassification,
  fetchDocuments,
  getArtifactDownloadUrl,
  getOriginalDownloadUrl,
  updateReview,
  type ClassificationRecord,
  type DocumentRecord,
} from '../lib/api'
import { formatDateTime, formatDurationMs } from '../lib/format'
import { useLanguage } from '../lib/language'
import { getMarkingLabel, replaceMarkingCodesInText } from '../lib/marking-labels'
import { getDocumentStatusTone, getReviewStatusTone } from '../lib/presentation'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'

type ReasoningSection = {
  title?: string
  items: Array<{
    kind: 'paragraph'
    value: string
  }>
}

type KeyPassage = {
  pageNumber: number
  reason: string
  excerpt?: string
}

function getCopy(uiLanguage: 'en' | 'fr') {
  if (uiLanguage === 'fr') {
    return {
      classificationUnavailable: 'Classification indisponible.',
      identification: "Identification de l'element examine",
      militaryAnalysis: 'Analyse militaire',
      dualUseAnalysis: 'Analyse double usage',
      itarAssessment: 'Evaluation ITAR',
      earAnalysis: 'Analyse EAR / CCL',
      technicalAnalysis: 'Analyse technique du document',
      decisionAndAction: 'Decision et action',
      humanValidation: 'Une validation humaine reste necessaire avant diffusion du marquage.',
      usableButModerate: 'Le verdict reste exploitable, mais la confiance est moderee.',
      review: 'Revue',
      reviewAwaitingAction: 'Une action humaine est attendue pour confirmer ou refuser ce marquage.',
      analystName: 'Nom analyste',
      approve: 'Approuver',
      needsInfo: 'Infos requises',
      reject: 'Rejeter',
      noPendingAction: 'Aucune action en attente.',
      noReviewRequested: 'Pas de revue demandee.',
      loading: 'Chargement',
      documentNotFound: 'Document introuvable.',
      analysisInProgress: 'Analyse en cours',
      queued: 'En attente',
      back: 'Retour',
      document: 'Document',
      markedDocument: 'Document marque',
      verdict: 'Verdict',
      reviewRequired: 'Revue requise',
      usableDecision: 'Decision exploitable',
      justification: 'Justification',
      noRationale: 'Aucune justification restituee.',
      decisivePassages: 'Passages decisifs',
      decisivePassagesCopy: 'Quelques passages vraiment utilises pour porter le verdict.',
      page: 'Page',
      info: 'Infos',
      time: 'Temps',
      pages: 'Pages',
      marking: 'Marquage',
      available: 'Disponible',
      missing: 'Absent',
      original: 'Original',
    }
  }

  return {
    classificationUnavailable: 'Classification unavailable.',
    identification: 'Identification of the examined item',
    militaryAnalysis: 'Military analysis',
    dualUseAnalysis: 'Dual-use analysis',
    itarAssessment: 'ITAR assessment',
    earAnalysis: 'EAR / CCL analysis',
    technicalAnalysis: 'Technical analysis of the document',
    decisionAndAction: 'Decision and action',
    humanValidation: 'Human validation is still required before releasing the marking.',
    usableButModerate: 'The verdict is usable, but confidence remains moderate.',
    review: 'Review',
    reviewAwaitingAction: 'Human action is expected to confirm or reject this marking.',
    analystName: 'Analyst name',
    approve: 'Approve',
    needsInfo: 'Needs info',
    reject: 'Reject',
    noPendingAction: 'No pending action.',
    noReviewRequested: 'No review requested.',
    loading: 'Loading',
    documentNotFound: 'Document not found.',
    analysisInProgress: 'Analysis in progress',
    queued: 'Queued',
    back: 'Back',
    document: 'Document',
    markedDocument: 'Marked document',
    verdict: 'Verdict',
    reviewRequired: 'Review required',
    usableDecision: 'Usable decision',
    justification: 'Rationale',
    noRationale: 'No rationale available.',
    decisivePassages: 'Key passages',
    decisivePassagesCopy: 'A few passages that materially supported the verdict.',
    page: 'Page',
    info: 'Info',
    time: 'Time',
    pages: 'Pages',
    marking: 'Marking',
    available: 'Available',
    missing: 'Missing',
    original: 'Original',
  }
}

function getErrorMessage(error: unknown, uiLanguage: 'en' | 'fr') {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response
    if (response?.data?.detail) return response.data.detail
  }
  return error instanceof Error ? error.message : getCopy(uiLanguage).classificationUnavailable
}

function cleanInlineText(value?: string | null) {
  return (value ?? '').replace(/\s+/g, ' ').replace(/^[-*]\s*/, '').trim()
}

function normalizeLabelToken(value: string) {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[\u2019']/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

function getDisplayTitles(uiLanguage: 'en' | 'fr'): Record<string, string> {
  const copy = getCopy(uiLanguage)
  return {
    'identification du tangible': copy.identification,
    "identification de l element analyse": copy.identification,
    "identification de l element examine": copy.identification,
    'identification of the examined item': copy.identification,
    'military analysis': copy.militaryAnalysis,
    'analyse militaire': copy.militaryAnalysis,
    'itar assessment': copy.itarAssessment,
    'analyse itar': copy.itarAssessment,
    'dual-use analysis': copy.dualUseAnalysis,
    'analyse double usage': copy.dualUseAnalysis,
    'ear analysis (us dual-use)': copy.earAnalysis,
    'ear analysis  us dual-use': copy.earAnalysis,
    'ear / ccl analysis': copy.earAnalysis,
    'analyse ear (dual-use us)': copy.earAnalysis,
    'analyse ear  dual-use us': copy.earAnalysis,
    'analyse ear / ccl': copy.earAnalysis,
    'technical analysis of the document': copy.technicalAnalysis,
    'analyse technique du document': copy.technicalAnalysis,
    'decision and action': copy.decisionAndAction,
    'decision et action': copy.decisionAndAction,
  }
}

function isUpperHeading(line: string) {
  const candidate = line.replace(/^\d+[.)]?\s*/, '').trim()
  return Boolean(candidate) && candidate === candidate.toUpperCase() && /[A-Z]/.test(candidate)
}

function formatHeading(line: string, uiLanguage: 'en' | 'fr') {
  const normalized = cleanInlineText(line)
    .replace(/^\d+[.)]?\s*/, '')
    .replace(/\(si non militaire\)/gi, '')
    .replace(/[:.]$/, '')
    .trim()
  const displayOverride = getDisplayTitles(uiLanguage)[normalizeLabelToken(normalized)]
  if (displayOverride) return displayOverride
  const lowerCased = normalized.toLowerCase()
  return lowerCased.replace(/(^|[\s/-])([a-z0-9])/g, (_, prefix: string, letter: string) => {
    return `${prefix}${letter.toUpperCase()}`
  })
}

function getSectionHeading(line: string, uiLanguage: 'en' | 'fr') {
  if (/^\d+[.)]?\s+/.test(line)) return formatHeading(line, uiLanguage)
  if (isUpperHeading(line) && line.length <= 120) return formatHeading(line, uiLanguage)
  return null
}

function parseReasoningSections(summary?: string | null, uiLanguage: 'en' | 'fr' = 'en'): ReasoningSection[] {
  if (!summary) return []

  const normalizedSummary = summary
    .replace(/\s+(?=\d+\.\s+(?:IDENTIFICATION|ANALYSE|DECISION))/gi, '\n')

  const lines = normalizedSummary
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (!lines.length) return []

  const sections: ReasoningSection[] = []
  let current: ReasoningSection = { items: [] }

  function pushCurrent() {
    if (!current.title && !current.items.length) return
    sections.push(current)
    current = { items: [] }
  }

  for (const rawLine of lines) {
    const line = rawLine.replace(/^[-*]\s*/, '').trim()
    if (!line) continue

    if (/^\d+[.)]?$/.test(line)) {
      pushCurrent()
      continue
    }

    const heading = getSectionHeading(line, uiLanguage)
    if (heading) {
      pushCurrent()
      current.title = heading
      continue
    }

    current.items.push({
      kind: 'paragraph',
      value: line,
    })
  }

  pushCurrent()

  if (!sections.length) {
    return [
      {
        items: lines
          .map((line) => cleanInlineText(line))
          .filter(Boolean)
          .map((value) => ({ kind: 'paragraph' as const, value })),
      },
    ]
  }

  return sections.map((section) => ({
    title: section.title,
    items: section.items
      .map((item) => ({ kind: 'paragraph' as const, value: cleanInlineText(item.value) }))
      .filter((item) => Boolean(item.value)),
  }))
}

function dedupeItems<T>(items: T[], keyFn: (item: T) => string) {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = keyFn(item)
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function getKeyPassages(classification: ClassificationRecord): KeyPassage[] {
  const items = classification.evidence_items
    .map((item) => ({
      pageNumber: item.page_number,
      reason: cleanInlineText(item.reason),
      excerpt: cleanInlineText(item.excerpt) || undefined,
    }))
    .filter((item) => item.reason || item.excerpt)
    .sort((left, right) => {
      if (Boolean(left.excerpt) !== Boolean(right.excerpt)) {
        return Number(Boolean(right.excerpt)) - Number(Boolean(left.excerpt))
      }
      return left.pageNumber - right.pageNumber
    })

  return dedupeItems(items, (item) => `${item.pageNumber}-${item.reason}-${item.excerpt ?? ''}`).slice(0, 4)
}

function getAttentionNote(classification: ClassificationRecord, uiLanguage: 'en' | 'fr') {
  const copy = getCopy(uiLanguage)
  if (classification.requires_human_review) {
    return copy.humanValidation
  }
  if (classification.final_confidence < 0.65) {
    return copy.usableButModerate
  }
  return null
}

function ReviewSection({
  classification,
  reviewerName,
  setReviewerName,
  reviewBusy,
  onAction,
  uiLanguage,
}: {
  classification: ClassificationRecord
  reviewerName: string
  setReviewerName: (value: string) => void
  reviewBusy: boolean
  onAction: (status: 'approved' | 'needs_info' | 'rejected') => Promise<void>
  uiLanguage: 'en' | 'fr'
}) {
  const copy = getCopy(uiLanguage)
  const reviewTone = classification.review ? getReviewStatusTone(classification.review.status, uiLanguage) : null

  return (
    <section className="app-panel overflow-hidden">
      <div className="panel-header">
        <h3 className="section-title">{copy.review}</h3>
        {reviewTone ? <Badge variant={reviewTone.variant}>{reviewTone.label}</Badge> : null}
      </div>

      <div className="panel-body space-y-4">
        {classification.review?.status === 'pending' ? (
          <>
            <p className="section-copy">
              {copy.reviewAwaitingAction}
            </p>

            <Input
              value={reviewerName}
              onChange={(event) => setReviewerName(event.target.value)}
              placeholder={copy.analystName}
              className="h-11 rounded-2xl"
            />

            <div className="grid gap-2 sm:grid-cols-3">
              <Button onClick={() => void onAction('approved')} disabled={reviewBusy}>
                {reviewBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                {copy.approve}
              </Button>
              <Button variant="outline" onClick={() => void onAction('needs_info')} disabled={reviewBusy}>
                <AlertTriangle className="h-4 w-4" />
                {copy.needsInfo}
              </Button>
              <Button variant="destructive" onClick={() => void onAction('rejected')} disabled={reviewBusy}>
                <XCircle className="h-4 w-4" />
                {copy.reject}
              </Button>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            {classification.review ? copy.noPendingAction : copy.noReviewRequested}
          </p>
        )}
      </div>
    </section>
  )
}

export function DocumentDetailPage() {
  const { uiLanguage } = useLanguage()
  const copy = getCopy(uiLanguage)
  const { documentId } = useParams()
  const [documentRecord, setDocumentRecord] = useState<DocumentRecord | null>(null)
  const [classification, setClassification] = useState<ClassificationRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState(copy.loading)
  const [error, setError] = useState<string | null>(null)
  const [reviewerName, setReviewerName] = useState('')
  const [reviewBusy, setReviewBusy] = useState(false)

  useEffect(() => {
    if (!documentId) return

    let cancelled = false
    const stableId = documentId

    async function load() {
      try {
        const documents = await fetchDocuments()
        const currentDocument = documents.find((item) => item.id === documentId)

        if (!currentDocument) {
          if (!cancelled) {
            setLoading(false)
            setError(copy.documentNotFound)
          }
          return
        }

        if (!cancelled) setDocumentRecord(currentDocument)

        const failedMessage = currentDocument.latest_job_error || currentDocument.processing_error
        if (currentDocument.latest_job_status === 'failed' || failedMessage) {
          if (!cancelled) {
            setLoading(false)
            setError(failedMessage ?? copy.classificationUnavailable)
          }
          return
        }

        if (!currentDocument.final_marking && currentDocument.latest_job_status !== 'completed') {
          if (!cancelled) {
            setClassification(null)
            setLoading(true)
            setError(null)
            setMessage(currentDocument.latest_job_status === 'running' ? copy.analysisInProgress : copy.queued)
          }
          return
        }

        const nextClassification = await fetchDocumentClassification(stableId)
        if (!cancelled) {
          setClassification(nextClassification)
          setLoading(false)
          setError(null)
        }
      } catch (nextError) {
        if (!cancelled) {
          setLoading(false)
          setError(getErrorMessage(nextError, uiLanguage))
        }
      }
    }

    void load()
    const intervalId = window.setInterval(() => {
      void load()
    }, 6000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [copy.analysisInProgress, copy.classificationUnavailable, copy.documentNotFound, copy.queued, documentId, uiLanguage])

  async function handleReviewAction(status: 'approved' | 'needs_info' | 'rejected') {
    if (!classification?.review?.id) return
    setReviewBusy(true)
    try {
      await updateReview(classification.review.id, {
        status,
        reviewer_name: reviewerName || undefined,
      })
      const nextClassification = await fetchDocumentClassification(classification.document_id)
      setClassification(nextClassification)
    } finally {
      setReviewBusy(false)
    }
  }

  const statusTone = documentRecord
    ? getDocumentStatusTone(documentRecord, uiLanguage)
    : { label: '-', variant: 'outline' as const }

  const reasoningSections = useMemo(
    () => (classification ? parseReasoningSections(classification.reasoning_summary, uiLanguage) : []),
    [classification, uiLanguage],
  )
  const keyPassages = useMemo(
    () => (classification ? getKeyPassages(classification) : []),
    [classification],
  )
  const attentionNote = useMemo(
    () => (classification ? getAttentionNote(classification, uiLanguage) : null),
    [classification, uiLanguage],
  )
  const downloadReady = Boolean(
    documentRecord && (documentRecord.artifact_status === 'ready' || documentRecord.artifact_available),
  )
  const inlineReview = classification?.review?.status === 'pending'

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3">
          <Button asChild variant="ghost" className="w-fit px-0">
            <Link to="/">
              <ArrowLeft className="h-4 w-4" />
              {copy.back}
            </Link>
          </Button>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-2xl font-semibold tracking-tight">
                {documentRecord?.original_filename ?? copy.document}
              </h2>
              <Badge variant={statusTone.variant}>{statusTone.label}</Badge>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              {documentRecord ? formatDateTime(documentRecord.updated_at) : '-'}
            </p>
          </div>
        </div>

        {downloadReady ? (
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <a href={getOriginalDownloadUrl(documentRecord!.id)} download>
                <FileText className="h-4 w-4" />
                {copy.original}
              </a>
            </Button>
            <Button asChild variant="outline">
              <a href={getArtifactDownloadUrl(documentRecord!.id)} download>
                <Download className="h-4 w-4" />
                {copy.markedDocument}
              </a>
            </Button>
          </div>
        ) : null}
      </div>

      {error ? (
        <section className="app-panel border-destructive/25 bg-destructive/5">
          <div className="panel-body flex items-start gap-3">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <p className="text-sm text-destructive">{error}</p>
          </div>
        </section>
      ) : null}

      {loading && !classification ? (
        <section className="app-panel">
          <div className="panel-body flex min-h-[220px] items-center justify-center">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {message}
            </div>
          </div>
        </section>
      ) : null}

      {classification ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
          <div className="space-y-6">
            <section className="app-panel overflow-hidden">
              <div className="panel-body space-y-6">
                <div className="space-y-3">
                  <p className="eyebrow">{copy.verdict}</p>
                  <h3 className="text-3xl font-semibold tracking-tight">
                    {getMarkingLabel(classification.final_marking, uiLanguage)}
                  </h3>

                  <div className="flex flex-wrap gap-2">
                    <Badge variant={classification.requires_human_review ? 'warning' : 'success'}>
                      {classification.requires_human_review ? copy.reviewRequired : copy.usableDecision}
                    </Badge>
                  </div>

                  {attentionNote ? (
                    <p className="text-sm leading-6 text-muted-foreground">{attentionNote}</p>
                  ) : null}
                </div>

                <div className="workspace-divider" />

                <div className="space-y-4">
                  <p className="metric-label">{copy.justification}</p>
                  {reasoningSections.length ? (
                    <div className="space-y-4">
                      {reasoningSections.map((section, index) => (
                        <div
                          key={`${section.title ?? 'section'}-${index}`}
                          className="rounded-[20px] border border-border/70 bg-surface px-4 py-4"
                        >
                            {section.title ? (
                              <p className="text-sm font-semibold text-foreground">
                                {replaceMarkingCodesInText(section.title, uiLanguage)}
                              </p>
                            ) : null}
                          <div className="space-y-3">
                            {section.items.map((item) => (
                              <p key={item.value} className="text-sm leading-7 text-muted-foreground">
                                {replaceMarkingCodesInText(item.value, uiLanguage)}
                              </p>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">{copy.noRationale}</p>
                  )}
                </div>
              </div>
            </section>

            {inlineReview ? (
              <ReviewSection
                classification={classification}
                reviewerName={reviewerName}
                setReviewerName={setReviewerName}
                reviewBusy={reviewBusy}
                onAction={handleReviewAction}
                uiLanguage={uiLanguage}
              />
            ) : null}

            {keyPassages.length ? (
              <section className="app-panel overflow-hidden">
                <div className="panel-header">
                  <div>
                    <h3 className="section-title">{copy.decisivePassages}</h3>
                    <p className="section-copy">{copy.decisivePassagesCopy}</p>
                  </div>
                </div>

                <div className="panel-body space-y-4">
                  {keyPassages.map((passage) => (
                    <div
                      key={`${passage.pageNumber}-${passage.reason}-${passage.excerpt ?? ''}`}
                      className="rounded-[20px] border border-border/70 bg-surface px-4 py-4"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">
                          {copy.page} {passage.pageNumber}
                        </Badge>
                      </div>
                      <p className="mt-3 text-sm leading-7">{replaceMarkingCodesInText(passage.reason, uiLanguage)}</p>
                      {passage.excerpt ? (
                        <p className="mt-3 text-sm leading-6 text-muted-foreground">
                          "{replaceMarkingCodesInText(passage.excerpt, uiLanguage)}"
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </section>
            ) : null}
          </div>

          <aside className="sticky-rail space-y-6">
            <section className="app-panel overflow-hidden">
              <div className="panel-header">
                <h3 className="section-title">{copy.info}</h3>
              </div>

              <div className="panel-body space-y-4">
                <div className="space-y-3 text-sm text-muted-foreground">
                  <div className="flex items-center justify-between gap-3">
                    <span>{copy.time}</span>
                    <span className="text-foreground">{formatDurationMs(documentRecord?.duration_ms)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>{copy.pages}</span>
                    <span className="text-foreground">{documentRecord?.page_count ?? '-'}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>{copy.marking}</span>
                    <span className="text-foreground">{downloadReady ? copy.available : copy.missing}</span>
                  </div>
                </div>
              </div>
            </section>

            {!inlineReview ? (
              <ReviewSection
                classification={classification}
                reviewerName={reviewerName}
                setReviewerName={setReviewerName}
                reviewBusy={reviewBusy}
                onAction={handleReviewAction}
                uiLanguage={uiLanguage}
              />
            ) : null}
          </aside>
        </div>
      ) : null}
    </div>
  )
}
