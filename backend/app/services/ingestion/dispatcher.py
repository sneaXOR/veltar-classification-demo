from __future__ import annotations

from pathlib import Path

from app.models.enums import DocumentKind
from app.services.ingestion.email_extractor import extract_email
from app.services.ingestion.image_extractor import extract_image
from app.services.ingestion.office_extractor import extract_office
from app.services.ingestion.pdf_extractor import extract_pdf
from app.services.ingestion.text_extractor import extract_text_file
from app.services.ingestion.types import IngestedDocument
from app.services.storage.file_manager import FileManager


def detect_kind(content_type: str | None, filename: str) -> DocumentKind | None:
    suffix = Path(filename).suffix.lower()
    content_type = (content_type or "").lower()
    if suffix == ".pdf" or content_type == "application/pdf":
        return DocumentKind.PDF
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"} or content_type.startswith("image/"):
        return DocumentKind.IMAGE
    if suffix in {".docx", ".xlsx", ".xlsm", ".pptx"}:
        return DocumentKind.OFFICE
    if suffix in {".eml", ".msg"} or content_type in {"message/rfc822", "application/vnd.ms-outlook"}:
        return DocumentKind.EMAIL
    if suffix in {".txt", ".md"} or content_type.startswith("text/"):
        return DocumentKind.TEXT
    return None


def extract_supported_file(path: str, document_id, file_manager: FileManager, content_type: str | None = None) -> IngestedDocument:
    kind = detect_kind(content_type, path)
    if kind == DocumentKind.PDF:
        return extract_pdf(path, document_id, file_manager)
    if kind == DocumentKind.IMAGE:
        return extract_image(path)
    if kind == DocumentKind.OFFICE:
        return extract_office(path)
    if kind == DocumentKind.EMAIL:
        return extract_email(path, document_id, file_manager)
    if kind == DocumentKind.TEXT:
        return extract_text_file(path)
    return IngestedDocument(kind=DocumentKind.UNKNOWN, pages=[], metadata={"source": "unsupported"})
