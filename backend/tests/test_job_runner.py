import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.services.classification.job_runner as job_runner_module
from app.models import ClassificationJob, ClassificationResult, Document, DocumentPage, PageClassification, ReviewRecord
from app.models.enums import DocumentKind, DocumentStatus, JobStatus, LaneType, PageContentType, ReviewPriority
from app.services.classification.job_runner import (
    _critical_llm_failure_message,
    _ingest_document,
    _persist_classification,
    _should_raise_for_critical_llm_failure,
    build_job_progress_snapshot,
    recover_incomplete_jobs,
)
from app.services.classification.queue import build_queue_state
from app.services.ingestion.types import IngestedDocument, IngestedPage
from app.services.storage.file_manager import FileManager


def test_critical_llm_failure_message_detects_page_scan_failure():
    message = _critical_llm_failure_message(
        {
            "page_payloads": [
                {"page_number": 3, "_llm_failed": True, "_llm_error": "LLM ConnectError: boom"},
            ],
            "step_results": {},
        }
    )

    assert message == "Echec LLM critique pendant l'analyse de page 3: LLM ConnectError: boom"


def test_build_job_progress_snapshot_uses_english_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        snapshot = build_job_progress_snapshot(stage="queued")
        assert snapshot["stage_label"] == "Queued"
        assert snapshot["message"] == "Waiting for processing"
    finally:
        get_settings.cache_clear()


def test_critical_llm_failure_message_detects_step_failure():
    message = _critical_llm_failure_message(
        {
            "page_payloads": [],
            "step_results": {
                "step_b": {"_llm_failed": True, "_llm_error": "LLM ConnectError: All connection attempts failed"},
                "step_timing": {"step_b": 1.23},
            },
        }
    )

    assert message == (
        "Echec LLM critique pendant l'identification du tangible: "
        "LLM ConnectError: All connection attempts failed"
    )


def test_critical_llm_failure_message_returns_none_when_payload_is_clean():
    message = _critical_llm_failure_message(
        {
            "page_payloads": [{"page_number": 1, "_llm_failed": False}],
            "step_results": {"step_b": {"_llm_failed": False}, "step_timing": {"step_b": 1.23}},
        }
    )

    assert message is None


def test_should_not_raise_when_orchestrator_degrades_to_review_required():
    result_payload = {
        "final_marking": "EC_Review_Required",
        "requires_human_review": True,
        "step_results": {
            "step_c": {"_llm_failed": True, "_llm_error": "LLM provider returned an error payload: Temporary upstream failure"},
        },
    }
    critical_message = _critical_llm_failure_message(result_payload)

    assert critical_message is not None
    assert _should_raise_for_critical_llm_failure(result_payload, critical_message) is False


def test_should_raise_when_no_review_fallback_exists():
    result_payload = {
        "final_marking": None,
        "requires_human_review": False,
        "step_results": {
            "step_b": {"_llm_failed": True, "_llm_error": "LLM ConnectError: boom"},
        },
    }
    critical_message = _critical_llm_failure_message(result_payload)

    assert critical_message is not None
    assert _should_raise_for_critical_llm_failure(result_payload, critical_message) is True


