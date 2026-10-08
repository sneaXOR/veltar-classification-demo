from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.services.language_settings import get_ui_language, resolve_text


_ENVIRONMENT_PROFILE_ID = "environment"
_LOCAL_QWEN_PROFILE_ID = "local_qwen_8b"
_OPENROUTER_QWEN_PROFILE_ID = "openrouter_qwen_plus"
_OPENROUTER_MISTRAL_PROFILE_ID = "openrouter_mistral_medium_3_1"
_OPENROUTER_MISTRAL_LARGE_PROFILE_ID = "openrouter_mistral_large_2512"

_LOCAL_QWEN_MODEL = "Qwen/Qwen3-VL-8B-Instruct"
_LOCAL_QWEN_BASE_URL = "http://host.docker.internal:8080/v1"
_OPENROUTER_MISTRAL_MODEL = "mistralai/mistral-medium-3.1"
_OPENROUTER_MISTRAL_LARGE_MODEL = "mistralai/mistral-large-2512"


@dataclass(frozen=True)
class LLMRuntimeProfile:
    id: str
    label: str
    description: str
    runtime_name: str
    model_name: str
    base_url: str
    api_key: str
    image_transport: str
    verify_ssl: bool
    step2_visual_thinking: bool
    timeout_seconds: int
    max_tokens: int
    local: bool = False

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip()) or self.local


def list_runtime_profiles() -> list[LLMRuntimeProfile]:
    settings = get_settings()
    profiles = _preset_profiles(settings)
    environment_profile = _environment_profile(settings)
    if _has_explicit_environment_runtime() and not any(_same_runtime(profile, environment_profile) for profile in profiles):
        profiles.insert(0, environment_profile)
    return profiles


def get_active_runtime_profile() -> LLMRuntimeProfile:
    stored_profile_id = _read_active_profile_id()
    if stored_profile_id:
        try:
            return get_runtime_profile(stored_profile_id)
        except ValueError:
            pass
    if _has_explicit_environment_runtime():
        settings = get_settings()
        environment_profile = _environment_profile(settings)
        for profile in _preset_profiles(settings):
            if _same_runtime(profile, environment_profile):
                return profile
        return environment_profile
    return get_runtime_profile(_OPENROUTER_QWEN_PROFILE_ID)


def get_runtime_profile(profile_id: str | None) -> LLMRuntimeProfile:
    if profile_id is None:
        return get_active_runtime_profile()

    settings = get_settings()
    profiles = list_runtime_profiles()
    for profile in profiles:
        if profile_id in {profile.id, profile.runtime_name}:
            return profile
    if profile_id == _ENVIRONMENT_PROFILE_ID:
        return _environment_profile(settings)
    return _environment_profile(settings, runtime_name=profile_id)


def get_preferred_openrouter_profile() -> LLMRuntimeProfile:
    active_profile = get_active_runtime_profile()
    settings = get_settings()
    active_profile_id = getattr(active_profile, "id", None)
    if active_profile_id in {
        _OPENROUTER_QWEN_PROFILE_ID,
        _OPENROUTER_MISTRAL_PROFILE_ID,
        _OPENROUTER_MISTRAL_LARGE_PROFILE_ID,
    }:
        return get_runtime_profile(active_profile_id)
    active_base_url = getattr(active_profile, "base_url", None)
    if isinstance(active_base_url, str) and _normalize_base_url(active_base_url) == _normalize_base_url(settings.openrouter_base_url):
        return active_profile
    return get_runtime_profile(_OPENROUTER_QWEN_PROFILE_ID)


def set_active_runtime_profile(profile_id: str) -> LLMRuntimeProfile:
    available_profiles = list_runtime_profiles()
    profile = next((item for item in available_profiles if profile_id == item.id), None)
    if profile is None:
        raise ValueError(f"Unknown LLM runtime profile: {profile_id}")
    selection_path = _runtime_selection_path()
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(json.dumps({"profile_id": profile.id}), encoding="utf-8")
    return profile


def serialize_runtime_profile(profile: LLMRuntimeProfile) -> dict[str, str | bool | int]:
    return {
        "id": profile.id,
        "label": profile.label,
        "description": profile.description,
        "runtime_name": profile.runtime_name,
        "model_name": profile.model_name,
        "base_url": profile.base_url,
        "image_transport": profile.image_transport,
        "verify_ssl": profile.verify_ssl,
        "step2_visual_thinking": profile.step2_visual_thinking,
        "timeout_seconds": profile.timeout_seconds,
        "max_tokens": profile.max_tokens,
        "local": profile.local,
        "api_key_configured": profile.api_key_configured,
    }


def _preset_profiles(settings) -> list[LLMRuntimeProfile]:
    return [
        _local_qwen_profile(settings),
        _openrouter_qwen_profile(settings),
        _openrouter_mistral_profile(settings),
        _openrouter_mistral_large_profile(settings),
    ]


def _environment_profile(settings, *, runtime_name: str = _ENVIRONMENT_PROFILE_ID) -> LLMRuntimeProfile:
    api_key = _resolve_environment_api_key(settings)
    ui_language = get_ui_language()
    return LLMRuntimeProfile(
        id=_ENVIRONMENT_PROFILE_ID,
        label=resolve_text(
            english="Environment configuration",
            french="Configuration environnement",
            language=ui_language,
        ),
        description=resolve_text(
            english="Profile derived from the currently loaded LLM_* variables.",
            french="Profil derive des variables LLM_* actuellement chargees.",
            language=ui_language,
        ),
        runtime_name=runtime_name,
        model_name=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=api_key,
        image_transport=settings.llm_image_transport,
        verify_ssl=settings.llm_verify_ssl,
        step2_visual_thinking=settings.step2_visual_thinking,
        timeout_seconds=max(60, settings.llm_timeout_seconds),
        max_tokens=max(512, settings.llm_max_tokens),
        local=_is_local_base_url(settings.llm_base_url),
    )


