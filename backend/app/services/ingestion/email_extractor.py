from __future__ import annotations

import email
from email import policy
from pathlib import Path

from app.models.enums import DocumentKind, PageContentType
from app.services.ingestion.types import IngestedDocument, IngestedPage
from app.services.storage.file_manager import FileManager


def extract_email(path: str, document_id, file_manager: FileManager) -> IngestedDocument:
    pages: list[IngestedPage] = []
    with open(path, "rb") as handle:
        message = email.message_from_binary_file(handle, policy=policy.default)

    body_parts: list[str] = []
    attachment_page_offset = 1
    for part in message.walk():
        content_disposition = part.get_content_disposition()
        filename = part.get_filename()
        if content_disposition == "attachment" and filename:
            payload = part.get_payload(decode=True) or b""
            attachment_path = file_manager.save_attachment(document_id, filename, payload)
            from app.services.ingestion.dispatcher import detect_kind, extract_supported_file

            kind = detect_kind(part.get_content_type(), filename)
            if kind:
                nested = extract_supported_file(str(attachment_path), document_id, file_manager, content_type=part.get_content_type())
                for nested_page in nested.pages:
                    attachment_page_offset += 1
                    pages.append(
                        IngestedPage(
                            page_number=attachment_page_offset,
                            content_type=nested_page.content_type,
                            section_label=f"Attachment {filename} - {nested_page.section_label}",
                            extracted_text=nested_page.extracted_text,
                            image_path=nested_page.image_path,
                            width=nested_page.width,
                            height=nested_page.height,
                            metadata={"source": "email_attachment", "filename": filename},
                        )
                    )
            continue

        if part.get_content_type() == "text/plain":
            body_parts.append(part.get_content().strip())

    header_block = "\n".join(
        [
            f"Subject: {message.get('subject', '')}",
            f"From: {message.get('from', '')}",
            f"To: {message.get('to', '')}",
            "",
            "\n".join(part for part in body_parts if part),
        ]
    ).strip()
    pages.insert(
        0,
        IngestedPage(
            page_number=1,
            content_type=PageContentType.TEXT,
            section_label=Path(path).name,
            extracted_text=header_block,
            metadata={"source": "email"},
        ),
    )
    return IngestedDocument(kind=DocumentKind.EMAIL, pages=pages, metadata={"subject": message.get("subject", "")})
