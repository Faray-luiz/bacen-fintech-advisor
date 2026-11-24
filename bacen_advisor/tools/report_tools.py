"""Local function tools used by the analysis, discovery and reporting agents.

Every tool:

* has a specific, action-oriented name (``list_supported_bacen_filters``,
  ``calculate_weighted_institution_ranking``, ``export_report_to_gcs``);
* documents its purpose, every parameter and return shape in human-readable docstrings;
* uses explicit Pydantic schemas for strict input/output validation;
* never crashes the agent run: errors return ``status="error"`` plus a descriptive
  ``recovery_hint`` guiding the LLM how to recover.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import uuid

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from pydantic import ValidationError

from ..config import get_settings
from ..observability.tracing import get_tracer
from ..pii import redact
from ..schemas import (
    CREDIT_MODALITY_ALIASES,
    GLOSSARY_TOPICS,
    KNOWN_INSTITUTIONS,
    SEGMENT_ALIASES,
    BenchmarkWeights,
    ExportReportResult,
    InstitutionMetrics,
    RankedInstitution,
    RankingResult,
    SupportedFiltersResult,
)

logger = logging.getLogger(__name__)

_MAX_REPORT_CHARS = 200_000


def list_supported_bacen_filters() -> dict:
    """Lists all canonical filter values accepted by the Bacen MCP data tools.

    Call this BEFORE querying BCB data whenever the user refers to an institution,
    segment or credit modality in free text and you need the exact canonical identifier.

    Returns:
      A ``SupportedFiltersResult`` dict listing canonical ``instituicoes``,
      ``segmentos`` aliases, ``modalidades_credito`` aliases, ``topicos_glossario``
      and expected date/quarter formats.
    """
    return SupportedFiltersResult(
        instituicoes=list(KNOWN_INSTITUTIONS),
        segmentos=SEGMENT_ALIASES,
        modalidades_credito=CREDIT_MODALITY_ALIASES,
        topicos_glossario=list(GLOSSARY_TOPICS),
        formato_ano_mes="YYYY-MM (ex.: 2026-09)",
        formato_trimestre="YYYY-Q# (ex.: 2026-Q3)",
    ).model_dump()


def calculate_weighted_institution_ranking(
    institutions: list[InstitutionMetrics],
    weights: BenchmarkWeights | None = None,
) -> dict:
    """Ranks Brazilian financial institutions with custom weights over the 4 BCB pillars.

    Use this whenever the user wants a benchmark reflecting their own strategic
    priorities (e.g. "dê 50% para Pix/MED, 30% para reclamações e 20% para taxas de
    crédito"). Default weights match the Bacen MCP consolidated score:
    ``reclamacoes`` 30%, ``taxas_credito`` 25%, ``pix_med`` 25%, ``prudencial`` 20%.
    All input scores must be on the 0-10 normalized scale returned by
    ``comparar_instituicoes_financeiras`` (where 10 is best). Missing pillars for an
    institution are skipped and remaining weights are renormalized proportionally.

    Args:
      institutions: Per-institution normalized 0-10 pillar scores copied verbatim from
        ``comparar_instituicoes_financeiras`` (``score_reclamacoes_0_10``,
        ``score_taxas_credito_0_10``, ``score_pix_med_0_10``, ``score_prudencial_0_10``).
      weights: Relative non-negative weights for ``reclamacoes``, ``taxas_credito``,
        ``pix_med`` and ``prudencial``. Automatically normalized to sum to 1.

    Returns:
      A ``RankingResult`` dict containing the ordered ``ranking`` and
      ``weights_normalized``, or ``status='error'`` with a ``recovery_hint``.
    """
    try:
        items = [
            item if isinstance(item, InstitutionMetrics) else InstitutionMetrics.model_validate(item)
            for item in institutions
        ]
        w = weights if isinstance(weights, BenchmarkWeights) else BenchmarkWeights.model_validate(weights or {})
    except ValidationError as exc:
        return RankingResult(
            status="error",
            error_message=f"Invalid input: {exc.errors()[0]['msg']}",
            recovery_hint=(
                "Pass normalized 0-10 pillar scores copied verbatim from "
                "comparar_instituicoes_financeiras (each score must be between 0 and 10)."
            ),
        ).model_dump()

    if not items:
        return RankingResult(
            status="error",
            error_message="No institutions provided.",
            recovery_hint="Call comparar_instituicoes_financeiras first and pass its records.",
        ).model_dump()

    total = w.reclamacoes + w.taxas_credito + w.pix_med + w.prudencial
    if total <= 0:
        return RankingResult(
            status="error",
            error_message="All weights are zero.",
            recovery_hint=(
                "Supply at least one positive weight, e.g. "
                "{'reclamacoes': 0.30, 'taxas_credito': 0.25, 'pix_med': 0.25, 'prudencial': 0.20}."
            ),
        ).model_dump()

    norm = {
        "reclamacoes": w.reclamacoes / total,
        "taxas_credito": w.taxas_credito / total,
        "pix_med": w.pix_med / total,
        "prudencial": w.prudencial / total,
    }

    scored: list[tuple[str, float, list[str]]] = []
    for inst in items:
        pillars = {
            "reclamacoes": inst.score_reclamacoes_0_10,
            "taxas_credito": inst.score_taxas_credito_0_10,
            "pix_med": inst.score_pix_med_0_10,
            "prudencial": inst.score_prudencial_0_10,
        }
        available = {k: v for k, v in pillars.items() if v is not None and norm[k] > 0}
        if not available:
            continue
        weight_sum = sum(norm[k] for k in available)
        score = sum(v * norm[k] for k, v in available.items()) / weight_sum
        scored.append((inst.instituicao.upper(), round(score, 2), sorted(available)))

    if not scored:
        return RankingResult(
            status="error",
            error_message="No institution has any score for the selected weights.",
            recovery_hint="Provide at least one non-null 0-10 pillar score per institution.",
        ).model_dump()

    scored.sort(key=lambda t: t[1], reverse=True)
    ranking = [
        RankedInstitution(position=i + 1, instituicao=name, weighted_score_0_10=val, pillars_used=used)
        for i, (name, val, used) in enumerate(scored)
    ]
    with get_tracer().start_as_current_span("bacen.tool.calculate_weighted_institution_ranking") as span:
        span.set_attribute("bacen.ranking.institutions_count", len(ranking))
        span.set_attribute("bacen.ranking.leader", ranking[0].instituicao)
        return RankingResult(
            status="success",
            ranking=ranking,
            weights_normalized={k: round(v, 3) for k, v in norm.items()},
        ).model_dump()


def export_report_to_gcs(title: str, markdown_report: str, tool_context: ToolContext) -> dict:
    """Publishes the final, critic-approved Markdown benchmark report to Cloud Storage.

    HIGH-STAKES ACTION: writes a durable, shareable report artifact to GCS. Wrapped
    with ``require_confirmation=True`` so ADK pauses execution and requires explicit
    human approval before running. Call ONLY after the critic has approved the report
    AND the user explicitly requested saving/exporting it.

    Args:
      title: Short human-readable title, e.g. "Benchmark Nubank vs Incumbentes - 2026-Q3".
      markdown_report: Full critic-approved Markdown report including BCB sources and periods.
      tool_context: Injected by ADK (session/user metadata). Not provided by the LLM.

    Returns:
      An ``ExportReportResult`` dict with ``gcs_uri`` on success, or ``status='error'``
      plus a ``recovery_hint``.
    """
    settings = get_settings()
    if not settings.reports_bucket:
        return ExportReportResult(
            status="error",
            error_message="REPORTS_BUCKET is not configured.",
            recovery_hint=(
                "Inform the user that GCS export is unavailable in this environment and "
                "present the full report inline instead."
            ),
        ).model_dump()
    if not title.strip() or not markdown_report.strip():
        return ExportReportResult(
            status="error",
            error_message="Empty title or report.",
            recovery_hint="Provide a non-empty title and the complete approved report in markdown_report.",
        ).model_dump()
    if len(markdown_report) > _MAX_REPORT_CHARS:
        return ExportReportResult(
            status="error",
            error_message=f"Report too large ({len(markdown_report)} chars).",
            recovery_hint=f"Condense the report below {_MAX_REPORT_CHARS} characters and retry.",
        ).model_dump()

    report_id = f"{dt.datetime.now(dt.UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    user_id = re.sub(r"[^A-Za-z0-9_-]", "_", getattr(tool_context, "user_id", None) or "anonymous")[:64]
    blob_name = f"reports/{user_id}/{report_id}.md"
    body = f"# {title}\n\n{markdown_report}\n"
    try:
        from google.cloud import storage

        with get_tracer().start_as_current_span("bacen.tool.export_report_to_gcs") as span:
            span.set_attribute("bacen.report.id", report_id)
            span.set_attribute("bacen.report.bucket", settings.reports_bucket)
            blob = storage.Client(project=settings.project_id).bucket(settings.reports_bucket).blob(blob_name)
            blob.metadata = {"title": redact(title) or "", "report_id": report_id}
            blob.upload_from_string(redact(body) or "", content_type="text/markdown; charset=utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.error("report_export_failed", extra={"report_id": report_id, "error": str(exc)})
        return ExportReportResult(
            status="error",
            report_id=report_id,
            error_message=f"Upload failed: {exc}",
            recovery_hint=(
                "Do not retry automatically. Show the report inline and let the user know "
                "the Cloud Storage upload failed."
            ),
        ).model_dump()

    uri = f"gs://{settings.reports_bucket}/{blob_name}"
    tool_context.state["last_report_uri"] = uri
    return ExportReportResult(status="success", gcs_uri=uri, report_id=report_id).model_dump()


# ADK FunctionTool wrappers (HITL confirmation enforced on the sole write action).
list_supported_bacen_filters_tool = FunctionTool(list_supported_bacen_filters)
calculate_weighted_institution_ranking_tool = FunctionTool(calculate_weighted_institution_ranking)
export_report_to_gcs_tool = FunctionTool(export_report_to_gcs, require_confirmation=True)
