from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import DocumentKind, PageContentType


def sanitize_text_for_storage(value: str | None) -> str | None:
    if value is None or "\x00" not in value:
        return value
    return value.replace("\x00", "")


@dataclass(slots=True)
class IngestedPage:
    page_number: int
    content_type: PageContentType
    section_label: str
    extracted_text: str | None = None
    image_path: str | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.section_label = sanitize_text_for_storage(self.section_label) or ""
        self.extracted_text = sanitize_text_for_storage(self.extracted_text)
        self.image_path = sanitize_text_for_storage(self.image_path)

    @property
    def char_count(self) -> int:
        return len((self.extracted_text or "").strip())


@dataclass(slots=True)
class IngestedDocument:
    kind: DocumentKind
    pages: list[IngestedPage]
    metadata: dict = field(default_factory=dict)
