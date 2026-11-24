"""Structured logging and OpenTelemetry distributed tracing for Bacen Fintech Advisor."""

from .logging import CloudJsonFormatter, PiiRedactionFilter, configure_logging, get_logger
from .tracing import (
    CONTENT_CAPTURE_DEFAULTS,
    apply_privacy_defaults,
    configure_tracing,
    current_trace_context,
    get_tracer,
)

__all__ = [
    "CONTENT_CAPTURE_DEFAULTS",
    "CloudJsonFormatter",
    "PiiRedactionFilter",
    "apply_privacy_defaults",
    "configure_logging",
    "configure_tracing",
    "current_trace_context",
    "get_logger",
    "get_tracer",
]
