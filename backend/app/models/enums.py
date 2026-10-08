from __future__ import annotations

import enum


class BatchStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    INGESTING = "ingesting"
    READY = "ready"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactStatus(str, enum.Enum):
    NONE = "none"
    READY = "ready"
    FAILED = "failed"


class ArtifactRevisionKind(str, enum.Enum):
    ORIGINAL_SNAPSHOT = "original_snapshot"
    MARKED_REVISION = "marked_revision"


class DocumentKind(str, enum.Enum):
    PDF = "pdf"
    IMAGE = "image"
    OFFICE = "office"
    EMAIL = "email"
    TEXT = "text"
    UNKNOWN = "unknown"


class PageContentType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    HYBRID = "hybrid"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INFO = "needs_info"


class ReviewPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LaneType(str, enum.Enum):
    FR_EU = "fr_eu"
    US = "us"


class AuditEventType(str, enum.Enum):
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_MARKED = "document_marked"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    REVIEW_UPDATED = "review_updated"
