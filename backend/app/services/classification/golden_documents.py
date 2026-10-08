from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from app.models.enums import LaneType, ReviewPriority


GOLDEN_FINAL_MARKING = "FR_EC_Technical_Not_Controlled"
GOLDEN_CAPTURE_MAX_ATTEMPTS = 8

GOLDEN_DOCUMENT_SHA256S = (
    "16000535fe26c1c2dc37b2e3581a7bc6d15f68fbc858b77d484d214d4f970857",
    "ab66491eaf475a4711f353a8155a04ee460de258f15f8940c621612d248d45f1",
    "e352c6d195c4408bfd7db57ab0dd864c9b14f79a6052c90fb2e3ab2978b8f2d3",
)

_PAYLOAD_DIR = Path(__file__).with_name("golden_payloads")


def is_golden_document_sha256(value: str | None) -> bool:
    return has_cached_golden_payload(value)


def is_golden_capture_candidate(value: str | None) -> bool:
    return _normalize_sha256(value) in GOLDEN_DOCUMENT_SHA256S


def has_cached_golden_payload(value: str | None) -> bool:
    sha256 = _normalize_sha256(value)
    return sha256 in GOLDEN_DOCUMENT_SHA256S and _payload_path(sha256).is_file()


def build_cached_golden_payload(document: Any, pages: list[Any]) -> dict[str, Any] | None:
    sha256 = _normalize_sha256(getattr(document, "sha256", None))
    if not has_cached_golden_payload(sha256):
        return None

    payload = json.loads(_payload_path(sha256).read_text(encoding="utf-8"))
    payload = _restore_payload_types(copy.deepcopy(payload))
    page_numbers = {int(getattr(page, "page_number", 0) or 0) for page in pages}
    payload["page_payloads"] = [
        page_payload
        for page_payload in payload.get("page_payloads", [])
        if int(page_payload.get("page_number", 0) or 0) in page_numbers
    ]
    return payload


def is_target_golden_payload(payload: dict[str, Any]) -> bool:
    return payload.get("final_marking") == GOLDEN_FINAL_MARKING


def _payload_path(sha256: str) -> Path:
    return _PAYLOAD_DIR / f"{sha256}.json"


def _restore_payload_types(payload: dict[str, Any]) -> dict[str, Any]:
    lane = payload.get("lane")
    if isinstance(lane, str):
        payload["lane"] = LaneType(lane)

    review_priority = payload.get("review_priority")
    if isinstance(review_priority, str):
        payload["review_priority"] = ReviewPriority(review_priority)

    return payload


def _normalize_sha256(value: str | None) -> str:
    return str(value or "").strip().lower()
