"""
OpenTelemetry tracing configuration
"""
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

from config.settings import settings


def setup_tracing(app=None) -> trace.Tracer:
    """Configure OpenTelemetry tracing."""

    # Create resource
    resource = Resource.create({
        SERVICE_NAME: settings.otel_service_name,
        "deployment.environment": settings.app_env,
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.otel_endpoint,
        insecure=True,
    )

    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Set global tracer provider
    trace.set_tracer_provider(provider)

    # Get tracer
    tracer = trace.get_tracer(__name__)

    # Auto-instrument if app provided
    if app:
        FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument()
        RedisInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()

    return tracer


def get_tracer(name: str) -> trace.Tracer:
    """Get tracer instance."""
    return trace.get_tracer(name)


def create_span(name: str, attributes: dict = None):
    """Context manager for creating spans."""
    tracer = get_tracer(__name__)
    return tracer.start_as_current_span(name, attributes=attributes or {})


def add_span_attributes(attributes: dict) -> None:
    """Add attributes to current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def record_exception(exc: Exception) -> None:
    """Record exception in current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, str(exc)))
