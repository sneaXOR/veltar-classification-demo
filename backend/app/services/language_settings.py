from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings


SUPPORTED_LANGUAGE_CODES = ("en", "fr")
DEFAULT_LANGUAGE_CODE = "en"


@dataclass(frozen=True)
class LanguageSettings:
    ui_language: str = DEFAULT_LANGUAGE_CODE
    analysis_language: str = DEFAULT_LANGUAGE_CODE
    rationale_language: str = DEFAULT_LANGUAGE_CODE


def get_language_settings() -> LanguageSettings:
    settings_path = _language_settings_path()
    if not settings_path.exists():
        return LanguageSettings()

    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return LanguageSettings()

    if not isinstance(payload, dict):
        return LanguageSettings()

    return LanguageSettings(
        ui_language=_normalize_language_code(payload.get("ui_language")),
        analysis_language=_normalize_language_code(payload.get("analysis_language")),
        rationale_language=_normalize_language_code(payload.get("rationale_language")),
    )


def set_language_settings(
    *,
    ui_language: str | None = None,
    analysis_language: str | None = None,
    rationale_language: str | None = None,
) -> LanguageSettings:
    current = get_language_settings()
    next_settings = LanguageSettings(
        ui_language=_normalize_language_code(ui_language, default=current.ui_language),
        analysis_language=_normalize_language_code(analysis_language, default=current.analysis_language),
        rationale_language=_normalize_language_code(rationale_language, default=current.rationale_language),
    )

    settings_path = _language_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(serialize_language_settings(next_settings), indent=2),
        encoding="utf-8",
    )
    return next_settings


def serialize_language_settings(settings: LanguageSettings) -> dict[str, str]:
    return {
        "ui_language": settings.ui_language,
        "analysis_language": settings.analysis_language,
        "rationale_language": settings.rationale_language,
    }


def get_ui_language() -> str:
    return get_language_settings().ui_language


def get_analysis_language() -> str:
    return get_language_settings().analysis_language


def get_rationale_language() -> str:
    return get_language_settings().rationale_language


def resolve_text(*, english: str, french: str, language: str) -> str:
    return english if _normalize_language_code(language) == "en" else french


def get_prompt_language_name(language: str) -> str:
    return "English" if _normalize_language_code(language) == "en" else "French"


def _normalize_language_code(value: Any, *, default: str = DEFAULT_LANGUAGE_CODE) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in SUPPORTED_LANGUAGE_CODES:
            return normalized
    return default


def _language_settings_path() -> Path:
    settings = get_settings()
    return settings.storage_root.parent / "runtime" / "language_settings.json"
