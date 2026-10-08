from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import JobStatus, LaneType, ReviewPriority, ReviewStatus


class ClassificationJob(Base, TimestampMixin):
    __tablename__ = "classification_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED, nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    runtime_name: Mapped[str] = mapped_column(String(255), default="openai-compatible", nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    gate_report: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    document = relationship("Document", back_populates="jobs")
    classification = relationship("ClassificationResult", back_populates="job", uselist=False, cascade="all, delete-orphan")


class ClassificationResult(Base, TimestampMixin):
    __tablename__ = "classification_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id"), unique=True, nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("classification_jobs.id"), unique=True, nullable=False)
    lane: Mapped[LaneType] = mapped_column(Enum(LaneType), nullable=False, default=LaneType.FR_EU)
    final_marking: Mapped[str] = mapped_column(String(255), nullable=False)
    final_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    experimental: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    insufficient_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    review_priority: Mapped[ReviewPriority] = mapped_column(Enum(ReviewPriority), default=ReviewPriority.MEDIUM, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False)
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_markings: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    citations: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    evidence_items: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    page_rollup: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    step_results: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    veltar_projection: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(10), default="v1", nullable=False)
    lifecycle_phase: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tangible_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tangible_category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    document = relationship("Document", back_populates="classification")
    job = relationship("ClassificationJob", back_populates="classification")
    page_classifications = relationship("PageClassification", back_populates="classification_result", cascade="all, delete-orphan")
    review = relationship("ReviewRecord", back_populates="classification_result", uselist=False, cascade="all, delete-orphan")


class PageClassification(Base, TimestampMixin):
    __tablename__ = "page_classifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    classification_result_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("classification_results.id"), nullable=False)
    page_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("document_pages.id"), nullable=False, unique=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    relevant: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    technical_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    citations: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    step_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    classification_result = relationship("ClassificationResult", back_populates="page_classifications")
    page = relationship("DocumentPage", back_populates="page_classification")


class ReviewRecord(Base, TimestampMixin):
    __tablename__ = "review_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    classification_result_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("classification_results.id"), unique=True, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False)
    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_marking_override: Mapped[str | None] = mapped_column(String(255), nullable=True)

    classification_result = relationship("ClassificationResult", back_populates="review")
