from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.classification.runtime_config import LLMRuntimeProfile
from app.services.language_settings import LanguageSettings


def _profile(profile_id: str, *, label: str) -> LLMRuntimeProfile:
    return LLMRuntimeProfile(
        id=profile_id,
        label=label,
        description=f"{label} profile",
        runtime_name=profile_id,
        model_name=f"{label}-model",
        base_url=f"http://{profile_id}.local/v1",
        api_key="configured",
        image_transport="base64",
        verify_ssl=False,
        step2_visual_thinking=False,
        timeout_seconds=120,
        max_tokens=1800,
        local=profile_id.startswith("local"),
    )


def test_get_llm_settings_endpoint(monkeypatch):
    qwen = _profile("openrouter_qwen_plus", label="OpenRouter Qwen")
    mistral = _profile("openrouter_mistral_medium_3_1", label="OpenRouter Mistral")
    mistral_large = _profile("openrouter_mistral_large_2512", label="OpenRouter Mistral Large")

    monkeypatch.setattr("app.api.settings.get_active_runtime_profile", lambda: qwen)
    monkeypatch.setattr("app.api.settings.list_runtime_profiles", lambda: [qwen, mistral, mistral_large])

    with TestClient(app) as client:
        response = client.get("/api/settings/llm")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_profile_id"] == "openrouter_qwen_plus"
    assert payload["available_profiles"][1]["id"] == "openrouter_mistral_medium_3_1"
    assert payload["available_profiles"][2]["id"] == "openrouter_mistral_large_2512"


def test_update_llm_settings_endpoint(monkeypatch):
    qwen = _profile("openrouter_qwen_plus", label="OpenRouter Qwen")
    mistral = _profile("openrouter_mistral_medium_3_1", label="OpenRouter Mistral")

    monkeypatch.setattr("app.api.settings.list_runtime_profiles", lambda: [qwen, mistral])
    monkeypatch.setattr(
        "app.api.settings.set_active_runtime_profile",
        lambda profile_id: mistral if profile_id == "openrouter_mistral_medium_3_1" else qwen,
    )

    with TestClient(app) as client:
        response = client.put("/api/settings/llm", json={"profile_id": "openrouter_mistral_medium_3_1"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_profile_id"] == "openrouter_mistral_medium_3_1"
    assert payload["active_profile"]["label"] == "OpenRouter Mistral"


def test_get_language_settings_endpoint(monkeypatch):
    monkeypatch.setattr(
        "app.api.settings.get_language_settings",
        lambda: LanguageSettings(ui_language="en", analysis_language="en", rationale_language="fr"),
    )

    with TestClient(app) as client:
        response = client.get("/api/settings/language")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "ui_language": "en",
        "analysis_language": "en",
        "rationale_language": "fr",
    }


def test_update_language_settings_endpoint(monkeypatch):
    monkeypatch.setattr(
        "app.api.settings.set_language_settings",
        lambda **_: LanguageSettings(ui_language="fr", analysis_language="en", rationale_language="en"),
    )

    with TestClient(app) as client:
        response = client.put(
            "/api/settings/language",
            json={"ui_language": "fr", "analysis_language": "en", "rationale_language": "en"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ui_language"] == "fr"
    assert payload["analysis_language"] == "en"
    assert payload["rationale_language"] == "en"
