"""
Structured logging configuration
"""
import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

from config.settings import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with PII redaction."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pii_fields = set(settings.log_pii_fields)

    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record["timestamp"] = self.formatTime(record)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name

        # Add request context if available
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id

        # Redact PII
        self._redact_pii(log_record)

    def _redact_pii(self, log_record: dict[str, Any]) -> None:
        """Redact PII fields from log record."""
        for key in list(log_record.keys()):
            if any(pii_field in key.lower() for pii_field in self.pii_fields):
                log_record[key] = "[REDACTED]"

            # Also check nested dicts
            if isinstance(log_record[key], dict):
                self._redact_nested_pii(log_record[key])

    def _redact_nested_pii(self, obj: dict[str, Any]) -> None:
        for key in list(obj.keys()):
            if any(pii_field in key.lower() for pii_field in self.pii_fields):
                obj[key] = "[REDACTED]"
            elif isinstance(obj[key], dict):
                self._redact_nested_pii(obj[key])


def setup_logging() -> None:
    """Configure structured logging."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)

    if settings.log_format == "json":
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s",
            rename_fields={"levelname": "level"},
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Reduce noise from third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)
