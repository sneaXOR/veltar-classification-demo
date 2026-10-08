from app.models.enums import PageContentType
from app.services.ingestion.types import IngestedPage, sanitize_text_for_storage


def test_sanitize_text_for_storage_removes_null_bytes():
    assert sanitize_text_for_storage("abc\x00def") == "abcdef"
    assert sanitize_text_for_storage(None) is None


def test_ingested_page_sanitizes_text_fields_and_char_count():
    page = IngestedPage(
        page_number=1,
        content_type=PageContentType.TEXT,
        section_label="Page\x00 1",
        extracted_text="abc\x00def",
        image_path="/tmp/page-\x000001.png",
    )

    assert page.section_label == "Page 1"
    assert page.extracted_text == "abcdef"
    assert page.image_path == "/tmp/page-0001.png"
    assert page.char_count == 6
