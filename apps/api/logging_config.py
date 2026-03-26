"""Structured logging configuration with OpenTelemetry-ready handlers."""

import logging
import sys

import structlog
from opentelemetry import trace

from apps.api.config import settings


def add_otel_trace_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Inject OpenTelemetry span and trace IDs into every log record.

    Args:
        logger: The logger instance.
        method_name: The name of the log method called.
        event_dict: The current structured log event dictionary.

    Returns:
        The enriched event dictionary with trace context fields.
    """
    span = trace.get_current_span()
    span_context = span.get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


def setup_logging() -> None:
    """Configure structlog with OpenTelemetry trace context injection.

    Sets up structured JSON logging to stdout with trace/span ID enrichment
    so that logs can be correlated with distributed traces once an
    OpenTelemetry exporter is wired in.
    """
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_otel_trace_context,
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ]
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structured logger instance.

    Args:
        name: The logger name, typically the module path.

    Returns:
        A bound structlog logger with the given name.
    """
    return structlog.get_logger(name)
