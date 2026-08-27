"""
Experiments API endpoints
"""
import asyncio
import math
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.requests import ExperimentAnalysisRequest
from api.models.responses import ExperimentAnalysisResponse, ExperimentResponse
from agents.experiment_agent.analyzer import analyze_experiment_simple
from db.connection import get_db
from db.schema.models import Experiment, ExperimentAssignment

router = APIRouter()


@router.get("", response_model=list[ExperimentResponse])
async def list_experiments(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List experiments."""
    query = select(Experiment).order_by(desc(Experiment.started_at))

    if status:
        query = query.where(Experiment.status == status)

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get experiment by ID."""
    query = select(Experiment).where(Experiment.id == experiment_id)
    result = await db.execute(query)
    experiment = result.scalar_one_or_none()

    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return ExperimentResponse.from_orm(experiment)


@router.get("/{experiment_id}/assignments")
async def get_experiment_assignments(
    experiment_id: uuid.UUID,
    variant: str | None = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Get experiment assignments."""
    query = select(ExperimentAssignment).where(
        ExperimentAssignment.experiment_id == experiment_id
    )

    if variant:
        query = query.where(ExperimentAssignment.variant == variant)

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/analyze", response_model=ExperimentAnalysisResponse)
async def analyze_experiment(
    request: ExperimentAnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    """Analyze an A/B experiment with statistical tests."""
    experiment = await db.get(Experiment, request.experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    metric_type = request.metric_type
    if not metric_type:
        metric_type_map = {
            "conversion": "proportion",
            "activation": "proportion",
            "retention": "proportion",
            "revenue": "mean",
        }
        metric_type = metric_type_map.get(request.metric, "proportion")

    def run_analysis() -> dict:
        from db.connection import get_sync_session

        with get_sync_session() as sync_db:
            return analyze_experiment_simple(
                session=sync_db,
                experiment_id=str(request.experiment_id),
                metric=request.metric,
                metric_type=metric_type,
            )

    analysis = await asyncio.to_thread(run_analysis)

    if "error" in analysis:
        raise HTTPException(status_code=400, detail=analysis["error"])

    confidence_interval = analysis.get("effect_size_ci") or analysis.get("confidence_interval") or [0, 0]
    warnings = list(analysis.get("warnings") or [])

    def _finite_number(value: object, default: float) -> float:
        try:
            number = float(value)
            return number if math.isfinite(number) else default
        except (TypeError, ValueError):
            return default

    effect_size = _finite_number(analysis.get("effect_size"), 0.0)
    p_value = _finite_number(analysis.get("p_value"), 1.0)
    ci_low = _finite_number(confidence_interval[0] if len(confidence_interval) > 0 else 0.0, 0.0)
    ci_high = _finite_number(confidence_interval[1] if len(confidence_interval) > 1 else 0.0, 0.0)
    achieved_power = analysis.get("achieved_power")
    achieved_power_value = _finite_number(achieved_power, 0.0) if achieved_power is not None else None

    if p_value == 1.0 and analysis.get("p_value") not in (1, 1.0, "1", Decimal("1")):
        warnings.append("P-value was non-finite and has been normalized to 1.0")

    return ExperimentAnalysisResponse(
        experiment_id=request.experiment_id,
        metric=request.metric,
        control=analysis.get("control", {}),
        treatment=analysis.get("treatment", {}),
        effect_size=Decimal(str(effect_size)),
        confidence_interval=[Decimal(str(ci_low)), Decimal(str(ci_high))],
        p_value=Decimal(str(p_value)),
        statistically_significant=bool(analysis.get("statistically_significant", False)),
        interpretation=analysis.get("interpretation", "No interpretation available"),
        confidence_level=Decimal(str(analysis.get("confidence_level"))) if analysis.get("confidence_level") is not None else None,
        test_used=analysis.get("test_used"),
        assumptions_met=analysis.get("assumptions_met"),
        warnings=warnings,
        achieved_power=Decimal(str(achieved_power_value)) if achieved_power_value is not None else None,
        analysis_source="real",
        analyzed_at=datetime.fromisoformat(analysis["analyzed_at"]) if analysis.get("analyzed_at") else datetime.utcnow(),
    )
