from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import ClassificationResult


router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/veltar/{document_id}")
async def get_veltar_projection(document_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    classification = await db.scalar(select(ClassificationResult).where(ClassificationResult.document_id == document_id))
    if not classification:
        raise HTTPException(status_code=404, detail="Classification not found.")
    return classification.veltar_projection
