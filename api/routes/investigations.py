"""
Investigations API endpoints
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.requests import InvestigationCreateRequest
from api.models.responses import (
    InvestigationListResponse,
    InvestigationResponse,
    InvestigationSummary,
    RecommendationResponse,
    SQLQueryResponse,
)
from db.connection import get_db
from db.schema.models import Investigation, InvestigationSQLQuery, Recommendation

router = APIRouter()


@router.post("", response_model=InvestigationResponse, status_code=status.HTTP_201_CREATED)
async def create_investigation(
    request: InvestigationCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new investigation."""
    investigation = Investigation(
        id=uuid.uuid4(),
        question=request.question,
        trigger_type=request.trigger or "manual",
        status="pending",
        anomaly_id=request.anomaly_id,
        metadata_=request.metadata or {},
    )

    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    # TODO: Trigger async investigation via background worker
    # For now, return the created investigation

    return InvestigationResponse.from_orm(investigation)


@router.get("", response_model=InvestigationListResponse)
async def list_investigations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    trigger: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List investigations with pagination and filtering."""
    query = select(Investigation).order_by(desc(Investigation.created_at))

    if status:
        query = query.where(Investigation.status == status)
    if trigger:
        query = query.where(Investigation.trigger_type == trigger)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    investigations = result.scalars().all()

    return InvestigationListResponse(
        items=[InvestigationSummary.from_orm(inv) for inv in investigations],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(
    investigation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get investigation by ID with all related data."""
    query = (
        select(Investigation)
        .options(
            selectinload(Investigation.sql_queries),
            selectinload(Investigation.recommendations),
            selectinload(Investigation.anomaly),
        )
        .where(Investigation.id == investigation_id)
    )
    result = await db.execute(query)
    investigation = result.scalar_one_or_none()

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return InvestigationResponse.from_orm(investigation)


@router.get("/{investigation_id}/sql-queries", response_model=list[SQLQueryResponse])
async def get_investigation_sql_queries(
    investigation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all SQL queries for an investigation."""
    query = select(InvestigationSQLQuery).where(
        InvestigationSQLQuery.investigation_id == investigation_id
    ).order_by(InvestigationSQLQuery.step_number)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{investigation_id}/recommendations", response_model=list[RecommendationResponse])
async def get_investigation_recommendations(
    investigation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all recommendations for an investigation."""
    query = select(Recommendation).where(
        Recommendation.investigation_id == investigation_id
    ).order_by(desc(Recommendation.rice_score))
    result = await db.execute(query)
    return result.scalars().all()
