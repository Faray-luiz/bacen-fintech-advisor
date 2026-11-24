"""Server-side intent vs. outcome middleware for every MCP ``tools/call``.

Mirrors ``bacen_advisor/plugins/observability.py`` on the Cloud Run side:
emits ``mcp_tool_intent`` before execution and ``mcp_tool_outcome`` after, carrying
``request_id``, latency, returned rows and ``data_origin`` (live BCB HTTP, RAM cache
or embedded seed fallback), while annotating the active OpenTelemetry server span.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from opentelemetry import trace
from pydantic import BaseModel

logger = logging.getLogger("mcp_bacen.audit")


def summarize_result(result: HandlerResult) -> dict[str, Any]:
    """Extracts status, row count and effective data origin from a ``tools/call`` result."""
    is_error = False
    structured: Any = None
    if isinstance(result, BaseModel):
        is_error = bool(getattr(result, "is_error", False))
        structured = getattr(result, "structured_content", None)
    elif isinstance(result, dict):
        is_error = bool(result.get("isError"))
        structured = result.get("structuredContent")
    registros = structured.get("registros") if isinstance(structured, dict) else None
    fonte = structured.get("metadados_fonte") if isinstance(structured, dict) else None
    return {
        "status": "error" if is_error else "success",
        "records_returned": len(registros) if isinstance(registros, list) else None,
        "data_origin": fonte.get("origem_leitura") if isinstance(fonte, dict) else None,
    }


class ObservabilityMiddleware:
    """MCP server middleware emitting ``mcp_tool_intent`` / ``mcp_tool_outcome``."""

    async def __call__(self, ctx: ServerRequestContext[Any, Any], call_next: CallNext) -> HandlerResult:
        if ctx.method != "tools/call":
            return await call_next(ctx)

        params = ctx.params or {}
        tool = str(params.get("name"))
        base = {
            "tool": tool,
            "request_id": str(ctx.request_id) if ctx.request_id is not None else None,
            "protocol_version": ctx.protocol_version,
        }
        span = trace.get_current_span()
        span.add_event("mcp_tool_intent", {"tool": tool})
        logger.info(
            "mcp_tool_intent",
            extra={"event": "mcp_tool_intent", "intended_args": dict(params.get("arguments") or {}), **base},
        )

        started = time.perf_counter()
        try:
            result = await call_next(ctx)
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            span.add_event("mcp_tool_outcome", {"tool": tool, "status": "exception"})
            logger.error(
                "mcp_tool_outcome",
                extra={
                    "event": "mcp_tool_outcome",
                    "status": "exception",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "latency_ms": latency_ms,
                    **base,
                },
            )
            raise

        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        summary = summarize_result(result)
        attributes: dict[str, Any] = {"bacen.mcp.status": summary["status"], "bacen.mcp.latency_ms": latency_ms}
        if summary["records_returned"] is not None:
            attributes["bacen.mcp.records_returned"] = summary["records_returned"]
        if summary["data_origin"]:
            attributes["bacen.mcp.data_origin"] = summary["data_origin"]
        span.set_attributes(attributes)
        span.add_event("mcp_tool_outcome", {"tool": tool, "status": summary["status"]})
        logger.log(
            logging.ERROR if summary["status"] == "error" else logging.INFO,
            "mcp_tool_outcome",
            extra={"event": "mcp_tool_outcome", "latency_ms": latency_ms, **summary, **base},
        )
        return result
