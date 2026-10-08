from __future__ import annotations

import uuid

import fitz

from app.core.config import get_settings
from app.services.ingestion.pdf_extractor import extract_pdf
from app.services.storage.file_manager import FileManager


def _build_pdf(path, page_count: int) -> None:
    document = fitz.open()
    for index in range(page_count):
        page = document.new_page()
        page.insert_text((72, 72), f"Page {index + 1}")
    document.save(path)
    document.close()


def test_extract_pdf_reads_all_pages_when_no_limit(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_root", tmp_path / "storage")
    monkeypatch.setattr(settings, "max_pages_per_document", None)

    pdf_path = tmp_path / "sample.pdf"
    _build_pdf(pdf_path, page_count=3)

    ingestion = extract_pdf(str(pdf_path), uuid.uuid4(), FileManager())

    assert len(ingestion.pages) == 3
    assert ingestion.metadata["source_page_count"] == 3
    assert ingestion.metadata["page_limit_applied"] is None


def test_extract_pdf_respects_configured_page_limit(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_root", tmp_path / "storage")
    monkeypatch.setattr(settings, "max_pages_per_document", 2)

    pdf_path = tmp_path / "sample.pdf"
    _build_pdf(pdf_path, page_count=4)

    ingestion = extract_pdf(str(pdf_path), uuid.uuid4(), FileManager())

    assert len(ingestion.pages) == 2
    assert ingestion.metadata["source_page_count"] == 4
    assert ingestion.metadata["page_limit_applied"] == 2
