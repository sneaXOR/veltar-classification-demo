from __future__ import annotations

import logging
import uuid as uuid_module
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import inspect
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import NO_VALUE

from app.core.config import get_settings
from app.db.session import get_db
from app.models import AuditEvent, Batch, ClassificationJob, ClassificationResult, Document
from app.models.enums import AuditEventType, BatchStatus, DocumentKind, DocumentStatus, JobStatus
from app.schemas.api import BatchSubmissionResponse, ClassificationResponse, DocumentListItem, DocumentSubmissionResponse
from app.services.classification.golden_documents import is_golden_document_sha256
from app.services.classification.job_runner import build_job_progress_snapshot, extract_job_progress
from app.services.classification.orchestrator import ClassificationOrchestrator
from app.services.classification.queue import build_gate_report, build_queue_state, enqueue_classification_job
from app.services.classification.runtime_config import get_active_runtime_profile
from app.services.storage.file_manager import FileManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])
batch_router = APIRouter(prefix="/batches", tags=["batches"])


def _classification_page_payloads(classification: ClassificationResult) -> list[dict]:
    payloads: list[dict] = []
    for page_classification in getattr(classification, "page_classifications", []) or []:
        step_payload = getattr(page_classification, "step_payload", None) or {}
        payload = dict(step_payload) if isinstance(step_payload, dict) else {}
        payload.setdefault("page_number", getattr(page_classification, "page_number", 0))
        payload.setdefault("relevant", getattr(page_classification, "relevant", False))
        payload.setdefault("content_signals", {})
        payload.setdefault("tangible_hints", [])
        payloads.append(payload)
    return payloads


def _queued_gate_report() -> dict:
    now = datetime.now(timezone.utc)
    return build_gate_report(
        queue_state=build_queue_state(state="queued", enqueued_at=now, heartbeat_at=now),
        progress=build_job_progress_snapshot(stage="queued"),
    )


def _parse_client_profile_id(raw: str | None) -> UUID | None:
    if not raw:
        return None
    try:
        return uuid_module.UUID(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"client_profile_id invalide: {raw}") from exc


def _assert_runtime_profile_ready(runtime_profile) -> None:
    profile_base_url = str(getattr(runtime_profile, "base_url", "") or "").lower()
    api_key_configured = bool(getattr(runtime_profile, "api_key_configured", False))
    if "openrouter.ai" in profile_base_url and not api_key_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "Le runtime LLM actif n'est pas configure pour OpenRouter. "
                "Renseignez OPENROUTER_API_KEY ou LLM_API_KEY dans compose.env, "
                "puis redemarrez la stack."
            ),
        )


def _normalize_relative_path(raw: str | None) -> str | None:
    if raw is None:
        return None

    normalized = str(raw).strip().replace("\\", "/")
    if not normalized:
        return None

    parts: list[str] = []
    for part in PurePosixPath(normalized).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise HTTPException(status_code=400, detail=f"relative_path invalide: {raw}")
        parts.append(part)

    if not parts:
        return None

    candidate = "/".join(parts)
    if candidate.startswith("/") or ":" in candidate:
        raise HTTPException(status_code=400, detail=f"relative_path invalide: {raw}")
    return candidate


def _latest_job(document: Document) -> ClassificationJob | None:
    loaded_jobs = inspect(document).attrs.jobs.loaded_value
    if loaded_jobs is NO_VALUE:
        return None
    return max(loaded_jobs, key=lambda job: job.created_at, default=None)


