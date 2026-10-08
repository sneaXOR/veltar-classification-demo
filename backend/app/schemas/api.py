from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ArtifactStatus, BatchStatus, DocumentKind, DocumentStatus, JobStatus, ReviewPriority, ReviewStatus


COUNTRY_CODE_PATTERN = re.compile(r"^[A-Za-z]{2}$")


def _normalize_country_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if not COUNTRY_CODE_PATTERN.fullmatch(normalized):
        raise ValueError("country must be a 2-letter ISO code")
    return normalized


class ClientProfileCreate(BaseModel):
    name: str
    country: str
    activity_description: str | None = None
    product_families: list[str] = Field(default_factory=list)
    product_characteristics: dict[str, Any] = Field(default_factory=dict)
    program_names: list[str] = Field(default_factory=list)
    naming_conventions: dict[str, Any] = Field(default_factory=dict)
    classification_history: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str) -> str:
        normalized = _normalize_country_code(value)
        assert normalized is not None
        return normalized


class ClientProfileUpdate(BaseModel):
    name: str | None = None
    country: str | None = None
    activity_description: str | None = None
    product_families: list[str] | None = None
    product_characteristics: dict[str, Any] | None = None
    program_names: list[str] | None = None
    naming_conventions: dict[str, Any] | None = None
    classification_history: list[dict[str, Any]] | None = None

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str | None) -> str | None:
        return _normalize_country_code(value)


class ClientProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    country: str
    activity_description: str | None
    product_families: list[Any]
    product_characteristics: dict[str, Any]
    program_names: list[Any]
    naming_conventions: dict[str, Any]
    classification_history: list[Any]
    regulatory_scope: list[Any]
    created_at: datetime
    updated_at: datetime


class JobProgressResponse(BaseModel):
    stage: str
    stage_label: str
    message: str
    percent: int | None = None
    processed_pages: int | None = None
    total_pages: int | None = None
    current_page: int | None = None


class PageClassificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    relevant: bool
    technical_score: int
    confidence: float
    summary: str
    evidence: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    step_payload: dict[str, Any]


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ReviewStatus
    reviewer_name: str | None
    reviewer_note: str | None
    final_marking_override: str | None
    created_at: datetime
    updated_at: datetime


class ClassificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    job_id: UUID
    lane: str
    final_marking: str
    final_confidence: float
    experimental: bool
    insufficient_evidence: bool
    requires_human_review: bool
    review_priority: ReviewPriority
    jurisdiction: str
    reasoning_summary: str
    candidate_markings: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    evidence_items: list[dict[str, Any]]
    page_rollup: dict[str, Any]
    step_results: dict[str, Any]
    veltar_projection: dict[str, Any]
    pipeline_version: str = "v1"
    lifecycle_phase: str | None = None
    tangible_description: str | None = None
    tangible_category: str | None = None
    page_classifications: list[PageClassificationResponse] = Field(default_factory=list)
    review: ReviewResponse | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID | None
    client_profile_id: UUID | None = None
    original_filename: str
    relative_path: str | None = None
    media_type: str
    kind: DocumentKind
    status: DocumentStatus
    page_count: int
    duration_ms: int | None = None
    context_hint: str | None
    processing_error: str | None
    artifact_status: ArtifactStatus = ArtifactStatus.NONE
    artifact_available: bool = False
    latest_job_id: UUID | None = None
    latest_job_status: JobStatus | None = None
    latest_job_error: str | None = None
    final_marking: str | None = None
    final_confidence: float | None = None
    experimental: bool | None = None
    requires_human_review: bool | None = None
    review_status: ReviewStatus | None = None
    review_priority: ReviewPriority | None = None
    progress: JobProgressResponse | None = None
    created_at: datetime
    updated_at: datetime


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    status: JobStatus
    model_name: str
    runtime_name: str
    duration_ms: int | None
    error_message: str | None
    gate_report: dict[str, Any]
    progress: JobProgressResponse | None = None
    created_at: datetime
    updated_at: datetime


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: BatchStatus
    total_documents: int
    completed_documents: int
    failed_documents: int
    created_at: datetime
    updated_at: datetime


class DocumentSubmissionResponse(BaseModel):
    document: DocumentListItem
    job: JobResponse


class BatchSubmissionResponse(BaseModel):
    batch: BatchResponse
    jobs: list[JobResponse]


class LLMRuntimeProfileResponse(BaseModel):
    id: str
    label: str
    description: str
    runtime_name: str
    model_name: str
    base_url: str
    image_transport: str
    verify_ssl: bool
    step2_visual_thinking: bool
    timeout_seconds: int
    max_tokens: int
    local: bool
    api_key_configured: bool


class LLMRuntimeSettingsResponse(BaseModel):
    active_profile_id: str
    active_profile: LLMRuntimeProfileResponse
    available_profiles: list[LLMRuntimeProfileResponse]


class LLMRuntimeUpdateRequest(BaseModel):
    profile_id: str


class LanguageSettingsResponse(BaseModel):
    ui_language: str
    analysis_language: str
    rationale_language: str


class LanguageSettingsUpdateRequest(BaseModel):
    ui_language: str
    analysis_language: str
    rationale_language: str


class ReviewUpdateRequest(BaseModel):
    status: ReviewStatus
    reviewer_name: str | None = None
    reviewer_note: str | None = None
    final_marking_override: str | None = None


class DashboardResponse(BaseModel):
    total_documents: int
    completed_documents: int
    pending_reviews: int
    failed_jobs: int
    batches: int
    by_marking: dict[str, int]
    by_status: dict[str, int]


class DocumentArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ArtifactStatus
    version: int
    has_original_snapshot: bool
    has_marked_revision: bool
    download_url: str | None = None
    batch_download_url: str | None = None
    relative_path: str | None = None


class DocumentDecisionResponse(BaseModel):
    final_marking: str | None = None
    final_confidence: float | None = None
    requires_human_review: bool | None = None
    review_priority: ReviewPriority | None = None
    lane: str | None = None
    jurisdiction: str | None = None
    pipeline_version: str | None = None
    lifecycle_phase: str | None = None
    tangible_description: str | None = None
    tangible_category: str | None = None


class DocumentProofResponse(BaseModel):
    reasoning_summary: str | None = None
    candidate_markings: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)


class DocumentAuditResponse(BaseModel):
    document_id: UUID
    classification_id: UUID | None = None
    job_id: UUID | None = None
    latest_job_status: JobStatus | None = None
    latest_job_error: str | None = None
    review_status: ReviewStatus | None = None
    reviewer_name: str | None = None
    reviewer_note: str | None = None
    pipeline_version: str | None = None
    processing_error: str | None = None
    artifact_status: ArtifactStatus = ArtifactStatus.NONE
    artifact_error: str | None = None


class DocumentTimingResponse(BaseModel):
    queue_ms: int | None = None
    ingestion_ms: int | None = None
    page_scan_ms: int | None = None
    decision_ms: int | None = None
    analysis_ms: int | None = None
    marking_ms: int | None = None
    total_ms: int | None = None


class DocumentRelevantUnitResponse(BaseModel):
    page_number: int
    section_label: str | None = None
    content_type: str | None = None
    relevant: bool
    technical_score: int
    confidence: float
    summary: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class DocumentViewResponse(BaseModel):
    state: str
    message: str | None = None
    document: DocumentListItem
    decision: DocumentDecisionResponse | None = None
    proofs: DocumentProofResponse | None = None
    audit: DocumentAuditResponse
    timings: DocumentTimingResponse | None = None
    artifacts: DocumentArtifactResponse
    relevant_units: list[DocumentRelevantUnitResponse] = Field(default_factory=list)
