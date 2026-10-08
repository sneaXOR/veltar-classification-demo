import type { DocumentRecord, JobProgressRecord, JobRecord, SupportedLanguage } from './api'
import { getMarkingLabel } from './marking-labels'

export function getDocumentStatusTone(doc: DocumentRecord, language: SupportedLanguage = 'en') {
  if (doc.processing_error || doc.latest_job_error) {
    return { label: language === 'fr' ? 'Erreur' : 'Error', variant: 'destructive' as const }
  }
  if (doc.final_marking || doc.latest_job_status === 'completed') {
    return { label: language === 'fr' ? 'Termine' : 'Completed', variant: 'success' as const }
  }
  if (doc.latest_job_status === 'running') {
    return { label: language === 'fr' ? 'Analyse en cours' : 'Analyzing', variant: 'info' as const }
  }
  if (doc.latest_job_status === 'queued') {
    return { label: language === 'fr' ? 'En attente' : 'Queued', variant: 'warning' as const }
  }
  return { label: language === 'fr' ? 'Recu' : 'Received', variant: 'outline' as const }
}

export function getReviewStatusTone(status?: string | null, language: SupportedLanguage = 'en') {
  if (status === 'approved') {
    return { label: language === 'fr' ? 'Approuve' : 'Approved', variant: 'success' as const }
  }
  if (status === 'rejected') {
    return { label: language === 'fr' ? 'Rejete' : 'Rejected', variant: 'destructive' as const }
  }
  if (status === 'need_info' || status === 'needs_info') {
    return { label: language === 'fr' ? 'Infos requises' : 'Needs info', variant: 'warning' as const }
  }
  return { label: language === 'fr' ? 'En attente' : 'Pending', variant: 'warning' as const }
}

export function getConfidenceLevel(
  confidence: number,
  language: SupportedLanguage = 'en',
): { label: string; variant: 'success' | 'warning' | 'destructive'; percent: number } {
  const percent = Math.round(confidence * 100)
  if (confidence >= 0.8) {
    return { label: language === 'fr' ? 'Haute' : 'High', variant: 'success', percent }
  }
  if (confidence >= 0.5) {
    return { label: language === 'fr' ? 'Moyenne' : 'Medium', variant: 'warning', percent }
  }
  return { label: language === 'fr' ? 'Faible' : 'Low', variant: 'destructive', percent }
}

export function summarizeJob(job?: JobRecord | null) {
  if (!job) return null
  return {
    duration: job.duration_ms ?? null,
    model: job.model_name,
    runtime: job.runtime_name,
    progress: job.progress ?? null,
  }
}

export function getDecisionSummary(
  doc: DocumentRecord,
  classification: {
    final_marking: string
    final_confidence: number
    requires_human_review: boolean
    experimental: boolean
    lane: string
  },
  language: SupportedLanguage = 'en',
) {
  return {
    label: getMarkingLabel(classification.final_marking, language),
    code: classification.final_marking,
    confidence: Math.round(classification.final_confidence * 100),
    reviewRequired: classification.requires_human_review,
    experimental: classification.experimental,
    lane: classification.lane,
    status: getDocumentStatusTone(doc, language),
  }
}

export function getProgressStageLabel(stage: string | null | undefined, language: SupportedLanguage = 'en') {
  const labels =
    language === 'fr'
      ? {
          queued: 'File',
          ingesting: 'Prep',
          processing: 'Analyse',
          finalizing: 'Final',
          completed: 'Termine',
          failed: 'Erreur',
        }
      : {
          queued: 'Queue',
          ingesting: 'Prep',
          processing: 'Analyze',
          finalizing: 'Finalize',
          completed: 'Completed',
          failed: 'Failed',
        }

  if (!stage) return language === 'fr' ? 'Analyse' : 'Analyze'
  return labels[stage as keyof typeof labels] ?? stage
}

export function getProgressMessage(
  progress: JobProgressRecord | null | undefined,
  language: SupportedLanguage = 'en',
) {
  const stage = progress?.stage
  const currentPage = progress?.current_page
  const totalPages = progress?.total_pages

  if (stage === 'queued') {
    return language === 'fr' ? 'En attente de traitement' : 'Waiting for processing'
  }
  if (stage === 'ingesting') {
    return language === 'fr' ? 'Preparation du document' : 'Preparing document'
  }
  if (stage === 'processing' && currentPage && totalPages) {
    return language === 'fr'
      ? `Analyse de la page ${currentPage} sur ${totalPages}`
      : `Analyzing page ${currentPage} of ${totalPages}`
  }
  if (stage === 'processing') {
    return language === 'fr' ? 'Analyse du document' : 'Analyzing document'
  }
  if (stage === 'finalizing') {
    return language === 'fr' ? 'Analyse finale du document' : 'Finalizing document analysis'
  }
  if (stage === 'completed') {
    return language === 'fr' ? 'Analyse terminee' : 'Analysis completed'
  }
  if (stage === 'failed') {
    return language === 'fr' ? 'Analyse interrompue' : 'Analysis failed'
  }

  return language === 'fr' ? 'Analyse du document' : 'Analyzing document'
}

export function countReviewableDocuments(documents: DocumentRecord[]) {
  return documents.filter((doc) => doc.requires_human_review).length
}

export function countCompletedDocuments(documents: DocumentRecord[]) {
  return documents.filter((doc) => Boolean(doc.final_marking)).length
}

export function countActiveDocuments(documents: DocumentRecord[]) {
  return documents.filter((doc) =>
    Boolean(doc.latest_job_status && !['completed', 'failed'].includes(doc.latest_job_status)),
  ).length
}
