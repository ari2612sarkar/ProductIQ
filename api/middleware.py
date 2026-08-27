"""
API Middleware for Product Intelligence
"""
import time
import uuid
from collections.abc import Callable

from prometheus_client import Counter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from config.settings import settings
from observability.logging import get_logger
from observability.metrics import http_request_duration_seconds, http_requests_total

logger = get_logger(__name__)

# Metrics
RATE_LIMIT_EXCEEDED = Counter("rate_limit_exceeded_total", "Rate limit exceeded count")
ERROR_COUNT = Counter("http_errors_total", "HTTP error count", ["status_code", "endpoint"])


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to all requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Structured request/response logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        request_id = getattr(request.state, "request_id", "unknown")

        # Log request
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": request.client.host if request.client else None,
            }
        )

        try:
            response = await call_next(request)

            # Log response
            duration = time.time() - start_time
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                }
            )

            # Record metrics
            http_requests_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()

            http_request_duration_seconds.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration_ms": round(duration * 1000, 2),
                },
                exc_info=True
            )

            ERROR_COUNT.labels(status_code=500, endpoint=request.url.path).inc()
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting (use Redis in production)."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.requests = {}  # In production, use Redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.rate_limit_requests:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"
        now = time.time()

        # Clean old entries
        self.requests = {k: v for k, v in self.requests.items() if v > now - settings.rate_limit_window}

        # Check rate limit
        count = len([v for v in self.requests.values() if v > now - settings.rate_limit_window])

        if count >= settings.rate_limit_requests:
            RATE_LIMIT_EXCEEDED.inc()
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": settings.rate_limit_window,
                },
                headers={"Retry-After": str(settings.rate_limit_window)}
            )

        self.requests[key] = now
        return await call_next(request)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Global error handling with structured responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except HTTPException:
            raise
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Validation error",
                    "message": str(e),
                    "request_id": getattr(request.state, "request_id", "unknown"),
                }
            )
        except PermissionError as e:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Permission denied",
                    "message": str(e),
                    "request_id": getattr(request.state, "request_id", "unknown"),
                }
            )
        except Exception:
            # Log the full error
            logger.exception(
                "Unhandled exception",
                extra={
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "path": request.url.path,
                }
            )

            if settings.is_development:
                raise

            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                    "request_id": getattr(request.state, "request_id", "unknown"),
                }
            )


# Import HTTPException here to avoid circular import
from fastapi import HTTPException
