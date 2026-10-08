from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image

from app.core.config import get_settings
from app.models.document import Document, DocumentPage
from app.models.enums import ArtifactRevisionKind, ArtifactStatus, DocumentKind, DocumentStatus, PageContentType
from app.services.classification.marking_labels import get_marking_label
from app.services.document_artifacts import build_and_persist_document_artifact, persist_document_artifact_revision
from app.services.storage.file_manager import FileManager


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)


def test_build_document_artifact_keeps_source_unchanged_and_tracks_revision(monkeypatch, tmp_path):
    settings = get_settings()
    storage_root = tmp_path / "storage"
    monkeypatch.setattr(settings, "storage_root", storage_root)

    source_path = tmp_path / "spec_excerpt.txt"
    original_text = "Specification body for artifact test."
    source_path.write_text(original_text, encoding="utf-8")

    document = Document(
        id=uuid4(),
        original_filename="spec_excerpt.txt",
        stored_filename="stored.txt",
        media_type="text/plain",
        kind=DocumentKind.TEXT,
        status=DocumentStatus.COMPLETED,
        source_path=str(source_path),
        sha256="abc123",
        page_count=1,
        artifact_version=0,
    )
    document.pages = [
        DocumentPage(
            page_number=1,
            content_type=PageContentType.TEXT,
            section_label="Page 1",
            extracted_text=original_text,
            image_path=None,
            char_count=len(original_text),
        )
    ]

    classification = SimpleNamespace(final_marking="FR_EC_7E001", final_confidence=0.85)
    file_manager = FileManager()

    artifact_result = asyncio.run(
        build_and_persist_document_artifact(
            document=document,
            classification=classification,
            file_manager=file_manager,
            page_classifications=[
                {
                    "page_number": 1,
                    "relevant": True,
                    "technical_score": 85,
                    "confidence": 0.92,
                    "summary": "Technical excerpt",
                    "citations": [],
                    "evidence": [],
                }
            ],
        )
    )

    marked_path = Path(artifact_result.marked_revision_path)

    assert artifact_result.revision == 1
    assert Path(artifact_result.current_path) == marked_path
    assert source_path.read_text(encoding="utf-8") == original_text
    assert marked_path.exists()
    marked_text = marked_path.read_text(encoding="utf-8")
    assert marked_text.startswith(original_text)
    assert marked_text.endswith(get_marking_label("FR_EC_7E001"))
    assert "FR_EC_7E001" not in marked_text
    assert "%" not in marked_text
    assert "CLASSEMENT:" not in marked_text

    session = RecordingSession()
    persist_document_artifact_revision(
        session=session,
        document=document,
        artifact_result=artifact_result,
    )

    assert document.artifact_status == ArtifactStatus.READY
    assert document.artifact_version == 1
    assert document.marked_artifact_path == artifact_result.marked_revision_path

    revisions = {(item.kind, item.revision, item.is_current) for item in session.added}
    assert (ArtifactRevisionKind.ORIGINAL_SNAPSHOT, 1, False) in revisions
    assert (ArtifactRevisionKind.MARKED_REVISION, 1, True) in revisions


def test_marking_label_hides_internal_prefixes():
    assert get_marking_label("DE_EC_7E001", language="fr") == "Controle export DE - rubrique 7E001"
    assert get_marking_label("FR_EC_ML22.a", language="fr") == "Controle export FR - rubrique ML22.a"


def test_build_document_artifact_marks_rgb_image_without_crashing(monkeypatch, tmp_path):
    settings = get_settings()
    storage_root = tmp_path / "storage"
    monkeypatch.setattr(settings, "storage_root", storage_root)

    source_path = tmp_path / "sample.webp"
    Image.new("RGB", (240, 160), color=(240, 240, 240)).save(source_path, format="WEBP")

    document = Document(
        id=uuid4(),
        original_filename="sample.webp",
        stored_filename="sample.webp",
        media_type="image/webp",
        kind=DocumentKind.IMAGE,
        status=DocumentStatus.COMPLETED,
        source_path=str(source_path),
        sha256="def456",
        page_count=1,
        artifact_version=0,
    )
    document.pages = [
        DocumentPage(
            page_number=1,
            content_type=PageContentType.IMAGE,
            section_label="Image",
            extracted_text="",
            image_path=str(source_path),
            char_count=0,
        )
    ]

    classification = SimpleNamespace(final_marking="FR_EC_7E001", final_confidence=0.85)
    file_manager = FileManager()

    artifact_result = asyncio.run(
        build_and_persist_document_artifact(
            document=document,
            classification=classification,
            file_manager=file_manager,
            page_classifications=[
                {
                    "page_number": 1,
                    "relevant": True,
                    "technical_score": 85,
                    "confidence": 0.92,
                    "summary": "Technical image",
                    "citations": [],
                    "evidence": [],
                }
            ],
        )
    )

    marked_path = Path(artifact_result.marked_revision_path)
    assert marked_path.exists()
    assert marked_path.suffix.lower() == ".webp"
