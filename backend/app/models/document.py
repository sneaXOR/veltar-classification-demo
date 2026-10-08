from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import ArtifactStatus, DocumentKind, DocumentStatus, PageContentType

ARTIFACT_STATUS_ENUM = Enum(
    ArtifactStatus,
    values_callable=lambda enum: [item.value for item in enum],
    native_enum=False,
)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("batches.id"), nullable=True)
    client_profile_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("client_profiles.id"), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    kind: Mapped[DocumentKind] = mapped_column(Enum(DocumentKind), default=DocumentKind.UNKNOWN, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED, nullable=False)
    artifact_status: Mapped[ArtifactStatus] = mapped_column(ARTIFACT_STATUS_ENUM, default=ArtifactStatus.NONE, nullable=False)
    artifact_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_snapshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    marked_artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    marking_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    context_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch = relationship("Batch", back_populates="documents")
    client_profile = relationship("ClientProfile", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_number")
    jobs = relationship("ClassificationJob", back_populates="document", cascade="all, delete-orphan")
    classification = relationship("ClassificationResult", back_populates="document", uselist=False, cascade="all, delete-orphan")
    artifacts = relationship("DocumentArtifactRevision", back_populates="document", cascade="all, delete-orphan", order_by="DocumentArtifactRevision.revision")


class DocumentPage(Base, TimestampMixin):
    __tablename__ = "document_pages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[PageContentType] = mapped_column(Enum(PageContentType), nullable=False)
    section_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    document = relationship("Document", back_populates="pages")
    page_classification = relationship("PageClassification", back_populates="page", uselist=False, cascade="all, delete-orphan")
