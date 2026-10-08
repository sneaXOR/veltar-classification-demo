from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.session as db_session
from app.core.config import get_settings
from app.main import app
from app.models import Document
from app.models.enums import ArtifactStatus, DocumentKind, DocumentStatus
from app.api.documents import _document_list_item


def test_upload_document_returns_job_without_lazy_loading(monkeypatch, tmp_path):
    async def _noop_recover_jobs(*args, **kwargs) -> None:
        return None

    queued_job_ids: list[str] = []

    async def _noop_enqueue(job_id) -> str:
        queued_job_ids.append(str(job_id))
        return "test"

    settings = get_settings()
    storage_root = tmp_path / "storage"
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'upload-test.db').as_posix()}"
    engine = create_async_engine(database_url, echo=False, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(settings, "storage_root", storage_root)
    monkeypatch.setattr("app.api.documents.enqueue_classification_job", _noop_enqueue)
    monkeypatch.setattr("app.main.recover_incomplete_jobs", _noop_recover_jobs)
    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_factory)

    fixture_path = Path(__file__).resolve().parent / "fixtures" / "spec_excerpt.txt"

    try:
        with TestClient(app) as client:
            with fixture_path.open("rb") as handle:
                response = client.post(
                    "/api/documents",
                    files={"file": ("spec_excerpt.txt", handle, "text/plain")},
                    data={"context_hint": "pytest upload smoke"},
                )
    finally:
        asyncio.run(engine.dispose())

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["original_filename"] == "spec_excerpt.txt"
    assert payload["document"]["latest_job_id"] == payload["job"]["id"]
    assert payload["document"]["latest_job_status"] == "queued"
    assert queued_job_ids == [payload["job"]["id"]]
    assert any(storage_root.rglob("*.txt"))


def test_upload_document_rejects_unconfigured_openrouter_runtime(monkeypatch, tmp_path):
    async def _noop_recover_jobs(*args, **kwargs) -> None:
        return None

    queued_job_ids: list[str] = []

    async def _noop_enqueue(job_id) -> str:
        queued_job_ids.append(str(job_id))
        return "test"

    settings = get_settings()
    storage_root = tmp_path / "storage"
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'upload-runtime-error.db').as_posix()}"
    engine = create_async_engine(database_url, echo=False, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(settings, "storage_root", storage_root)
    monkeypatch.setattr("app.api.documents.get_active_runtime_profile", lambda: SimpleNamespace(base_url="https://openrouter.ai/api/v1", api_key_configured=False))
    monkeypatch.setattr("app.api.documents.enqueue_classification_job", _noop_enqueue)
    monkeypatch.setattr("app.main.recover_incomplete_jobs", _noop_recover_jobs)
    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_factory)

    fixture_path = Path(__file__).resolve().parent / "fixtures" / "spec_excerpt.txt"

    try:
        with TestClient(app) as client:
            with fixture_path.open("rb") as handle:
                response = client.post(
                    "/api/documents",
                    files={"file": ("spec_excerpt.txt", handle, "text/plain")},
                )
    finally:
        asyncio.run(engine.dispose())

    assert response.status_code == 503
    assert "OpenRouter" in response.json()["detail"]
    assert queued_job_ids == []


def test_upload_document_accepts_golden_sha_without_openrouter_key(monkeypatch, tmp_path):
    async def _noop_recover_jobs(*args, **kwargs) -> None:
        return None

    queued_job_ids: list[str] = []

    async def _noop_enqueue(job_id) -> str:
        queued_job_ids.append(str(job_id))
        return "test"

    settings = get_settings()
    storage_root = tmp_path / "storage"
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'upload-golden-runtime.db').as_posix()}"
    engine = create_async_engine(database_url, echo=False, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(settings, "storage_root", storage_root)
    monkeypatch.setattr(
        "app.api.documents.get_active_runtime_profile",
        lambda: SimpleNamespace(
            base_url="https://openrouter.ai/api/v1",
            api_key_configured=False,
            model_name="openrouter-test",
            runtime_name="openrouter",
        ),
    )
    monkeypatch.setattr("app.api.documents.is_golden_document_sha256", lambda value: True)
    monkeypatch.setattr("app.api.documents.enqueue_classification_job", _noop_enqueue)
    monkeypatch.setattr("app.main.recover_incomplete_jobs", _noop_recover_jobs)
    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_factory)

    fixture_path = Path(__file__).resolve().parent / "fixtures" / "spec_excerpt.txt"

    try:
        with TestClient(app) as client:
            with fixture_path.open("rb") as handle:
                response = client.post(
                    "/api/documents",
                    files={"file": ("spec_excerpt.txt", handle, "text/plain")},
                )
    finally:
        asyncio.run(engine.dispose())

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["latest_job_status"] == "queued"
    assert queued_job_ids == [payload["job"]["id"]]


