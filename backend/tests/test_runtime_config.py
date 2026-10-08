from __future__ import annotations

import json

from app.core.config import get_settings
import pytest

from app.services.classification.runtime_config import (
    get_active_runtime_profile,
    get_runtime_profile,
    list_runtime_profiles,
    set_active_runtime_profile,
)


def test_runtime_profiles_expose_openrouter_qwen_and_mistral_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_IMAGE_TRANSPORT", raising=False)
    monkeypatch.delenv("LLM_VERIFY_SSL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    monkeypatch.delenv("STEP2_VISUAL_THINKING", raising=False)
    get_settings.cache_clear()

    try:
        profiles = list_runtime_profiles()
        profile_ids = [profile.id for profile in profiles]
        mistral_profile = next(profile for profile in profiles if profile.id == "openrouter_mistral_medium_3_1")
        mistral_large_profile = next(profile for profile in profiles if profile.id == "openrouter_mistral_large_2512")

        assert "openrouter_qwen_plus" in profile_ids
        assert "openrouter_mistral_medium_3_1" in profile_ids
        assert "openrouter_mistral_large_2512" in profile_ids
        assert get_active_runtime_profile().id == "openrouter_qwen_plus"
        assert mistral_profile.model_name == "mistralai/mistral-medium-3.1"
        assert mistral_profile.api_key_configured is True
        assert mistral_large_profile.model_name == "mistralai/mistral-large-2512"
        assert mistral_large_profile.api_key_configured is True
    finally:
        get_settings.cache_clear()


def test_set_active_runtime_profile_persists_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()

    try:
        profile = set_active_runtime_profile("openrouter_mistral_medium_3_1")

        assert profile.id == "openrouter_mistral_medium_3_1"
        assert get_active_runtime_profile().id == "openrouter_mistral_medium_3_1"

        payload = json.loads((tmp_path / "runtime" / "llm_runtime_profile.json").read_text(encoding="utf-8"))
        assert payload == {"profile_id": "openrouter_mistral_medium_3_1"}
    finally:
        get_settings.cache_clear()


def test_environment_profile_is_exposed_when_runtime_is_custom(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("LLM_BASE_URL", "http://custom-runtime.local/v1")
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    monkeypatch.setenv("LLM_API_KEY", "custom-key")
    get_settings.cache_clear()

    try:
        profiles = list_runtime_profiles()
        profile_ids = [profile.id for profile in profiles]

        assert profile_ids[0] == "environment"
        assert "openrouter_qwen_plus" in profile_ids
        assert "openrouter_mistral_medium_3_1" in profile_ids
        assert "openrouter_mistral_large_2512" in profile_ids
        assert get_active_runtime_profile().id == "environment"
        assert profiles[0].model_name == "custom-model"
    finally:
        get_settings.cache_clear()


def test_active_profile_reuses_openrouter_preset_when_explicit_env_matches_it(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen/qwen3.6-plus")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    get_settings.cache_clear()

    try:
        profile = get_active_runtime_profile()

        assert profile.id == "openrouter_qwen_plus"
        assert profile.api_key_configured is True
    finally:
        get_settings.cache_clear()


def test_environment_profile_uses_openrouter_api_key_when_matching_base_url(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_MODEL", "custom-openrouter-model")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    get_settings.cache_clear()

    try:
        profile = get_runtime_profile("environment")

        assert profile.id == "environment"
        assert profile.runtime_name == "environment"
        assert profile.api_key_configured is True
    finally:
        get_settings.cache_clear()


def test_get_runtime_profile_resolves_environment_without_explicit_env(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_IMAGE_TRANSPORT", raising=False)
    monkeypatch.delenv("LLM_VERIFY_SSL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    monkeypatch.delenv("STEP2_VISUAL_THINKING", raising=False)
    get_settings.cache_clear()

    try:
        settings = get_settings()
        profile = get_runtime_profile("environment")

        assert profile.id == "environment"
        assert profile.runtime_name == "environment"
        assert profile.model_name == settings.llm_model
    finally:
        get_settings.cache_clear()


def test_get_runtime_profile_falls_back_to_environment_for_unknown_runtime_name(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        settings = get_settings()
        profile = get_runtime_profile("legacy_runtime")

        assert profile.id == "environment"
        assert profile.runtime_name == "legacy_runtime"
        assert profile.base_url == settings.llm_base_url
    finally:
        get_settings.cache_clear()


def test_set_active_runtime_profile_rejects_unknown_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()

    try:
        with pytest.raises(ValueError, match="Unknown LLM runtime profile: invalid"):
            set_active_runtime_profile("invalid")
    finally:
        get_settings.cache_clear()
