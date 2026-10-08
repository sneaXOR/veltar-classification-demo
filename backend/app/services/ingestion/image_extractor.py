from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.models.enums import DocumentKind, PageContentType
from app.services.ingestion.types import IngestedDocument, IngestedPage


def extract_image(path: str) -> IngestedDocument:
    image = Image.open(path)
    return IngestedDocument(
        kind=DocumentKind.IMAGE,
        pages=[
            IngestedPage(
                page_number=1,
                content_type=PageContentType.IMAGE,
                section_label=Path(path).name,
                extracted_text=None,
                image_path=path,
                width=image.width,
                height=image.height,
                metadata={"source": "image"},
            )
        ],
        metadata={"source": "image"},
    )