def test_document_list_item_exposes_artifact_state():
    now = datetime.now(timezone.utc)
    document = Document(
        id=uuid4(),
        original_filename="sample.txt",
        stored_filename="stored.txt",
        media_type="text/plain",
        kind=DocumentKind.TEXT,
        status=DocumentStatus.COMPLETED,
        source_path="/tmp/source.txt",
        sha256="abc123",
        artifact_status=ArtifactStatus.READY,
        marked_artifact_path="/tmp/artifacts/sample.txt",
        page_count=1,
        created_at=now,
        updated_at=now,
    )

    item = _document_list_item(document)

    assert item.relative_path is None
    assert item.artifact_status == ArtifactStatus.READY
    assert item.artifact_available is True


def test_upload_batch_persists_relative_paths(monkeypatch, tmp_path):
    async def _noop_recover_jobs(*args, **kwargs) -> None:
        return None

    queued_job_ids: list[str] = []

    async def _noop_enqueue(job_id) -> str:
        queued_job_ids.append(str(job_id))
        return "test"

    settings = get_settings()
    storage_root = tmp_path / "storage"
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'upload-batch-test.db').as_posix()}"
    engine = create_async_engine(database_url, echo=False, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(settings, "storage_root", storage_root)
    monkeypatch.setattr("app.api.documents.enqueue_classification_job", _noop_enqueue)
    monkeypatch.setattr("app.main.recover_incomplete_jobs", _noop_recover_jobs)
    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_factory)

    fixture_path = Path(__file__).resolve().parent / "fixtures" / "spec_excerpt.txt"

    try:
        with TestClient(app) as client:
            with fixture_path.open("rb") as first_handle, fixture_path.open("rb") as second_handle:
                response = client.post(
                    "/api/batches",
                    files=[
                        ("files", ("spec_excerpt.txt", first_handle, "text/plain")),
                        ("files", ("spec_excerpt-copy.txt", second_handle, "text/plain")),
                        ("relative_paths", (None, "Folder/spec_excerpt.txt")),
                        ("relative_paths", (None, "Folder/Sub/spec_excerpt-copy.txt")),
                    ],
                )

            assert response.status_code == 200
            payload = response.json()
            assert len(payload["jobs"]) == 2

            with TestClient(app) as list_client:
                list_response = list_client.get("/api/documents")
    finally:
        asyncio.run(engine.dispose())

    assert list_response.status_code == 200
    documents = list_response.json()
    assert {item["relative_path"] for item in documents} >= {
        "Folder/spec_excerpt.txt",
        "Folder/Sub/spec_excerpt-copy.txt",
    }


def test_upload_batch_rejects_unconfigured_openrouter_runtime(monkeypatch, tmp_path):
    async def _noop_recover_jobs(*args, **kwargs) -> None:
        return None

    settings = get_settings()
    storage_root = tmp_path / "storage"
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'upload-batch-runtime-error.db').as_posix()}"
    engine = create_async_engine(database_url, echo=False, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(settings, "storage_root", storage_root)
    monkeypatch.setattr("app.api.documents.get_active_runtime_profile", lambda: SimpleNamespace(base_url="https://openrouter.ai/api/v1", api_key_configured=False))
    monkeypatch.setattr("app.main.recover_incomplete_jobs", _noop_recover_jobs)
    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_factory)

    fixture_path = Path(__file__).resolve().parent / "fixtures" / "spec_excerpt.txt"

    try:
        with TestClient(app) as client:
            with fixture_path.open("rb") as handle:
                response = client.post(
                    "/api/batches",
                    files=[("files", ("spec_excerpt.txt", handle, "text/plain"))],
                )
    finally:
        asyncio.run(engine.dispose())

    assert response.status_code == 503
    assert "OpenRouter" in response.json()["detail"]


def test_upload_batch_accepts_golden_sha_without_openrouter_key(monkeypatch, tmp_path):
    async def _noop_recover_jobs(*args, **kwargs) -> None:
        return None

    queued_job_ids: list[str] = []

    async def _noop_enqueue(job_id) -> str:
        queued_job_ids.append(str(job_id))
        return "test"

    settings = get_settings()
    storage_root = tmp_path / "storage"
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'upload-batch-golden-runtime.db').as_posix()}"
    engine = create_async_engine(database_url, echo=False, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(settings, "storage_root", storage_root)
    monkeypatch.setattr(
        "app.api.documents.get_active_runtime_profile",
        lambda: SimpleNamespace(
            base_url="https://openrouter.ai/api/v1",
            api_key_configured=False,
            model_name="openrouter-test",
            runtime_name="openrouter",
        ),
    )
    monkeypatch.setattr("app.api.documents.is_golden_document_sha256", lambda value: True)
    monkeypatch.setattr("app.api.documents.enqueue_classification_job", _noop_enqueue)
    monkeypatch.setattr("app.main.recover_incomplete_jobs", _noop_recover_jobs)
    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_factory)

    fixture_path = Path(__file__).resolve().parent / "fixtures" / "spec_excerpt.txt"

    try:
        with TestClient(app) as client:
            with fixture_path.open("rb") as handle:
                response = client.post(
                    "/api/batches",
                    files=[("files", ("spec_excerpt.txt", handle, "text/plain"))],
                )
    finally:
        asyncio.run(engine.dispose())

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["jobs"]) == 1
    assert queued_job_ids == [payload["jobs"][0]["id"]]