def test_persist_classification_reloads_pages_from_database(tmp_path):
    async def scenario() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'job-runner.db').as_posix()}", future=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        try:
            from app.db.base import Base

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            async with session_factory() as session:
                now = datetime.now(timezone.utc)
                document = Document(
                    id=uuid4(),
                    original_filename="sample.txt",
                    stored_filename="sample.txt",
                    media_type="text/plain",
                    kind=DocumentKind.TEXT,
                    status=DocumentStatus.PROCESSING,
                    source_path=str(tmp_path / "sample.txt"),
                    sha256="abc123",
                    page_count=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(document)
                await session.flush()

                page = DocumentPage(
                    document_id=document.id,
                    page_number=1,
                    content_type=PageContentType.TEXT,
                    section_label="Page 1",
                    extracted_text="hello",
                    char_count=5,
                )
                session.add(page)

                job = ClassificationJob(
                    document_id=document.id,
                    status=JobStatus.RUNNING,
                    model_name="test-model",
                    runtime_name="test-runtime",
                    gate_report={},
                )
                session.add(job)
                await session.commit()

                # Simulate a stale relationship state: persisted pages exist in DB,
                # but the in-memory document instance does not expose them reliably.
                set_committed_value(document, "pages", [])
                set_committed_value(document, "classification", None)

                payload = {
                    "lane": LaneType.FR_EU,
                    "final_marking": "FR_EC_2E001",
                    "final_confidence": 0.9,
                    "experimental": False,
                    "insufficient_evidence": False,
                    "requires_human_review": False,
                    "review_priority": ReviewPriority.MEDIUM,
                    "jurisdiction": "FR",
                    "reasoning_summary": "ok",
                    "candidate_markings": [],
                    "citations": [],
                    "evidence_items": [],
                    "page_rollup": {},
                    "step_results": {},
                    "veltar_projection": {},
                    "pipeline_version": "v2",
                    "lifecycle_phase": None,
                    "tangible_description": None,
                    "tangible_category": None,
                    "page_payloads": [
                        {
                            "page_number": 1,
                            "relevant": True,
                            "technical_score": 10,
                            "confidence": 0.8,
                            "page_summary": "summary",
                            "evidence": [],
                            "citations": [],
                        }
                    ],
                }

                classification = await _persist_classification(session, document, job, payload)
                await session.commit()
                await session.refresh(classification, attribute_names=["page_classifications"])

                assert len(classification.page_classifications) == 1
                assert classification.page_classifications[0].page_number == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_persist_classification_replaces_existing_result_when_relationship_is_stale(tmp_path):
    async def scenario() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'job-runner-existing.db').as_posix()}", future=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        try:
            from app.db.base import Base

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            async with session_factory() as session:
                now = datetime.now(timezone.utc)
                document = Document(
                    id=uuid4(),
                    original_filename="sample.txt",
                    stored_filename="sample.txt",
                    media_type="text/plain",
                    kind=DocumentKind.TEXT,
                    status=DocumentStatus.PROCESSING,
                    source_path=str(tmp_path / "sample.txt"),
                    sha256="abc123",
                    page_count=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(document)
                await session.flush()

                page = DocumentPage(
                    document_id=document.id,
                    page_number=1,
                    content_type=PageContentType.TEXT,
                    section_label="Page 1",
                    extracted_text="hello",
                    char_count=5,
                )
                session.add(page)

                first_job = ClassificationJob(
                    document_id=document.id,
                    status=JobStatus.COMPLETED,
                    model_name="test-model",
                    runtime_name="test-runtime",
                    gate_report={},
                )
                session.add(first_job)
                await session.flush()

                existing = ClassificationResult(
                    document_id=document.id,
                    job_id=first_job.id,
                    lane=LaneType.FR_EU,
                    final_marking="FR_EC_1A001",
                    final_confidence=0.5,
                    experimental=False,
                    insufficient_evidence=False,
                    requires_human_review=False,
                    review_priority=ReviewPriority.MEDIUM,
                    jurisdiction="FR",
                    reasoning_summary="old",
                    candidate_markings=[],
                    citations=[],
                    evidence_items=[],
                    page_rollup={},
                    step_results={},
                    veltar_projection={},
                    pipeline_version="v2",
                    lifecycle_phase=None,
                    tangible_description=None,
                    tangible_category=None,
                )
                session.add(existing)
                await session.flush()

                session.add(
                    PageClassification(
                        classification_result_id=existing.id,
                        page_id=page.id,
                        page_number=1,
                        relevant=True,
                        technical_score=10,
                        confidence=0.5,
                        summary="old page",
                        evidence=[],
                        citations=[],
                        step_payload={},
                    )
                )
                session.add(
                    ReviewRecord(
                        classification_result_id=existing.id,
                        reviewer_name="system",
                        reviewer_note="old review",
                    )
                )

                replacement_job = ClassificationJob(
                    document_id=document.id,
                    status=JobStatus.RUNNING,
                    model_name="test-model",
                    runtime_name="test-runtime",
                    gate_report={},
                )
                session.add(replacement_job)
                await session.commit()

                set_committed_value(document, "classification", None)

                payload = {
                    "lane": LaneType.FR_EU,
                    "final_marking": "FR_EC_2E001",
                    "final_confidence": 0.9,
                    "experimental": False,
                    "insufficient_evidence": False,
                    "requires_human_review": False,
                    "review_priority": ReviewPriority.MEDIUM,
                    "jurisdiction": "FR",
                    "reasoning_summary": "new",
                    "candidate_markings": [],
                    "citations": [],
                    "evidence_items": [],
                    "page_rollup": {},
                    "step_results": {},
                    "veltar_projection": {},
                    "pipeline_version": "v2",
                    "lifecycle_phase": None,
                    "tangible_description": None,
                    "tangible_category": None,
                    "page_payloads": [
                        {
                            "page_number": 1,
                            "relevant": True,
                            "technical_score": 10,
                            "confidence": 0.8,
                            "page_summary": "summary",
                            "evidence": [],
                            "citations": [],
                        }
                    ],
                }

                classification = await _persist_classification(session, document, replacement_job, payload)
                await session.commit()

                classifications = list(
                    await session.scalars(
                        job_runner_module.select(ClassificationResult).where(ClassificationResult.document_id == document.id)
                    )
                )
                assert len(classifications) == 1
                assert classifications[0].id == classification.id
                assert classifications[0].job_id == replacement_job.id
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_ingest_document_removes_null_bytes_before_persisting(tmp_path, monkeypatch):
    async def scenario() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'job-runner-ingest.db').as_posix()}", future=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        try:
            from app.core.config import get_settings
            from app.db.base import Base

            settings = get_settings()
            monkeypatch.setattr(settings, "storage_root", tmp_path / "storage")

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            async with session_factory() as session:
                now = datetime.now(timezone.utc)
                document = Document(
                    id=uuid4(),
                    original_filename="sample.pdf",
                    stored_filename="sample.pdf",
                    media_type="application/pdf",
                    kind=DocumentKind.PDF,
                    status=DocumentStatus.UPLOADED,
                    source_path=str(tmp_path / "sample.pdf"),
                    sha256="abc123",
                    page_count=0,
                    created_at=now,
                    updated_at=now,
                )
                session.add(document)
                await session.flush()

                monkeypatch.setattr(
                    job_runner_module,
                    "extract_supported_file",
                    lambda *args, **kwargs: IngestedDocument(
                        kind=DocumentKind.PDF,
                        pages=[
                            IngestedPage(
                                page_number=1,
                                content_type=PageContentType.TEXT,
                                section_label="Page\x00 1",
                                extracted_text="abc\x00def",
                                image_path="/tmp/page-\x000001.png",
                            )
                        ],
                        metadata={"source": "test"},
                    ),
                )

                await _ingest_document(session, document, FileManager())
                await session.commit()
                await session.refresh(document, attribute_names=["pages"])

                assert document.page_count == 1
                assert len(document.pages) == 1
                assert document.pages[0].section_label == "Page 1"
                assert document.pages[0].extracted_text == "abcdef"
                assert document.pages[0].image_path == "/tmp/page-0001.png"
                assert document.pages[0].char_count == 6
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_recover_incomplete_jobs_only_requeues_stale_running_by_default(tmp_path, monkeypatch):
    async def scenario() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'job-runner-recovery.db').as_posix()}", future=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        queued_job_ids: list[str] = []

        async def _capture_enqueue(job_id) -> str:
            queued_job_ids.append(str(job_id))
            return "test"

        try:
            from app.db.base import Base

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            monkeypatch.setattr(job_runner_module, "AsyncSessionLocal", session_factory)
            monkeypatch.setattr(job_runner_module, "enqueue_classification_job", _capture_enqueue)

            async with session_factory() as session:
                now = datetime.now(timezone.utc)

                queued_document = Document(
                    id=uuid4(),
                    original_filename="queued.txt",
                    stored_filename="queued.txt",
                    media_type="text/plain",
                    kind=DocumentKind.TEXT,
                    status=DocumentStatus.UPLOADED,
                    source_path=str(tmp_path / "queued.txt"),
                    sha256="queued",
                    page_count=1,
                    created_at=now,
                    updated_at=now,
                )
                stale_document = Document(
                    id=uuid4(),
                    original_filename="stale.txt",
                    stored_filename="stale.txt",
                    media_type="text/plain",
                    kind=DocumentKind.TEXT,
                    status=DocumentStatus.PROCESSING,
                    source_path=str(tmp_path / "stale.txt"),
                    sha256="stale",
                    page_count=1,
                    created_at=now,
                    updated_at=now,
                )
                active_document = Document(
                    id=uuid4(),
                    original_filename="active.txt",
                    stored_filename="active.txt",
                    media_type="text/plain",
                    kind=DocumentKind.TEXT,
                    status=DocumentStatus.PROCESSING,
                    source_path=str(tmp_path / "active.txt"),
                    sha256="active",
                    page_count=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add_all([queued_document, stale_document, active_document])
                await session.flush()

                queued_job = ClassificationJob(
                    document_id=queued_document.id,
                    status=JobStatus.QUEUED,
                    model_name="test-model",
                    runtime_name="test-runtime",
                    gate_report={"queue": build_queue_state(state="queued", enqueued_at=now)},
                )
                stale_job = ClassificationJob(
                    document_id=stale_document.id,
                    status=JobStatus.RUNNING,
                    model_name="test-model",
                    runtime_name="test-runtime",
                    gate_report={"queue": build_queue_state(state="running", enqueued_at=now, started_at=now - timedelta(hours=1), lease_until=now - timedelta(minutes=1), attempts=1, worker_id="worker-a")},
                )
                active_job = ClassificationJob(
                    document_id=active_document.id,
                    status=JobStatus.RUNNING,
                    model_name="test-model",
                    runtime_name="test-runtime",
                    gate_report={"queue": build_queue_state(state="running", enqueued_at=now, started_at=now, lease_until=now + timedelta(minutes=5), attempts=1, worker_id="worker-b")},
                )
                session.add_all([queued_job, stale_job, active_job])
                await session.commit()

            recovered = await recover_incomplete_jobs(requeue_queued=False)
            assert recovered == 1
            assert queued_job_ids == [str(stale_job.id)]

            async with session_factory() as session:
                queued_job_db = await session.get(ClassificationJob, queued_job.id)
                stale_job_db = await session.get(ClassificationJob, stale_job.id)
                active_job_db = await session.get(ClassificationJob, active_job.id)

                assert queued_job_db.status == JobStatus.QUEUED
                assert stale_job_db.status == JobStatus.QUEUED
                assert active_job_db.status == JobStatus.RUNNING
        finally:
            await engine.dispose()

    asyncio.run(scenario())
