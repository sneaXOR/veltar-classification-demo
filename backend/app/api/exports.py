from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import ClassificationResult


router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("")
async def export_results(
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    results = list(await db.scalars(select(ClassificationResult)))
    if format == "json":
        payload = [
            {
                "document_id": str(result.document_id),
                "final_marking": result.final_marking,
                "confidence": result.final_confidence,
                "requires_human_review": result.requires_human_review,
                "experimental": result.experimental,
                "veltar_projection": result.veltar_projection,
            }
            for result in results
        ]
        return Response(content=json.dumps(payload, indent=2), media_type="application/json")

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "document_id",
            "final_marking",
            "confidence",
            "requires_human_review",
            "experimental",
            "classification_code",
            "jurisdictions",
            "eccn_scope",
        ],
    )
    writer.writeheader()
    for result in results:
        projection = result.veltar_projection or {}
        writer.writerow(
            {
                "document_id": str(result.document_id),
                "final_marking": result.final_marking,
                "confidence": result.final_confidence,
                "requires_human_review": result.requires_human_review,
                "experimental": result.experimental,
                "classification_code": projection.get("classification_code"),
                "jurisdictions": ",".join(projection.get("jurisdictions", [])),
                "eccn_scope": ",".join(projection.get("eccn_scope", [])),
            }
        )
    return Response(content=output.getvalue(), media_type="text/csv")
