from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import (
    LLMRuntimeSettingsResponse,
    LLMRuntimeUpdateRequest,
    LanguageSettingsResponse,
    LanguageSettingsUpdateRequest,
)
from app.services.classification.runtime_config import (
    get_active_runtime_profile,
    list_runtime_profiles,
    serialize_runtime_profile,
    set_active_runtime_profile,
)
from app.services.language_settings import (
    get_language_settings,
    serialize_language_settings,
    set_language_settings,
)


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/llm", response_model=LLMRuntimeSettingsResponse)
async def get_llm_runtime_settings() -> LLMRuntimeSettingsResponse:
    active_profile = get_active_runtime_profile()
    profiles = list_runtime_profiles()
    return LLMRuntimeSettingsResponse(
        active_profile_id=active_profile.id,
        active_profile=serialize_runtime_profile(active_profile),
        available_profiles=[serialize_runtime_profile(profile) for profile in profiles],
    )


@router.put("/llm", response_model=LLMRuntimeSettingsResponse)
async def update_llm_runtime_settings(payload: LLMRuntimeUpdateRequest) -> LLMRuntimeSettingsResponse:
    try:
        active_profile = set_active_runtime_profile(payload.profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    profiles = list_runtime_profiles()
    return LLMRuntimeSettingsResponse(
        active_profile_id=active_profile.id,
        active_profile=serialize_runtime_profile(active_profile),
        available_profiles=[serialize_runtime_profile(profile) for profile in profiles],
    )


@router.get("/language", response_model=LanguageSettingsResponse)
async def get_language_runtime_settings() -> LanguageSettingsResponse:
    return LanguageSettingsResponse(**serialize_language_settings(get_language_settings()))


@router.put("/language", response_model=LanguageSettingsResponse)
async def update_language_runtime_settings(payload: LanguageSettingsUpdateRequest) -> LanguageSettingsResponse:
    settings = set_language_settings(
        ui_language=payload.ui_language,
        analysis_language=payload.analysis_language,
        rationale_language=payload.rationale_language,
    )
    return LanguageSettingsResponse(**serialize_language_settings(settings))
