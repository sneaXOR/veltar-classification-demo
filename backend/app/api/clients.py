from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.client import ClientProfile, normalize_country_code
from app.schemas.api import ClientProfileCreate, ClientProfileResponse, ClientProfileUpdate

router = APIRouter(prefix="/clients", tags=["clients"])

COUNTRY_TO_REGULATORY_SCOPE = {
    "FR": ["FR_ML", "EU_DU"],
    "DE": ["DE_ML", "EU_DU"],
    "IT": ["IT_ML", "EU_DU"],
    "ES": ["ES_ML", "EU_DU"],
    "GB": ["UK_ML", "UK_DU"],
    "US": ["ITAR", "EAR"],
}


def _compute_regulatory_scope(country: str) -> list[str]:
    country_upper = normalize_country_code(country)
    if country_upper in COUNTRY_TO_REGULATORY_SCOPE:
        return COUNTRY_TO_REGULATORY_SCOPE[country_upper]
    # Default EU member states to their ML + EU DU
    return [f"{country_upper}_ML", "EU_DU"]


@router.post("", response_model=ClientProfileResponse, status_code=201)
async def create_client(
    body: ClientProfileCreate,
    db: AsyncSession = Depends(get_db),
) -> ClientProfile:
    profile = ClientProfile(
        name=body.name,
        country=body.country.upper(),
        activity_description=body.activity_description,
        product_families=body.product_families,
        product_characteristics=body.product_characteristics,
        program_names=body.program_names,
        naming_conventions=body.naming_conventions,
        classification_history=body.classification_history,
        regulatory_scope=_compute_regulatory_scope(body.country),
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("", response_model=list[ClientProfileResponse])
async def list_clients(db: AsyncSession = Depends(get_db)) -> list[ClientProfile]:
    result = await db.scalars(select(ClientProfile).order_by(ClientProfile.name))
    return list(result)


@router.get("/{client_id}", response_model=ClientProfileResponse)
async def get_client(client_id: UUID, db: AsyncSession = Depends(get_db)) -> ClientProfile:
    profile = await db.get(ClientProfile, client_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Client profile not found.")
    return profile


@router.put("/{client_id}", response_model=ClientProfileResponse)
async def update_client(
    client_id: UUID,
    body: ClientProfileUpdate,
    db: AsyncSession = Depends(get_db),
) -> ClientProfile:
    profile = await db.get(ClientProfile, client_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Client profile not found.")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    if "country" in update_data:
        profile.country = profile.country.upper()
        profile.regulatory_scope = _compute_regulatory_scope(profile.country)

    await db.commit()
    await db.refresh(profile)
    return profile


@router.delete("/{client_id}", status_code=204, response_class=Response)
async def delete_client(client_id: UUID, db: AsyncSession = Depends(get_db)) -> Response:
    profile = await db.get(ClientProfile, client_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Client profile not found.")
    await db.delete(profile)
    await db.commit()
    return Response(status_code=204)
