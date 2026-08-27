"""
Health check endpoints
"""
import asyncio
import importlib.util
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agents.sql_agent.validator import SQLValidator
from config.settings import settings
from db.connection import get_db, readonly_engine

router = APIRouter()


@router.get("/health", tags=["health"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "0.1.0",
    }


@router.get("/ready", tags=["health"])
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check - verifies database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
        }
    except Exception as e:
        return {
            "status": "not ready",
            "database": "disconnected",
            "error": str(e),
        }


@router.get("/live", tags=["health"])
async def liveness_check():
    """Liveness check for Kubernetes."""
    return {"status": "alive"}


def _llm_config_check() -> tuple[bool, dict]:
    provider = settings.llm_provider
    if provider == "openrouter":
        ok = bool(settings.openrouter_api_key)
        return ok, {
            "provider": provider,
            "api_key_present": ok,
            "model": settings.llm_model,
        }

    ok = bool(settings.openai_api_key)
    return ok, {
        "provider": provider,
        "api_key_present": ok,
        "model": settings.llm_model,
    }


def _vector_store_check() -> tuple[bool, dict]:
    if settings.vector_db_type == "qdrant":
        if not settings.qdrant_url:
            return False, {
                "vector_db_type": "qdrant",
                "configured": False,
                "reason": "QDRANT_URL is missing",
            }

        try:
            with urlopen(f"{settings.qdrant_url.rstrip('/')}/collections", timeout=3) as response:
                ok = 200 <= response.status < 300
                return ok, {
                    "vector_db_type": "qdrant",
                    "configured": True,
                    "reachable": ok,
                    "status_code": response.status,
                }
        except URLError as error:
            return False, {
                "vector_db_type": "qdrant",
                "configured": True,
                "reachable": False,
                "error": str(error),
            }

    return bool(settings.vector_db_url), {
        "vector_db_type": settings.vector_db_type,
        "configured": bool(settings.vector_db_url),
    }


def _readonly_db_check() -> tuple[bool, dict]:
    try:
        with readonly_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, {"connected": True}
    except Exception as error:
        return False, {"connected": False, "error": str(error)}


def _sql_validator_check() -> tuple[bool, dict]:
    try:
        validator = SQLValidator()
        valid = validator.validate("SELECT 1")
        blocked = validator.validate("SELECT pg_sleep(1)")
        ok = valid.is_valid and (not blocked.is_valid)
        return ok, {
            "select_check": valid.is_valid,
            "dangerous_function_blocked": not blocked.is_valid,
            "forbidden_keywords_count": len(validator.forbidden_keywords),
            "max_joins": validator.max_joins,
            "max_subqueries": validator.max_subqueries,
        }
    except Exception as error:
        return False, {"error": str(error)}


@router.get("/health/agents", tags=["health"])
async def agents_health_check(db: AsyncSession = Depends(get_db)):
    """Readiness matrix for SQL and agent dependencies."""
    checks: dict[str, dict] = {}

    # API database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"ok": True, "details": {"connected": True}}
    except Exception as error:
        checks["database"] = {"ok": False, "details": {"connected": False, "error": str(error)}}

    # Read-only DB used by SQL endpoint
    readonly_ok, readonly_details = await asyncio.to_thread(_readonly_db_check)
    checks["readonly_database"] = {"ok": readonly_ok, "details": readonly_details}

    # SQL validator + guardrails
    validator_ok, validator_details = _sql_validator_check()
    checks["sql_validator"] = {"ok": validator_ok, "details": validator_details}

    checks["sql_route"] = {
        "ok": bool(settings.sql_forbidden_keywords_list) and settings.sql_max_rows > 0,
        "details": {
            "forbidden_keywords_count": len(settings.sql_forbidden_keywords_list),
            "sql_max_rows": settings.sql_max_rows,
            "sql_timeout_seconds": settings.sql_query_timeout,
        },
    }

    # LLM + vector dependencies for non-SQL agents
    llm_ok, llm_details = _llm_config_check()
    checks["llm"] = {"ok": llm_ok, "details": llm_details}

    vector_ok, vector_details = _vector_store_check()
    checks["vector_store"] = {"ok": vector_ok, "details": vector_details}

    # Optional background worker presence
    worker_spec = importlib.util.find_spec("scripts.background_worker")
    checks["background_worker_module"] = {
        "ok": worker_spec is not None,
        "details": {"module_found": worker_spec is not None},
    }

    overall_ok = all(item["ok"] for item in checks.values())

    return {
        "status": "healthy" if overall_ok else "degraded",
        "service": settings.app_name,
        "checks": checks,
    }
