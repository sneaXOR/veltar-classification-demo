from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import AuditEvent, Batch, ClassificationJob, ClassificationResult, ClientProfile, Document, DocumentPage, PageClassification, ReviewRecord
from app.models.enums import AuditEventType, BatchStatus, DocumentStatus, JobStatus, ReviewStatus
from app.services.classification.orchestrator import ClassificationOrchestrator
from app.services.classification.llm_client import LLMClient
from app.services.classification.queue import (
    QUEUE_STATE_KEY,
    TIMINGS_KEY,
    build_queue_state,
    enqueue_classification_job,
    extract_queue_state,
    extract_timings,
    get_worker_identity,
    parse_gate_datetime,
)
from app.services.language_settings import get_ui_language, resolve_text
from app.services.document_artifacts import build_and_persist_document_artifact, persist_document_artifact_revision
from app.services.ingestion.dispatcher import detect_kind, extract_supported_file
from app.services.ingestion.types import sanitize_text_for_storage
from app.services.storage.file_manager import FileManager

PROGRESS_KEY = "progress"

_CRITICAL_STEP_LABELS = {
    "step_b": "l'identification du tangible",
    "step_c": "l'analyse militaire",
    "step_d": "la qualification ML22 de la donnee",
    "step_e": "l'analyse double usage",
    "step_f": "la qualification Nature E / technologie",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _merge_gate_report(job: ClassificationJob, **updates: Any) -> dict[str, Any]:
    gate_report = dict(job.gate_report or {})
    gate_report.update({key: value for key, value in updates.items() if value is not None})
    job.gate_report = gate_report
    return gate_report


def _set_gate_report_section(job: ClassificationJob, key: str, value: dict[str, Any]) -> dict[str, Any]:
    gate_report = dict(job.gate_report or {})
    gate_report[key] = value
    job.gate_report = gate_report
    return gate_report


def build_job_progress_snapshot(
    *,
    stage: str,
    message: str | None = None,
    percent: int | None = None,
    processed_pages: int | None = None,
    total_pages: int | None = None,
    current_page: int | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "stage_label": _get_stage_label(stage),
        "message": message or _build_progress_message(stage, current_page=current_page, total_pages=total_pages),
        "percent": percent if percent is not None else _compute_progress_percent(stage, processed_pages=processed_pages, total_pages=total_pages),
        "processed_pages": processed_pages,
        "total_pages": total_pages,
        "current_page": current_page,
    }


def extract_job_progress(gate_report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(gate_report, dict):
        return None
    progress = gate_report.get(PROGRESS_KEY)
    return progress if isinstance(progress, dict) else None


def _compute_progress_percent(stage: str, *, processed_pages: int | None, total_pages: int | None) -> int | None:
    if stage == "queued":
        return 0
    if stage == "ingesting":
        return 5
    if stage == "finalizing":
        return 95
    if stage == "completed":
        return 100
    if stage == "failed":
        if total_pages and processed_pages is not None:
            return max(8, min(95, round((processed_pages / total_pages) * 90)))
        return None
    if stage == "processing":
        if total_pages and processed_pages is not None:
            return max(8, min(90, round((processed_pages / total_pages) * 90)))
        return 15
    return None


def _get_stage_label(stage: str) -> str:
    language = get_ui_language()
    labels = {
        "queued": resolve_text(english="Queued", french="En attente", language=language),
        "ingesting": resolve_text(english="Preparing", french="Preparation", language=language),
        "processing": resolve_text(english="Analyzing", french="Analyse", language=language),
        "finalizing": resolve_text(english="Finalizing", french="Finalisation", language=language),
        "completed": resolve_text(english="Completed", french="Termine", language=language),
        "failed": resolve_text(english="Error", french="Erreur", language=language),
    }
    return labels.get(stage, resolve_text(english="Analyzing", french="Analyse", language=language))


def _build_progress_message(stage: str, *, current_page: int | None, total_pages: int | None) -> str:
    language = get_ui_language()
    if stage == "queued":
        return resolve_text(english="Waiting for processing", french="En attente de traitement", language=language)
    if stage == "ingesting":
        return resolve_text(english="Preparing document", french="Preparation du document", language=language)
    if stage == "processing" and current_page and total_pages:
        return resolve_text(
            english=f"Analyzing page {current_page} of {total_pages}",
            french=f"Analyse de la page {current_page} sur {total_pages}",
            language=language,
        )
    if stage == "processing":
        return resolve_text(english="Analyzing document", french="Analyse du document", language=language)
    if stage == "finalizing":
        return resolve_text(english="Finalizing document analysis", french="Analyse finale du document", language=language)
    if stage == "completed":
        return resolve_text(english="Analysis completed", french="Analyse terminee", language=language)
    if stage == "failed":
        return resolve_text(english="Analysis failed", french="Analyse interrompue", language=language)
    return resolve_text(english="Analyzing document", french="Analyse du document", language=language)


def _set_job_progress(
    job: ClassificationJob,
    *,
    stage: str,
    message: str | None = None,
    percent: int | None = None,
    processed_pages: int | None = None,
    total_pages: int | None = None,
    current_page: int | None = None,
) -> dict[str, Any]:
    snapshot = build_job_progress_snapshot(
        stage=stage,
        message=message,
        percent=percent,
        processed_pages=processed_pages,
        total_pages=total_pages,
        current_page=current_page,
    )
    gate_report = dict(job.gate_report or {})
    gate_report[PROGRESS_KEY] = snapshot
    job.gate_report = gate_report
    return snapshot


def _set_queue_state(
    job: ClassificationJob,
    *,
    state: str,
    enqueued_at: datetime | None = None,
    started_at: datetime | None = None,
    heartbeat_at: datetime | None = None,
    lease_until: datetime | None = None,
    attempts: int | None = None,
    worker_id: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    queue_state = build_queue_state(
        state=state,
        enqueued_at=enqueued_at,
        started_at=started_at,
        heartbeat_at=heartbeat_at,
        lease_until=lease_until,
        attempts=attempts or 0,
        worker_id=worker_id,
        error_message=error_message,
    )
    return _set_gate_report_section(job, QUEUE_STATE_KEY, queue_state)


def _set_job_timings(job: ClassificationJob, timings: dict[str, Any]) -> dict[str, Any]:
    gate_report = dict(job.gate_report or {})
    existing = dict(gate_report.get(TIMINGS_KEY) or {})
    existing.update({key: value for key, value in timings.items() if value is not None})
    gate_report[TIMINGS_KEY] = existing
    job.gate_report = gate_report
    return existing


def _queue_wait_ms(job: ClassificationJob) -> int | None:
    queue_state = extract_queue_state(job.gate_report)
    if not queue_state:
        return None
    enqueued_at = parse_gate_datetime(queue_state.get("enqueued_at"))
    if not enqueued_at:
        return None
    return int(max(0, (_utcnow() - enqueued_at).total_seconds() * 1000))


def _queue_is_stale(job: ClassificationJob, *, lease_seconds: int) -> bool:
    queue_state = extract_queue_state(job.gate_report)
    if not queue_state:
        return True
    lease_until = parse_gate_datetime(queue_state.get("lease_until"))
    if lease_until is None:
        started_at = parse_gate_datetime(queue_state.get("started_at"))
        if started_at is None:
            return True
        return (_utcnow() - started_at) > timedelta(seconds=lease_seconds)
    return lease_until <= _utcnow()


def _critical_llm_failure_message(result_payload: dict[str, Any]) -> str | None:
    for page_payload in result_payload.get("page_payloads") or []:
        if not isinstance(page_payload, dict) or not page_payload.get("_llm_failed"):
            continue
        page_number = page_payload.get("page_number")
        page_label = f"page {page_number}" if page_number else "une page"
        error_detail = page_payload.get("_llm_error") or "LLM page scan failed"
        return f"Echec LLM critique pendant l'analyse de {page_label}: {error_detail}"

    for step_name, payload in (result_payload.get("step_results") or {}).items():
        if step_name == "step_timing" or not isinstance(payload, dict) or not payload.get("_llm_failed"):
            continue
        label = _CRITICAL_STEP_LABELS.get(step_name, step_name)
        error_detail = payload.get("_llm_error") or "LLM step failed"
        return f"Echec LLM critique pendant {label}: {error_detail}"

    return None


def _should_raise_for_critical_llm_failure(result_payload: dict[str, Any], critical_message: str | None) -> bool:
    if not critical_message:
        return False
    degraded_to_review = bool(result_payload.get("final_marking")) and bool(result_payload.get("requires_human_review"))
    return not degraded_to_review


async def process_job(job_id: UUID, *, worker_id: str | None = None) -> None:
    started_at = time.perf_counter()
    worker_id = worker_id or get_worker_identity()
    file_manager = FileManager()
    lease_seconds = get_settings().job_lease_seconds

    async with AsyncSessionLocal() as session:
        job = await _load_job(session, job_id, for_update=True)
        if not job:
            return

        queue_state = extract_queue_state(job.gate_report)
        now = _utcnow()
        if job.status == JobStatus.COMPLETED or job.status == JobStatus.FAILED:
            return
        if job.status == JobStatus.RUNNING and queue_state and not _queue_is_stale(job, lease_seconds=lease_seconds):
            return

        enqueued_at = parse_gate_datetime(queue_state.get("enqueued_at")) if queue_state else None
        attempts = int((queue_state or {}).get("attempts") or 0) + 1
        _set_queue_state(
            job,
            state="running",
            enqueued_at=enqueued_at or now,
            started_at=now,
            heartbeat_at=now,
            lease_until=now + timedelta(seconds=lease_seconds),
            attempts=attempts,
            worker_id=worker_id,
        )
        job.status = JobStatus.RUNNING
        job.error_message = None
        document = job.document
        document.status = DocumentStatus.INGESTING
        _set_job_progress(job, stage="ingesting")
        queue_wait_ms = _queue_wait_ms(job)
        if queue_wait_ms is not None:
            _set_job_timings(job, {"queue_wait_ms": queue_wait_ms})
        session.add(
            AuditEvent(
                document_id=document.id,
                event_type=AuditEventType.JOB_STARTED,
                payload={"job_id": str(job.id), "worker_id": worker_id},
                message=f"Started processing {document.original_filename}",
            )
        )
        await session.commit()

    try:
        async with AsyncSessionLocal() as session:
            job = await _load_job(session, job_id)
            if not job:
                return
            document = job.document
            ingestion_started = time.perf_counter()
            await _ingest_document(session, document, file_manager)
            ingestion_ms = int((time.perf_counter() - ingestion_started) * 1000)
            _set_job_timings(job, {"ingestion_ms": ingestion_ms})
            document.status = DocumentStatus.PROCESSING
            _set_job_progress(
                job,
                stage="processing",
                processed_pages=0,
                total_pages=document.page_count,
                current_page=None,
            )
            await session.commit()

            progress_lock = asyncio.Lock()

            async def progress_callback(processed_pages: int, total_pages: int) -> None:
                async with progress_lock:
                    now = _utcnow()
                    queue_state = extract_queue_state(job.gate_report) or {}
                    _set_queue_state(
                        job,
                        state="running",
                        enqueued_at=parse_gate_datetime(queue_state.get("enqueued_at")) or now,
                        started_at=parse_gate_datetime(queue_state.get("started_at")) or now,
                        heartbeat_at=now,
                        lease_until=now + timedelta(seconds=lease_seconds),
                        attempts=int(queue_state.get("attempts") or 0),
                        worker_id=queue_state.get("worker_id") or worker_id,
                    )
                    if total_pages and processed_pages >= total_pages:
                        _set_job_progress(
                            job,
                            stage="finalizing",
                            processed_pages=processed_pages,
                            total_pages=total_pages,
                            current_page=total_pages,
                        )
                    else:
                        _set_job_progress(
                            job,
                            stage="processing",
                            processed_pages=processed_pages,
                            total_pages=total_pages,
                            current_page=None,
                        )
                    await session.commit()

            orchestrator = ClassificationOrchestrator(llm_client=LLMClient(profile_id=job.runtime_name))
            client_profile = document.client_profile if document.client_profile_id else None
            analysis_started = time.perf_counter()
            result_payload = await orchestrator.classify_document(
                document,
                document.pages,
                client_profile=client_profile,
                progress_callback=progress_callback,
            )
            analysis_ms = int((time.perf_counter() - analysis_started) * 1000)
            critical_llm_failure = _critical_llm_failure_message(result_payload)
            if _should_raise_for_critical_llm_failure(result_payload, critical_llm_failure):
                raise RuntimeError(critical_llm_failure)
            classification = await _persist_classification(session, document, job, result_payload)

            # Build and persist the marked document artifact
            artifact_result = await build_and_persist_document_artifact(
                document=document,
                classification=classification,
                file_manager=file_manager,
                page_classifications=result_payload.get("page_payloads", []),
            )
            persist_document_artifact_revision(
                session=session,
                document=document,
                artifact_result=artifact_result,
            )

            phase_timings = dict(result_payload.get("phase_timings") or {})
            decision_ms = phase_timings.get("decision_ms")
            page_scan_ms = phase_timings.get("page_scan_ms")
            total_analysis_ms = phase_timings.get("analysis_ms") or analysis_ms
            marking_ms = artifact_result.duration_ms
            _set_job_timings(
                job,
                {
                    "page_scan_ms": page_scan_ms,
                    "decision_ms": decision_ms,
                    "analysis_ms": total_analysis_ms,
                    "classification_ms": analysis_ms,
                    "marking_ms": marking_ms,
                },
            )
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            job.duration_ms = duration_ms
            job.status = JobStatus.COMPLETED
            document.status = DocumentStatus.COMPLETED
            _set_queue_state(
                job,
                state="completed",
                enqueued_at=parse_gate_datetime((extract_queue_state(job.gate_report) or {}).get("enqueued_at")) or _utcnow(),
                started_at=parse_gate_datetime((extract_queue_state(job.gate_report) or {}).get("started_at")) or _utcnow(),
                heartbeat_at=_utcnow(),
                lease_until=None,
                attempts=int((extract_queue_state(job.gate_report) or {}).get("attempts") or 0),
                worker_id=(extract_queue_state(job.gate_report) or {}).get("worker_id") or worker_id,
            )
            _set_job_progress(
                job,
                stage="completed",
                processed_pages=document.page_count,
                total_pages=document.page_count,
                current_page=document.page_count if document.page_count else None,
            )
            session.add(
                AuditEvent(
                    document_id=document.id,
                    event_type=AuditEventType.DOCUMENT_MARKED,
                    payload={
                        "job_id": str(job.id),
                        "revision": artifact_result.revision,
                        "marking_duration_ms": artifact_result.duration_ms,
                        "artifact_path": artifact_result.current_path,
                    },
                    message=f"Marked {document.original_filename}",
                )
            )
            session.add(
                AuditEvent(
                    document_id=document.id,
                    event_type=AuditEventType.JOB_COMPLETED,
                    payload={
                        "job_id": str(job.id),
                        "duration_ms": duration_ms,
                        "timings": dict(job.gate_report or {}).get(TIMINGS_KEY, {}),
                    },
                    message=f"Completed processing {document.original_filename}",
                )
            )
            await _update_batch_status(session, document.batch_id)
            await session.commit()
    except Exception as exc:  # pragma: no cover
        async with AsyncSessionLocal() as session:
            job = await _load_job(session, job_id)
            if not job:
                return
            document = job.document
            queue_state = extract_queue_state(job.gate_report) or {}
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            document.status = DocumentStatus.FAILED
            document.processing_error = str(exc)
            progress = extract_job_progress(job.gate_report)
            processed_pages = progress.get("processed_pages") if progress else None
            total_pages = progress.get("total_pages") if progress else None
            current_page = progress.get("current_page") if progress else None
            _set_job_progress(
                job,
                stage="failed",
                processed_pages=processed_pages,
                total_pages=total_pages or (document.page_count or None),
                current_page=current_page,
            )
            _set_queue_state(
                job,
                state="failed",
                enqueued_at=parse_gate_datetime(queue_state.get("enqueued_at")) or _utcnow(),
                started_at=parse_gate_datetime(queue_state.get("started_at")) or _utcnow(),
                heartbeat_at=_utcnow(),
                lease_until=None,
                attempts=int(queue_state.get("attempts") or 0),
                worker_id=queue_state.get("worker_id") or worker_id,
                error_message=str(exc),
            )
            _set_job_timings(job, {"failed_ms": int((time.perf_counter() - started_at) * 1000)})
            session.add(
                AuditEvent(
                    document_id=document.id,
                    event_type=AuditEventType.JOB_FAILED,
                    payload={
                        "job_id": str(job.id),
                        "error": str(exc),
                        "timings": dict(job.gate_report or {}).get(TIMINGS_KEY, {}),
                    },
                    message=f"Failed processing {document.original_filename}",
                )
            )
            await _update_batch_status(session, document.batch_id)
            await session.commit()


async def recover_incomplete_jobs(*, requeue_queued: bool = False) -> int:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        jobs = list(
            await session.scalars(
                select(ClassificationJob)
                .where(ClassificationJob.status.in_((JobStatus.QUEUED, JobStatus.RUNNING)))
                .options(selectinload(ClassificationJob.document))
            )
        )

        if not jobs:
            return 0

        now = _utcnow()
        job_ids: list[UUID] = []
        for job in jobs:
            queue_state = extract_queue_state(job.gate_report) or {}
            enqueued_at = parse_gate_datetime(queue_state.get("enqueued_at")) or now
            attempts = int(queue_state.get("attempts") or 0)

            if job.status == JobStatus.QUEUED:
                if not requeue_queued:
                    continue
                job.error_message = None
                job.document.status = DocumentStatus.UPLOADED
                job.document.processing_error = None
                _set_queue_state(
                    job,
                    state="queued",
                    enqueued_at=enqueued_at,
                    heartbeat_at=now,
                    lease_until=None,
                    attempts=attempts,
                    worker_id=None,
                )
                _set_job_progress(job, stage="queued")
                job_ids.append(job.id)
                continue

            if not _queue_is_stale(job, lease_seconds=settings.job_lease_seconds):
                continue

            job.status = JobStatus.QUEUED
            job.error_message = None
            job.document.status = DocumentStatus.UPLOADED
            job.document.processing_error = None
            _set_queue_state(
                job,
                state="queued",
                enqueued_at=enqueued_at,
                heartbeat_at=now,
                lease_until=None,
                attempts=attempts,
                worker_id=None,
            )
            _set_job_progress(job, stage="queued")
            job_ids.append(job.id)

        await session.commit()

    for job_id in job_ids:
        await enqueue_classification_job(job_id)

    return len(job_ids)


async def _load_job(session, job_id: UUID, *, for_update: bool = False) -> ClassificationJob | None:
    statement = (
        select(ClassificationJob)
        .where(ClassificationJob.id == job_id)
        .options(
            selectinload(ClassificationJob.document).selectinload(Document.pages),
            selectinload(ClassificationJob.document).selectinload(Document.classification),
            selectinload(ClassificationJob.document).selectinload(Document.client_profile),
        )
    )
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def _ingest_document(session, document: Document, file_manager: FileManager) -> None:
    await session.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
    ingestion = extract_supported_file(document.source_path, document.id, file_manager, content_type=document.media_type)
    document.kind = detect_kind(document.media_type, document.original_filename) or ingestion.kind
    document.page_count = len(ingestion.pages)
    document.status = DocumentStatus.READY
    for page in ingestion.pages:
        session.add(
            DocumentPage(
                document_id=document.id,
                page_number=page.page_number,
                content_type=page.content_type,
                section_label=sanitize_text_for_storage(page.section_label),
                extracted_text=sanitize_text_for_storage(page.extracted_text),
                image_path=sanitize_text_for_storage(page.image_path),
                width=page.width,
                height=page.height,
                char_count=page.char_count,
            )
        )
    await session.flush()
    await session.refresh(document, attribute_names=["pages"])


async def _persist_classification(session, document: Document, job: ClassificationJob, payload: dict) -> ClassificationResult:
    existing_classification = await session.scalar(
        select(ClassificationResult)
        .where(ClassificationResult.document_id == document.id)
        .options(
            selectinload(ClassificationResult.page_classifications),
            selectinload(ClassificationResult.review),
        )
    )
    if existing_classification:
        await session.delete(existing_classification)
        await session.flush()

    classification = ClassificationResult(
        document_id=document.id,
        job_id=job.id,
        lane=payload["lane"],
        final_marking=payload["final_marking"],
        final_confidence=payload["final_confidence"],
        experimental=payload["experimental"],
        insufficient_evidence=payload["insufficient_evidence"],
        requires_human_review=payload["requires_human_review"],
        review_priority=payload["review_priority"],
        jurisdiction=payload["jurisdiction"],
        reasoning_summary=payload["reasoning_summary"],
        candidate_markings=payload["candidate_markings"],
        citations=payload["citations"],
        evidence_items=payload["evidence_items"],
        page_rollup=payload["page_rollup"],
        step_results=payload["step_results"],
        veltar_projection=payload["veltar_projection"],
        pipeline_version=payload.get("pipeline_version", "v1"),
        lifecycle_phase=payload.get("lifecycle_phase"),
        tangible_description=payload.get("tangible_description"),
        tangible_category=payload.get("tangible_category"),
    )
    session.add(classification)
    await session.flush()

    page_lookup = {
        page.page_number: page
        for page in await session.scalars(
            select(DocumentPage).where(DocumentPage.document_id == document.id)
        )
    }
    for page_payload in payload["page_payloads"]:
        page = page_lookup.get(page_payload["page_number"])
        if not page:
            continue
        session.add(
            PageClassification(
                classification_result_id=classification.id,
                page_id=page.id,
                page_number=page.page_number,
                relevant=page_payload.get("relevant", False),
                technical_score=page_payload.get("technical_score", 0),
                confidence=page_payload.get("confidence", 0.0),
                summary=page_payload.get("page_summary", ""),
                evidence=page_payload.get("evidence", []),
                citations=page_payload.get("citations", []),
                step_payload=page_payload,
            )
        )

    session.add(_build_review_record(classification.id, payload))
    await session.flush()
    return classification


async def _update_batch_status(session, batch_id: UUID | None) -> None:
    """Update batch counters using atomic SQL aggregation (no read-compute-write race)."""
    if not batch_id:
        return

    # Compute counts in a single SQL query, atomic even under concurrent commits.
    stmt = (
        select(
            func.count().label("total"),
            func.sum(case((ClassificationJob.status == JobStatus.COMPLETED, 1), else_=0)).label("completed"),
            func.sum(case((ClassificationJob.status == JobStatus.FAILED, 1), else_=0)).label("failed"),
            func.sum(
                case(
                    (ClassificationJob.status.in_([JobStatus.RUNNING, JobStatus.QUEUED]), 1),
                    else_=0,
                )
            ).label("active"),
        )
        .select_from(ClassificationJob)
        .join(Document, Document.id == ClassificationJob.document_id)
        .where(Document.batch_id == batch_id)
    )
    row = (await session.execute(stmt)).one()

    batch = await session.get(Batch, batch_id)
    if not batch:
        return

    total = int(row.total or 0)
    completed = int(row.completed or 0)
    failed = int(row.failed or 0)
    active = int(row.active or 0)

    batch.total_documents = total
    batch.completed_documents = completed
    batch.failed_documents = failed

    if failed == total and total > 0:
        batch.status = BatchStatus.FAILED
    elif completed == total and total > 0:
        batch.status = BatchStatus.COMPLETED
    elif active > 0:
        batch.status = BatchStatus.RUNNING
    else:
        batch.status = BatchStatus.PENDING


def _build_review_record(classification_result_id: UUID, payload: dict) -> ReviewRecord:
    requires_review = bool(payload.get("requires_human_review"))
    if requires_review:
        return ReviewRecord(
            classification_result_id=classification_result_id,
            status=ReviewStatus.PENDING,
            reviewer_note="Human review required by classifier policy.",
        )

    return ReviewRecord(
        classification_result_id=classification_result_id,
        status=ReviewStatus.APPROVED,
        reviewer_name="system",
        reviewer_note="Auto-cleared: human review not required.",
    )

