"""
SQL Query API endpoints (protected)
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import verify_api_key
from api.models.requests import SQLQueryRequest
from api.models.responses import SQLQueryResponse
from db.connection import get_db, get_readonly_db
from db.schema.models import InvestigationSQLQuery

router = APIRouter()


@router.post("/query", response_model=SQLQueryResponse, dependencies=[Depends(verify_api_key)])
async def execute_sql_query(
    request: SQLQueryRequest,
    db: AsyncSession = Depends(get_readonly_db),
):
    """Execute a validated read-only SQL query."""
    import time

    import sqlglot

    from db.connection import settings

    start_time = time.time()

    # Validate SQL
    try:
        parsed = sqlglot.parse_one(request.sql, dialect="postgres")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"SQL parse error: {e!s}"
        )

    # Check for forbidden operations
    forbidden_keywords = settings.sql_forbidden_keywords_list
    sql_upper = request.sql.upper()
    for keyword in forbidden_keywords:
        if keyword in sql_upper:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden SQL operation: {keyword}"
            )

    # Check complexity
    # Count joins (simplified)
    join_count = sql_upper.count(" JOIN ")
    if join_count > settings.sql_max_joins:
        raise HTTPException(
            status_code=400,
            detail=f"Too many joins: {join_count} (max: {settings.sql_max_joins})"
        )

    # Execute with timeout
    try:
        # Set statement timeout
        await db.execute(text(f"SET LOCAL statement_timeout = {settings.sql_query_timeout * 1000}"))

        result = await db.execute(text(request.sql))
        rows = result.fetchall()

        # Convert to list of dicts
        columns = result.keys()
        data = [dict(zip(columns, row)) for row in rows]

        # Limit rows
        if len(data) > settings.sql_max_rows:
            data = data[:settings.sql_max_rows]
            truncated = True
        else:
            truncated = False

        execution_time = int((time.time() - start_time) * 1000)

        return SQLQueryResponse(
            columns=list(columns),
            data=data,
            row_count=len(data),
            truncated=truncated,
            execution_time_ms=execution_time,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"SQL execution error: {e!s}"
        )


@router.get("/investigations/{investigation_id}/queries", response_model=list[SQLQueryResponse])
async def get_investigation_queries(
    investigation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all SQL queries executed during an investigation."""
    query = select(InvestigationSQLQuery).where(
        InvestigationSQLQuery.investigation_id == investigation_id
    ).order_by(InvestigationSQLQuery.step_number)
    result = await db.execute(query)
    return result.scalars().all()
