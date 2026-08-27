"""
Product Intelligence API - FastAPI Application
"""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from api.middleware import (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
)
from api.routes import anomalies, experiments, feedback, health, investigations, metrics, sql
from config.settings import settings
from db.connection import close_db, init_db_async
from observability.logging import setup_logging
from observability.metrics import setup_metrics
from observability.tracing import setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_logging()
    setup_metrics()
    setup_tracing()

    # Initialize database
    await init_db_async()

    yield

    # Shutdown
    await close_db()


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Product Intelligence API",
        description="Autonomous Product Intelligence & Decision Engine",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Custom middleware (order matters - first added = outermost)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Prometheus metrics endpoint
    @app.get("/prometheus/metrics", include_in_schema=False)
    async def metrics_endpoint():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # Health check (no auth required)
    app.include_router(health.router, tags=["health"])

    # API routes
    app.include_router(investigations.router, prefix="/investigations", tags=["investigations"])
    app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
    app.include_router(anomalies.router, prefix="/anomalies", tags=["anomalies"])
    app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
    app.include_router(sql.router, prefix="/sql", tags=["sql"])
    app.include_router(experiments.router, prefix="/experiments", tags=["experiments"])

    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": settings.app_name,
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs" if settings.is_development else "disabled in production",
        }

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "request_id": request_id,
                "message": str(exc) if settings.is_development else "An unexpected error occurred",
            },
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers if not settings.is_development else 1,
        reload=settings.is_development,
    )
