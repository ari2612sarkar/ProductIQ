"""
Feedback API endpoints
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.requests import FeedbackSearchRequest
from api.models.responses import FeedbackItem, FeedbackSearchResponse, SupportTicketResponse
from db.connection import get_db
from db.schema.models import ProductFeedback, SupportTicket

router = APIRouter()


@router.post("/search", response_model=FeedbackSearchResponse)
async def search_feedback(
    request: FeedbackSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Semantic search over product feedback (placeholder - uses text search for now)."""
    # TODO: Implement actual vector search with pgvector/Qdrant
    # For now, use PostgreSQL full-text search

    query = select(ProductFeedback).order_by(desc(ProductFeedback.created_at))

    if request.query:
        # Simple text search
        query = query.where(
            ProductFeedback.text.ilike(f"%{request.query}%")
        )

    if request.source:
        query = query.where(ProductFeedback.source == request.source)

    if request.sentiment:
        query = query.where(ProductFeedback.sentiment == request.sentiment)

    if request.product_area:
        query = query.where(ProductFeedback.product_area == request.product_area)

    if request.start_date:
        query = query.where(ProductFeedback.created_at >= request.start_date)

    if request.end_date:
        query = query.where(ProductFeedback.created_at <= request.end_date)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Paginate
    query = query.offset((request.page - 1) * request.page_size).limit(request.page_size)
    result = await db.execute(query)
    feedback_items = result.scalars().all()

    return FeedbackSearchResponse(
        items=[FeedbackItem.from_orm(f) for f in feedback_items],
        total=total,
        page=request.page,
        page_size=request.page_size,
        query=request.query,
    )


@router.get("/tickets", response_model=list[SupportTicketResponse])
async def list_support_tickets(
    user_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List support tickets."""
    query = select(SupportTicket).order_by(desc(SupportTicket.created_at))

    if user_id:
        query = query.where(SupportTicket.user_id == user_id)
    if status:
        query = query.where(SupportTicket.status == status)
    if category:
        query = query.where(SupportTicket.category == category)
    if priority:
        query = query.where(SupportTicket.priority == priority)

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/tickets/{ticket_id}", response_model=SupportTicketResponse)
async def get_support_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get support ticket by ID."""
    query = select(SupportTicket).where(SupportTicket.id == ticket_id)
    result = await db.execute(query)
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")

    return SupportTicketResponse.from_orm(ticket)