def _document_list_item(document: Document, *, latest_job: ClassificationJob | None = None) -> DocumentListItem:
    latest_job = latest_job or _latest_job(document)
    loaded_classification = inspect(document).attrs.classification.loaded_value
    classification = None if loaded_classification is NO_VALUE else loaded_classification
    if classification is None:
        review = None
    else:
        loaded_review = inspect(classification).attrs.review.loaded_value
        review = None if loaded_review is NO_VALUE else loaded_review

    return DocumentListItem(
        id=document.id,
        batch_id=document.batch_id,
        client_profile_id=document.client_profile_id,
        original_filename=document.original_filename,
        relative_path=document.relative_path,
        media_type=document.media_type,
        kind=document.kind,
        status=document.status,
        page_count=document.page_count,
        duration_ms=latest_job.duration_ms if latest_job else None,
        context_hint=document.context_hint,
        processing_error=document.processing_error,
        artifact_status=document.artifact_status,
        artifact_available=bool(document.artifact_status.value == "ready" and document.marked_artifact_path),
        latest_job_id=latest_job.id if latest_job else None,
        latest_job_status=latest_job.status if latest_job else None,
        latest_job_error=latest_job.error_message if latest_job else None,
        final_marking=classification.final_marking if classification else None,
        final_confidence=classification.final_confidence if classification else None,
        experimental=classification.experimental if classification else None,
        requires_human_review=classification.requires_human_review if classification else None,
        review_status=review.status if review else None,
        review_priority=classification.review_priority if classification else None,
        progress=extract_job_progress(latest_job.gate_report) if latest_job else None,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post("", response_model=DocumentSubmissionResponse)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    context_hint: Annotated[str | None, Form()] = None,
    client_profile_id: Annotated[str | None, Form()] = None,
    db: AsyncSession = Depends(get_db),
) -> DocumentSubmissionResponse:
    parsed_client_id = _parse_client_profile_id(client_profile_id)
    runtime_profile = get_active_runtime_profile()

    document_id = uuid4()
    try:
        saved = await FileManager().save_upload(file, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Upload failed for %s", file.filename)
        raise HTTPException(status_code=500, detail="Echec de l'enregistrement du fichier.")

    if not is_golden_document_sha256(saved.sha256):
        _assert_runtime_profile_ready(runtime_profile)

    document = Document(
        id=document_id,
        original_filename=saved.original_filename,
        stored_filename=saved.stored_filename,
        media_type=saved.media_type,
        kind=DocumentKind.UNKNOWN,
        status=DocumentStatus.UPLOADED,
        source_path=saved.source_path,
        sha256=saved.sha256,
        context_hint=context_hint,
        client_profile_id=parsed_client_id,
    )
    db.add(document)
    await db.flush()

    job = ClassificationJob(
        document_id=document_id,
        status=JobStatus.QUEUED,
        model_name=runtime_profile.model_name,
        runtime_name=runtime_profile.runtime_name,
        gate_report=_queued_gate_report(),
    )
    db.add(job)
    db.add(
        AuditEvent(
            document_id=document_id,
            event_type=AuditEventType.DOCUMENT_UPLOADED,
            payload={"filename": saved.original_filename},
            message=f"Uploaded {saved.original_filename}",
        )
    )
    await db.commit()
    await db.refresh(document)
    await db.refresh(job)
    await enqueue_classification_job(job.id)
    return DocumentSubmissionResponse(document=_document_list_item(document, latest_job=job), job=job)


@router.get("", response_model=list[DocumentListItem])
async def list_documents(db: AsyncSession = Depends(get_db)) -> list[DocumentListItem]:
    result = await db.scalars(
        select(Document)
        .options(
            selectinload(Document.classification).selectinload(ClassificationResult.review),
            selectinload(Document.jobs),
        )
        .order_by(desc(Document.created_at))
    )
    return [_document_list_item(document) for document in result]


@router.get("/{document_id}/classification", response_model=ClassificationResponse)
async def get_document_classification(document_id: UUID, db: AsyncSession = Depends(get_db)) -> ClassificationResult:
    classification = await db.scalar(
        select(ClassificationResult)
        .where(ClassificationResult.document_id == document_id)
        .options(selectinload(ClassificationResult.page_classifications), selectinload(ClassificationResult.review))
    )
    if not classification:
        raise HTTPException(status_code=404, detail="Classification not found.")
    classification.reasoning_summary = ClassificationOrchestrator.render_reasoning_summary_v2(
        classification.reasoning_summary,
        final_marking=classification.final_marking,
        final_confidence=classification.final_confidence,
        requires_review=classification.requires_human_review,
        step_results=classification.step_results or {},
        tangible_description=classification.tangible_description,
        lifecycle_phase=classification.lifecycle_phase,
        page_payloads=_classification_page_payloads(classification),
    )
    return classification


@batch_router.post("", response_model=BatchSubmissionResponse)
async def upload_batch(
    files: Annotated[list[UploadFile], File(...)],
    batch_name: Annotated[str | None, Form()] = None,
    relative_paths: Annotated[list[str] | None, Form()] = None,
    client_profile_id: Annotated[str | None, Form()] = None,
    db: AsyncSession = Depends(get_db),
) -> BatchSubmissionResponse:
    settings = get_settings()
    runtime_profile = get_active_runtime_profile()
    runtime_profile_error: HTTPException | None = None
    try:
        _assert_runtime_profile_ready(runtime_profile)
    except HTTPException as exc:
        runtime_profile_error = exc

    if len(files) > settings.max_batch_documents:
        raise HTTPException(status_code=400, detail=f"Batch size exceeds maximum of {settings.max_batch_documents}.")

    parsed_client_id = _parse_client_profile_id(client_profile_id)
    normalized_relative_paths = [_normalize_relative_path(item) for item in (relative_paths or [])]
    if normalized_relative_paths and len(normalized_relative_paths) != len(files):
        raise HTTPException(status_code=400, detail="Nombre de relative_paths incoherent avec les fichiers envoyes.")
    batch = Batch(name=batch_name or "Batch Classification", status=BatchStatus.PENDING, total_documents=len(files))
    db.add(batch)
    await db.flush()

    jobs: list[ClassificationJob] = []
    skipped: list[str] = []
    file_manager = FileManager()

    for index, upload in enumerate(files):
        document_id = uuid4()
        relative_path = normalized_relative_paths[index] if index < len(normalized_relative_paths) else None
        try:
            saved = await file_manager.save_upload(upload, document_id)
        except ValueError as exc:
            logger.warning("Skipping file %s in batch: %s", upload.filename, exc)
            skipped.append(f"{upload.filename}: {exc}")
            continue
        except Exception:
            logger.exception("Skipping file %s in batch due to error", upload.filename)
            skipped.append(f"{upload.filename}: erreur interne")
            continue

        if runtime_profile_error is not None and not is_golden_document_sha256(saved.sha256):
            skipped.append(f"{upload.filename}: {runtime_profile_error.detail}")
            continue

        document = Document(
            id=document_id,
            batch_id=batch.id,
            client_profile_id=parsed_client_id,
            original_filename=saved.original_filename,
            stored_filename=saved.stored_filename,
            media_type=saved.media_type,
            relative_path=relative_path,
            kind=DocumentKind.UNKNOWN,
            status=DocumentStatus.UPLOADED,
            source_path=saved.source_path,
            sha256=saved.sha256,
        )
        db.add(document)
        await db.flush()

        job = ClassificationJob(
            document_id=document_id,
            status=JobStatus.QUEUED,
            model_name=runtime_profile.model_name,
            runtime_name=runtime_profile.runtime_name,
            gate_report=_queued_gate_report(),
        )
        db.add(job)
        jobs.append(job)

    if not jobs:
        if runtime_profile_error is not None:
            raise HTTPException(status_code=runtime_profile_error.status_code, detail=runtime_profile_error.detail)
        detail = "Aucun fichier valide dans le batch."
        if skipped:
            detail = f"{detail} Erreurs: {'; '.join(skipped)}"
        raise HTTPException(status_code=400, detail=detail)

    batch.total_documents = len(jobs)
    await db.commit()
    await db.refresh(batch)
    for job in jobs:
        await db.refresh(job)
        await enqueue_classification_job(job.id)
    return BatchSubmissionResponse(batch=batch, jobs=jobs)
