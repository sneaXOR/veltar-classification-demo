from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models import AuditEvent, ReviewRecord
from app.models.enums import AuditEventType, ReviewStatus
from app.schemas.api import ReviewResponse, ReviewUpdateRequest


router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/pending", response_model=list[ReviewResponse])
async def list_pending_reviews(db: AsyncSession = Depends(get_db)) -> list[ReviewRecord]:
    result = await db.scalars(
        select(ReviewRecord).where(ReviewRecord.status == ReviewStatus.PENDING).order_by(desc(ReviewRecord.created_at))
    )
    return list(result)


@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(review_id: UUID, payload: ReviewUpdateRequest, db: AsyncSession = Depends(get_db)) -> ReviewRecord:
    review = await db.scalar(
        select(ReviewRecord)
        .where(ReviewRecord.id == review_id)
        .options(selectinload(ReviewRecord.classification_result))
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    review.status = payload.status
    review.reviewer_name = payload.reviewer_name
    review.reviewer_note = payload.reviewer_note
    review.final_marking_override = payload.final_marking_override
    db.add(
        AuditEvent(
            document_id=review.classification_result.document_id,
            event_type=AuditEventType.REVIEW_UPDATED,
            payload=payload.model_dump(),
            message=f"Review {review.id} updated",
        )
    )
    await db.commit()
    await db.refresh(review)
    return review
