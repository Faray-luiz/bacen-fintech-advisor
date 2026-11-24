"""OpenTelemetry distributed tracing for the Bacen MCP server (Cloud Trace).

The MCP Python SDK (2.x) automatically reads W3C ``traceparent`` from ``params._meta``
(injected by the ADK agent's ``McpToolset``) and opens a ``SERVER`` span for each
``tools/call``. Calling :func:`configure_tracing` exports those server spans to Cloud
Trace so the Cloud Run hop appears inside the exact same waterfall as the ADK agent.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from opentelemetry import trace

from src import __version__
from src.config import settings

logger = logging.getLogger(__name__)
_CONFIGURED = False


def tracing_enabled() -> bool:
    """True when spans must be exported (explicit flag, or auto on Cloud Run)."""
    if settings.enable_cloud_trace is not None:
        return settings.enable_cloud_trace
    return bool(os.getenv("K_SERVICE"))


def _resource():
    from opentelemetry.sdk.resources import Resource

    attributes: dict[str, Any] = {
        "service.name": settings.otel_service_name,
        "service.version": __version__,
        "deployment.environment": settings.environment,
    }
    if os.getenv("K_SERVICE"):
        attributes.update(
            {
                "cloud.provider": "gcp",
                "cloud.platform": "gcp_cloud_run",
                "faas.name": os.getenv("K_SERVICE", ""),
                "faas.version": os.getenv("K_REVISION", ""),
            }
        )
    resource = Resource.create(attributes)
    if os.getenv("K_SERVICE"):
        try:
            from opentelemetry.resourcedetector.gcp import GoogleCloudResourceDetector

            resource = GoogleCloudResourceDetector(raise_on_error=False).detect().merge(resource)
        except Exception as exc:  # noqa: BLE001
            logger.debug("gcp_resource_detection_skipped", extra={"error": str(exc)})
    return resource


def configure_tracing() -> None:
    """Registers a Cloud Trace exporter on the global tracer provider (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED or not tracing_enabled():
        return
    try:
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=_resource())
        provider.add_span_processor(
            BatchSpanProcessor(
                CloudTraceSpanExporter(project_id=settings.google_cloud_project or None),
                schedule_delay_millis=1000,
            )
        )
        trace.set_tracer_provider(provider)
        _CONFIGURED = True
        logger.info(
            "cloud_trace_enabled",
            extra={"event": "cloud_trace_enabled", "project_id": settings.google_cloud_project},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("cloud_trace_setup_failed", extra={"error": str(exc)})


def current_trace_context() -> dict[str, Any]:
    """Cloud Logging trace-correlation fields for the active span (empty if none)."""
    ctx = trace.get_current_span().get_span_context()
    if not ctx or not ctx.is_valid:
        return {}
    trace_id = f"{ctx.trace_id:032x}"
    project = settings.google_cloud_project
    return {
        "logging.googleapis.com/trace": f"projects/{project}/traces/{trace_id}" if project else trace_id,
        "logging.googleapis.com/spanId": f"{ctx.span_id:016x}",
        "logging.googleapis.com/trace_sampled": bool(ctx.trace_flags.sampled),
    }
