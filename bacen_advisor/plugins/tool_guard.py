"""Tool guard plugin: strict Pydantic schema validation and guided error recovery.

* ``before_tool_callback`` validates arguments sent to remote Bacen MCP tools against
  :data:`bacen_advisor.schemas.MCP_ARG_SCHEMAS`. Invalid calls are short-circuited
  without a network round-trip and return a descriptive ``recovery_hint``. Valid calls
  are normalized in place (e.g. ``'Nu Pagamentos'`` -> ``'NUBANK'``, ``'rotativo'`` ->
  ``'CARTAO_ROTATIVO'``).
* ``after_tool_callback`` validates the response shape via :class:`McpToolOutput` and
  attaches recovery guidance on malformed payloads, server errors or empty results.
* ``on_tool_error_callback`` converts transport/auth exceptions into structured error
  payloads instead of crashing the agent invocation.
"""

from __future__ import annotations

import json
from typing import Any

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from pydantic import ValidationError

from ..observability.logging import get_logger
from ..schemas import MCP_ARG_SCHEMAS, McpToolOutput

logger = get_logger(__name__)

_MAX_MCP_CALLS_PER_INVOCATION = 12


def _validation_hint(tool_name: str, exc: ValidationError) -> dict[str, Any]:
    problems = [
        f"{'.'.join(str(p) for p in err['loc']) or 'args'}: {err['msg']}" for err in exc.errors()
    ]
    return {
        "status": "error",
        "error_type": "invalid_arguments",
        "tool": tool_name,
        "error_message": "; ".join(problems),
        "recovery_hint": (
            "Fix the arguments and call the tool again. If unsure about canonical institution "
            "names, market segments or credit modalities, call list_supported_bacen_filters "
            "first. Never invent figures."
        ),
    }


def _recovery_for_exception(error: Exception) -> str:
    text = f"{type(error).__name__}: {error}".lower()
    if "401" in text or "403" in text or "unauthorized" in text or "forbidden" in text:
        return (
            "The Bacen MCP service rejected credentials. Do not retry. Inform the user "
            "that the data service is temporarily unavailable."
        )
    if "timeout" in text or "timed out" in text:
        return (
            "The Bacen MCP service timed out. Retry ONCE with a narrower query (specify "
            "instituicao, segmento or a smaller limite). If it fails again, tell the user."
        )
    if "connect" in text or "unavailable" in text or "503" in text:
        return "The Bacen MCP service is unreachable. Retry once; if it fails, inform the user."
    return "Unexpected tool failure. Do not retry with identical arguments; explain the limitation."


class ToolGuardPlugin(BasePlugin):
    """Validates tool arguments/outputs, prevents duplicate-call loops and guides recovery."""

    def __init__(self, *, max_calls_per_invocation: int = _MAX_MCP_CALLS_PER_INVOCATION) -> None:
        super().__init__(name="tool_guard")
        self._max_calls_per_invocation = max_calls_per_invocation
        self._seen_calls: dict[str, set[str]] = {}
        self._call_counts: dict[str, int] = {}

    async def before_tool_callback(
        self, *, tool: BaseTool, tool_args: dict[str, Any], tool_context: ToolContext
    ):
        schema = MCP_ARG_SCHEMAS.get(tool.name)
        if schema is None:
            return None
        try:
            validated = schema.model_validate(tool_args)
        except ValidationError as exc:
            logger.warning(
                "tool_args_rejected",
                extra={"tool": tool.name, "rejected_args": tool_args, "errors": exc.errors(include_url=False)},
            )
            return _validation_hint(tool.name, exc)

        normalized = validated.model_dump(exclude_none=True)
        inv_id = getattr(tool_context, "invocation_id", None)
        if inv_id:
            if len(self._seen_calls) > 2_000:
                self._seen_calls.clear()
                self._call_counts.clear()
            signature = f"{tool.name}:{json.dumps(normalized, sort_keys=True, ensure_ascii=False)}"
            seen = self._seen_calls.setdefault(inv_id, set())
            if signature in seen:
                logger.warning("duplicate_tool_call_blocked", extra={"tool": tool.name, "invocation_id": inv_id})
                return {
                    "status": "error",
                    "error_type": "duplicate_tool_call",
                    "tool": tool.name,
                    "error_message": "Identical tool call already executed in this invocation.",
                    "recovery_hint": (
                        "You already retrieved this exact result earlier in this turn. "
                        "Do NOT call this tool again; use the data already in conversation history "
                        "and immediately produce your final structured output."
                    ),
                }
            count = self._call_counts.get(inv_id, 0)
            if count >= self._max_calls_per_invocation:
                logger.warning("tool_call_budget_exceeded", extra={"tool": tool.name, "invocation_id": inv_id})
                return {
                    "status": "error",
                    "error_type": "call_budget_exceeded",
                    "tool": tool.name,
                    "error_message": f"Reached max {self._max_calls_per_invocation} MCP tool calls in one invocation.",
                    "recovery_hint": (
                        "Stop calling tools now and synthesize your response strictly from the "
                        "data already collected in this session."
                    ),
                }
            seen.add(signature)
            self._call_counts[inv_id] = count + 1

        tool_args.clear()
        tool_args.update(normalized)
        return None

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict[str, Any],
    ):
        if tool.name not in MCP_ARG_SCHEMAS or not isinstance(result, dict):
            return None
        try:
            parsed = McpToolOutput.model_validate(result)
        except ValidationError as exc:
            logger.warning(
                "tool_output_malformed",
                extra={"tool": tool.name, "errors": exc.errors(include_url=False)},
            )
            return {
                **result,
                "isError": True,
                "recovery_hint": (
                    "The Bacen MCP tool returned a malformed payload. Do not invent numbers; "
                    "tell the user the data source returned an unexpected format."
                ),
            }
        if parsed.isError:
            return {
                **result,
                "recovery_hint": (
                    "The Bacen MCP tool returned an error. Inspect the message, adjust "
                    "arguments (instituicao, segmento, modalidade, ano_mes/trimestre) and retry once."
                ),
            }
        if parsed.structuredContent and parsed.structuredContent.registros == []:
            return {
                **result,
                "recovery_hint": (
                    "No BCB records matched these filters. Broaden the query: drop ano_mes / "
                    "trimestre, use segmento='TODOS' or remove motivo. Never fabricate figures."
                ),
            }
        return None

    async def on_tool_error_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        error: Exception,
    ):
        return {
            "status": "error",
            "error_type": type(error).__name__,
            "tool": tool.name,
            "error_message": str(error)[:500],
            "recovery_hint": _recovery_for_exception(error),
        }
