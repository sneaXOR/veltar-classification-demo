from __future__ import annotations

import json

from app.core.config import get_settings
from app.services.language_settings import get_language_settings, set_language_settings


def test_language_settings_default_to_english(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()

    try:
        settings = get_language_settings()
        assert settings.ui_language == "en"
        assert settings.analysis_language == "en"
        assert settings.rationale_language == "en"
    finally:
        get_settings.cache_clear()


def test_language_settings_persist_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()

    try:
        settings = set_language_settings(
            ui_language="fr",
            analysis_language="en",
            rationale_language="fr",
        )

        assert settings.ui_language == "fr"
        assert settings.analysis_language == "en"
        assert settings.rationale_language == "fr"
        assert get_language_settings() == settings

        payload = json.loads((tmp_path / "runtime" / "language_settings.json").read_text(encoding="utf-8"))
        assert payload == {
            "ui_language": "fr",
            "analysis_language": "en",
            "rationale_language": "fr",
        }
    finally:
        get_settings.cache_clear()
