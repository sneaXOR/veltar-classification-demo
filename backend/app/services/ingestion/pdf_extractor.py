from __future__ import annotations

import fitz

from app.core.config import get_settings
from app.models.enums import DocumentKind, PageContentType
from app.services.ingestion.types import IngestedDocument, IngestedPage
from app.services.storage.file_manager import FileManager


def extract_pdf(path: str, document_id, file_manager: FileManager) -> IngestedDocument:
    settings = get_settings()
    pdf = fitz.open(path)
    pages: list[IngestedPage] = []
    max_pages = settings.max_pages_per_document
    page_iterable = pdf if not max_pages else pdf[:max_pages]

    for idx, page in enumerate(page_iterable, start=1):
        text = page.get_text("text")
        pix = page.get_pixmap(dpi=144, alpha=False)
        image_path = file_manager.save_page_image(document_id, idx, pix.tobytes("png"))
        content_type = PageContentType.HYBRID if text.strip() else PageContentType.IMAGE
        if text.strip() and page.rect.width < 1:
            content_type = PageContentType.TEXT
        pages.append(
            IngestedPage(
                page_number=idx,
                content_type=content_type,
                section_label=f"Page {idx}",
                extracted_text=text.strip() or None,
                image_path=image_path,
                width=pix.width,
                height=pix.height,
                metadata={"source": "pdf"},
            )
        )

    return IngestedDocument(
        kind=DocumentKind.PDF,
        pages=pages,
        metadata={
            "title": pdf.metadata.get("title"),
            "author": pdf.metadata.get("author"),
            "source_page_count": len(pdf),
            "page_limit_applied": max_pages,
        },
    )
