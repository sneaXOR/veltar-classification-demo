import axios from 'axios'

export const api = axios.create({
  baseURL: '',
  timeout: 120000,
})

export interface DashboardData {
  total_documents: number
  completed_documents: number
  pending_reviews: number
  failed_jobs: number
  batches: number
  by_marking: Record<string, number>
  by_status: Record<string, number>
}

export type UploadFileLike = File & {
  relativePath?: string
  webkitRelativePath?: string
}

export interface JobProgressRecord {
  stage: string
  stage_label: string
  message: string
  percent: number | null
  processed_pages: number | null
  total_pages: number | null
  current_page: number | null
}

export interface DocumentRecord {
  id: string
  batch_id: string | null
  client_profile_id?: string | null
  original_filename: string
  relative_path?: string | null
  media_type: string
  kind: string
  status: string
  page_count: number
  context_hint: string | null
  processing_error: string | null
  duration_ms?: number | null
  latest_job_id: string | null
  latest_job_status: string | null
  latest_job_error: string | null
  final_marking: string | null
  final_confidence: number | null
  experimental: boolean | null
  requires_human_review: boolean | null
  review_status: string | null
  review_priority: string | null
  progress: JobProgressRecord | null
  artifact_status?: string | null
  artifact_available?: boolean | null
  created_at: string
  updated_at: string
}

export interface JobRecord {
  id: string
  document_id: string
  status: string
  model_name: string
  runtime_name: string
  duration_ms: number | null
  error_message: string | null
  gate_report: Record<string, unknown>
  progress: JobProgressRecord | null
  created_at: string
  updated_at: string
}

export interface LLMRuntimeProfile {
  id: string
  label: string
  description: string
  runtime_name: string
  model_name: string
  base_url: string
  image_transport: string
  verify_ssl: boolean
  step2_visual_thinking: boolean
  timeout_seconds: number
  max_tokens: number
  local: boolean
  api_key_configured: boolean
}

export interface LLMRuntimeSettings {
  active_profile_id: string
  active_profile: LLMRuntimeProfile
  available_profiles: LLMRuntimeProfile[]
}

export type SupportedLanguage = 'en' | 'fr'

export interface LanguageSettings {
  ui_language: SupportedLanguage
  analysis_language: SupportedLanguage
  rationale_language: SupportedLanguage
}

export interface ReviewRecord {
  id: string
  status: string
  reviewer_name: string | null
  reviewer_note: string | null
  final_marking_override: string | null
  created_at: string
  updated_at: string
}

export interface ClassificationRecord {
  id: string
  document_id: string
  lane: string
  final_marking: string
  final_confidence: number
  experimental: boolean
  insufficient_evidence: boolean
  requires_human_review: boolean
  review_priority: string
  jurisdiction: string
  reasoning_summary: string
  candidate_markings: Array<{ code: string; confidence: number; reason: string }>
  citations: Array<{ source: string; title?: string }>
  evidence_items: Array<{ page_number: number; kind: string; excerpt?: string; reason: string; image_path?: string }>
  page_rollup: Record<string, unknown>
  step_results: Record<string, unknown>
  veltar_projection: Record<string, unknown>
  pipeline_version?: string
  lifecycle_phase?: string | null
  tangible_description?: string | null
  tangible_category?: string | null
  page_classifications: Array<{
    page_number: number
    relevant: boolean
    technical_score: number
    confidence: number
    summary: string
    evidence: Array<{ excerpt?: string; reason: string; kind: string }>
    citations: Array<{ source: string }>
    step_payload: Record<string, unknown>
  }>
  review?: ReviewRecord
}

// â”€â”€ Client Profiles â”€â”€

export interface ClientProfile {
  id: string
  name: string
  country: string
  activity_description: string | null
  product_families: string[]
  product_characteristics: Record<string, string>
  program_names: string[]
  naming_conventions: Record<string, string>
  classification_history: Array<Record<string, unknown>>
  regulatory_scope: string[]
  created_at: string
  updated_at: string
}

export interface ClientProfileCreate {
  name: string
  country: string
  activity_description?: string
  product_families?: string[]
  product_characteristics?: Record<string, string>
  program_names?: string[]
  naming_conventions?: Record<string, string>
  classification_history?: Array<Record<string, unknown>>
}

export async function fetchDashboard() {
  const { data } = await api.get<DashboardData>('/api/dashboard')
  return data
}

export async function fetchDocuments() {
  const { data } = await api.get<DocumentRecord[]>('/api/documents')
  return data
}

export async function fetchDocumentClassification(documentId: string) {
  const { data } = await api.get<ClassificationRecord>(`/api/documents/${documentId}/classification`)
  return data
}

export async function fetchPendingReviews() {
  const { data } = await api.get<ReviewRecord[]>('/api/reviews/pending')
  return data
}

export async function submitDocument(file: File, contextHint?: string, clientProfileId?: string) {
  const formData = new FormData()
  formData.append('file', file)
  if (contextHint) {
    formData.append('context_hint', contextHint)
  }
  if (clientProfileId) {
    formData.append('client_profile_id', clientProfileId)
  }
  const { data } = await api.post<{ document: DocumentRecord; job: JobRecord }>('/api/documents', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function submitBatch(files: UploadFileLike[], batchName?: string, clientProfileId?: string) {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('files', file)
    formData.append('relative_paths', file.relativePath || file.webkitRelativePath || '')
  })
  if (batchName) {
    formData.append('batch_name', batchName)
  }
  if (clientProfileId) {
    formData.append('client_profile_id', clientProfileId)
  }
  const { data } = await api.post<{ batch: { id: string }; jobs: JobRecord[] }>('/api/batches', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function fetchJob(jobId: string) {
  const { data } = await api.get<JobRecord>(`/api/jobs/${jobId}`)
  return data
}

export async function fetchLlmSettings() {
  const { data } = await api.get<LLMRuntimeSettings>('/api/settings/llm')
  return data
}

export async function updateLlmSettings(profileId: string) {
  const { data } = await api.put<LLMRuntimeSettings>('/api/settings/llm', { profile_id: profileId })
  return data
}

export async function fetchLanguageSettings() {
  const { data } = await api.get<LanguageSettings>('/api/settings/language')
  return data
}

export async function updateLanguageSettings(payload: LanguageSettings) {
  const { data } = await api.put<LanguageSettings>('/api/settings/language', payload)
  return data
}

export async function updateReview(reviewId: string, payload: { status: string; reviewer_name?: string; reviewer_note?: string; final_marking_override?: string }) {
  const { data } = await api.put<ReviewRecord>(`/api/reviews/${reviewId}`, payload)
  return data
}

// â”€â”€ Client Profile API â”€â”€

export async function fetchClients() {
  const { data } = await api.get<ClientProfile[]>('/api/clients')
  return data
}

export async function fetchClient(clientId: string) {
  const { data } = await api.get<ClientProfile>(`/api/clients/${clientId}`)
  return data
}

export async function createClient(payload: ClientProfileCreate) {
  const { data } = await api.post<ClientProfile>('/api/clients', payload)
  return data
}

export async function updateClient(clientId: string, payload: Partial<ClientProfileCreate>) {
  const { data } = await api.put<ClientProfile>(`/api/clients/${clientId}`, payload)
  return data
}

export async function deleteClient(clientId: string) {
  await api.delete(`/api/clients/${clientId}`)
}

// — Artifacts —

export function getArtifactDownloadUrl(documentId: string): string {
  return `/api/documents/${documentId}/artifact/download`
}

export function getOriginalDownloadUrl(documentId: string): string {
  return `/api/documents/${documentId}/artifact/original`
}
