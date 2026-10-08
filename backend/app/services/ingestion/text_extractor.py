from __future__ import annotations

from pathlib import Path

from app.models.enums import DocumentKind, PageContentType
from app.services.ingestion.types import IngestedDocument, IngestedPage


def extract_text_file(path: str) -> IngestedDocument:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    return IngestedDocument(
        kind=DocumentKind.TEXT,
        pages=[
            IngestedPage(
                page_number=1,
                content_type=PageContentType.TEXT,
                section_label=Path(path).name,
                extracted_text=text,
                metadata={"source": "text"},
            )
        ],
        metadata={"source": "text"},
    )
