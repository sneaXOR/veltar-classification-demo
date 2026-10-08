from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import ClassificationJob
from app.schemas.api import JobResponse
from app.services.classification.job_runner import extract_job_progress


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)) -> JobResponse:
    job = await db.scalar(select(ClassificationJob).where(ClassificationJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobResponse(
        id=job.id,
        document_id=job.document_id,
        status=job.status,
        model_name=job.model_name,
        runtime_name=job.runtime_name,
        duration_ms=job.duration_ms,
        error_message=job.error_message,
        gate_report=job.gate_report,
        progress=extract_job_progress(job.gate_report),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
