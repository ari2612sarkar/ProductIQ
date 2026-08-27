"""
Metrics API endpoints
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.responses import AnomalyResponse, MetricHistoryResponse, MetricResponse
from db.connection import get_db
from db.schema.models import Anomaly, MetricSnapshot

router = APIRouter()


@router.get("", response_model=list[MetricResponse])
async def get_current_metrics(
    metric_names: list[str] | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get current metric values."""
    # Get latest snapshot for each metric
    subquery = (
        select(
            MetricSnapshot.metric_name,
            func.max(MetricSnapshot.period_end).label("latest_period")
        )
        .group_by(MetricSnapshot.metric_name)
        .subquery()
    )

    query = (
        select(MetricSnapshot)
        .join(
            subquery,
            (MetricSnapshot.metric_name == subquery.c.metric_name) &
            (MetricSnapshot.period_end == subquery.c.latest_period)
        )
    )

    if metric_names:
        query = query.where(MetricSnapshot.metric_name.in_(metric_names))

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{metric_name}/history", response_model=MetricHistoryResponse)
async def get_metric_history(
    metric_name: str,
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    interval: str = Query("1 day", regex="^(1 hour|1 day|1 week|1 month)$"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Get metric time series history."""
    if not end_date:
        latest_period_query = select(func.max(MetricSnapshot.period_end)).where(
            MetricSnapshot.metric_name == metric_name
        )
        latest_period_result = await db.execute(latest_period_query)
        latest_period_end = latest_period_result.scalar_one_or_none()
        end_date = latest_period_end or datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    query = (
        select(MetricSnapshot)
        .where(
            MetricSnapshot.metric_name == metric_name,
            MetricSnapshot.period_start >= start_date,
            MetricSnapshot.period_end <= end_date,
        )
        .order_by(desc(MetricSnapshot.period_start))
        .limit(limit)
    )

    result = await db.execute(query)
    snapshots = result.scalars().all()

    return MetricHistoryResponse(
        metric_name=metric_name,
        data=[{"timestamp": s.period_start, "value": float(s.value)} for s in reversed(snapshots)],
        interval=interval,
    )


@router.get("/anomalies", response_model=list[AnomalyResponse])
async def get_anomalies(
    metric_name: str | None = Query(None),
    severity: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    acknowledged: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get detected anomalies."""
    query = select(Anomaly).order_by(desc(Anomaly.detected_at))

    if metric_name:
        query = query.where(Anomaly.metric_name == metric_name)
    if severity:
        query = query.where(Anomaly.severity == severity)
    if start_date:
        query = query.where(Anomaly.detected_at >= start_date)
    if end_date:
        query = query.where(Anomaly.detected_at <= end_date)
    if acknowledged is not None:
        if acknowledged:
            query = query.where(Anomaly.acknowledged_at.is_not(None))
        else:
            query = query.where(Anomaly.acknowledged_at.is_(None))

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
