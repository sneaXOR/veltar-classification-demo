from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Batch, ClassificationJob, ClassificationResult, Document, ReviewRecord
from app.models.enums import ReviewStatus
from app.schemas.api import DashboardResponse


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(db: AsyncSession = Depends(get_db)) -> DashboardResponse:
    documents = list(await db.scalars(select(Document)))
    jobs = list(await db.scalars(select(ClassificationJob)))
    reviews = list(await db.scalars(select(ReviewRecord)))
    results = list(await db.scalars(select(ClassificationResult)))
    batches = list(await db.scalars(select(Batch)))

    by_marking = Counter(result.final_marking for result in results)
    by_status = Counter(document.status.value for document in documents)
    return DashboardResponse(
        total_documents=len(documents),
        completed_documents=sum(1 for document in documents if document.status.value == "completed"),
        pending_reviews=sum(1 for review in reviews if review.status == ReviewStatus.PENDING),
        failed_jobs=sum(1 for job in jobs if job.status.value == "failed"),
        batches=len(batches),
        by_marking=dict(by_marking),
        by_status=dict(by_status),
    )
