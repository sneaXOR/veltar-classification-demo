from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Document
from app.models.enums import ArtifactStatus

router = APIRouter(prefix="/documents", tags=["artifacts"])


def _media_type_for(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".eml": "message/rfc822",
    }.get(ext, "application/octet-stream")


async def _get_document(document_id: UUID, db: AsyncSession) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    return document


@router.get("/{document_id}/artifact/download")
async def download_marked_artifact(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download the marked (classified) version of the document."""
    document = await _get_document(document_id, db)
    if document.artifact_status != ArtifactStatus.READY:
        raise HTTPException(status_code=409, detail="Le document marque n'est pas encore disponible.")
    if not document.marked_artifact_path or not Path(document.marked_artifact_path).is_file():
        raise HTTPException(status_code=404, detail="Fichier marque introuvable sur le disque.")
    return FileResponse(
        path=document.marked_artifact_path,
        media_type=_media_type_for(document.original_filename),
        filename=document.original_filename,
    )


@router.get("/{document_id}/artifact/original")
async def download_original_snapshot(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download the original (pre-marking) snapshot of the document."""
    document = await _get_document(document_id, db)
    if not document.original_snapshot_path or not Path(document.original_snapshot_path).is_file():
        raise HTTPException(status_code=404, detail="Snapshot original introuvable.")
    return FileResponse(
        path=document.original_snapshot_path,
        media_type=_media_type_for(document.original_filename),
        filename=f"original_{document.original_filename}",
    )
