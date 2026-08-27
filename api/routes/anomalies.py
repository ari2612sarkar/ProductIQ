"""
Anomalies API endpoints
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.responses import AnomalyDetailResponse
from db.connection import get_db
from db.schema.models import Anomaly

router = APIRouter()


@router.get("/{anomaly_id}", response_model=AnomalyDetailResponse)
async def get_anomaly(
    anomaly_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get anomaly details by ID."""
    query = select(Anomaly).where(Anomaly.id == anomaly_id)
    result = await db.execute(query)
    anomaly = result.scalar_one_or_none()

    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    return AnomalyDetailResponse.from_orm(anomaly)


@router.post("/{anomaly_id}/acknowledge")
async def acknowledge_anomaly(
    anomaly_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge an anomaly."""
    query = select(Anomaly).where(Anomaly.id == anomaly_id)
    result = await db.execute(query)
    anomaly = result.scalar_one_or_none()

    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    anomaly.acknowledged_at = datetime.utcnow()
    await db.commit()

    return {"status": "acknowledged", "anomaly_id": str(anomaly_id)}


@router.post("/{anomaly_id}/resolve")
async def resolve_anomaly(
    anomaly_id: uuid.UUID,
    resolution_notes: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Resolve an anomaly."""
    query = select(Anomaly).where(Anomaly.id == anomaly_id)
    result = await db.execute(query)
    anomaly = result.scalar_one_or_none()

    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    anomaly.resolved_at = datetime.utcnow()
    if resolution_notes:
        anomaly.metadata_ = anomaly.metadata_ or {}
        anomaly.metadata_["resolution_notes"] = resolution_notes
    await db.commit()

    return {"status": "resolved", "anomaly_id": str(anomaly_id)}