def _local_qwen_profile(settings) -> LLMRuntimeProfile:
    ui_language = get_ui_language()
    return LLMRuntimeProfile(
        id=_LOCAL_QWEN_PROFILE_ID,
        label="Local Qwen 8B",
        description=resolve_text(
            english="Local multimodal runtime via llama.cpp for workstation usage.",
            french="Runtime local multimodal via llama.cpp pour usage poste de travail.",
            language=ui_language,
        ),
        runtime_name=_LOCAL_QWEN_PROFILE_ID,
        model_name=_LOCAL_QWEN_MODEL,
        base_url=_LOCAL_QWEN_BASE_URL,
        api_key="",
        image_transport=settings.llm_image_transport,
        verify_ssl=False,
        step2_visual_thinking=settings.step2_visual_thinking,
        timeout_seconds=600,
        max_tokens=3200,
        local=True,
    )


def _openrouter_qwen_profile(settings) -> LLMRuntimeProfile:
    ui_language = get_ui_language()
    return LLMRuntimeProfile(
        id=_OPENROUTER_QWEN_PROFILE_ID,
        label="OpenRouter Qwen",
        description=resolve_text(
            english="Primary Qwen project model served through OpenRouter.",
            french="Modele Qwen principal du projet via OpenRouter.",
            language=ui_language,
        ),
        runtime_name=_OPENROUTER_QWEN_PROFILE_ID,
        model_name=settings.openrouter_model,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        image_transport="base64",
        verify_ssl=True,
        step2_visual_thinking=False,
        timeout_seconds=max(180, settings.openrouter_timeout_seconds),
        max_tokens=max(8000, settings.openrouter_max_tokens),
        local=False,
    )


def _openrouter_mistral_profile(settings) -> LLMRuntimeProfile:
    ui_language = get_ui_language()
    return LLMRuntimeProfile(
        id=_OPENROUTER_MISTRAL_PROFILE_ID,
        label="OpenRouter Mistral Medium 3.1",
        description=resolve_text(
            english="Mistral Medium 3.1 project model served through OpenRouter.",
            french="Modele Mistral Medium 3.1 via OpenRouter pour le projet.",
            language=ui_language,
        ),
        runtime_name=_OPENROUTER_MISTRAL_PROFILE_ID,
        model_name=_OPENROUTER_MISTRAL_MODEL,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        image_transport="base64",
        verify_ssl=True,
        step2_visual_thinking=False,
        timeout_seconds=max(180, settings.openrouter_timeout_seconds),
        max_tokens=max(8000, settings.openrouter_max_tokens),
        local=False,
    )


def _openrouter_mistral_large_profile(settings) -> LLMRuntimeProfile:
    ui_language = get_ui_language()
    return LLMRuntimeProfile(
        id=_OPENROUTER_MISTRAL_LARGE_PROFILE_ID,
        label="OpenRouter Mistral Large 25.12",
        description=resolve_text(
            english="Mistral Large 25.12 project model served through OpenRouter.",
            french="Modele Mistral Large 25.12 via OpenRouter pour le projet.",
            language=ui_language,
        ),
        runtime_name=_OPENROUTER_MISTRAL_LARGE_PROFILE_ID,
        model_name=_OPENROUTER_MISTRAL_LARGE_MODEL,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        image_transport="base64",
        verify_ssl=True,
        step2_visual_thinking=False,
        timeout_seconds=max(180, settings.openrouter_timeout_seconds),
        max_tokens=max(8000, settings.openrouter_max_tokens),
        local=False,
    )


def _same_runtime(left: LLMRuntimeProfile, right: LLMRuntimeProfile) -> bool:
    return (
        left.model_name.strip().lower() == right.model_name.strip().lower()
        and _normalize_base_url(left.base_url) == _normalize_base_url(right.base_url)
        and left.image_transport == right.image_transport
        and left.verify_ssl == right.verify_ssl
        and left.step2_visual_thinking == right.step2_visual_thinking
    )


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/").lower()


def _resolve_environment_api_key(settings) -> str:
    llm_api_key = (settings.llm_api_key or "").strip()
    if llm_api_key:
        return llm_api_key

    if _normalize_base_url(settings.llm_base_url) == _normalize_base_url(settings.openrouter_base_url):
        return (settings.openrouter_api_key or "").strip()

    return ""


def _is_local_base_url(value: str) -> bool:
    normalized = _normalize_base_url(value)
    return any(host in normalized for host in ("localhost", "127.0.0.1", "host.docker.internal"))


def _runtime_selection_path() -> Path:
    settings = get_settings()
    return settings.storage_root.parent / "runtime" / "llm_runtime_profile.json"


def _has_explicit_environment_runtime() -> bool:
    return any(
        key in os.environ
        for key in (
            "LLM_BASE_URL",
            "LLM_MODEL",
            "LLM_API_KEY",
            "LLM_IMAGE_TRANSPORT",
            "LLM_VERIFY_SSL",
            "LLM_TIMEOUT_SECONDS",
            "LLM_MAX_TOKENS",
            "STEP2_VISUAL_THINKING",
        )
    )


def _read_active_profile_id() -> str | None:
    selection_path = _runtime_selection_path()
    if not selection_path.exists():
        return None
    try:
        payload = json.loads(selection_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    profile_id = payload.get("profile_id") if isinstance(payload, dict) else None
    return profile_id.strip() if isinstance(profile_id, str) and profile_id.strip() else None
