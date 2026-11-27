"""Deterministic What-If BCB Ranking Simulator & Business-Value Driver tool.

Replicates the exact 0–10 pillar normalization formulas from ``mcp_bacen`` so
any interactive slider or conversational What-If scenario produces 100% consistent
before/after scores, ranking jumps, overtaken competitors, regulatory floor checks
and auto-matched Google Cloud FSI blueprints — with zero fabricated ROI percentages.
"""

from __future__ import annotations

from typing import Any

from google.adk.tools import FunctionTool
from pydantic import ValidationError

from ..catalog import load_gcp_fsi_catalog
from ..observability.tracing import get_tracer
from ..schemas import (
    BenchmarkWeights,
    InstitutionBenchmarkSnapshot,
    RankedInstitution,
    WhatIfMetricChange,
    WhatIfOverrides,
    WhatIfPillarDelta,
    WhatIfSimulationResult,
    WhatIfValueDriver,
    normalize_institution,
)
from .gcp_advisory_tools import _infer_segment, _normalize_record_aliases

_PILLAR_LABELS: dict[str, str] = {
    "reclamacoes": "Reclamações BCB (Deati)",
    "taxas_credito": "Taxas de Crédito (Olinda)",
    "pix_med": "Pix, SPI & Fraudes MED",
    "prudencial": "Prudencial (IF.data) & Open Finance",
}

# (field_name, label, bcb_pillar_id, unit, direction)
_METRIC_META: tuple[tuple[str, str, str, str, str], ...] = (
    ("indice_reclamacoes", "Índice de Reclamações Deati", "reclamacoes_deati", "/1M clientes", "lower_is_better"),
    ("taxa_juros_mensal_pct", "Taxa Mensal de Crédito", "taxas_credito", "% a.m.", "lower_is_better"),
    ("disponibilidade_spi_pct", "Disponibilidade SPI", "pix_med_spi", "%", "higher_is_better"),
    ("med_por_100k", "Fraudes MED Pix", "pix_med_spi", "/100k tx", "lower_is_better"),
    ("taxa_devolucao_med_pct", "Taxa de Devolução MED", "pix_med_spi", "%", "higher_is_better"),
    ("indice_basileia_pct", "Índice de Basileia III", "prudencial_ifdata_open_finance", "%", "higher_is_better"),
    ("roe_anualizado_pct", "ROE Anualizado", "prudencial_ifdata_open_finance", "%", "higher_is_better"),
    ("inadimplencia_90d_pct", "Inadimplência > 90d", "prudencial_ifdata_open_finance", "%", "lower_is_better"),
    (
        "disponibilidade_open_finance_pct",
        "Disponibilidade Open Finance",
        "prudencial_ifdata_open_finance",
        "%",
        "higher_is_better",
    ),
)

_REGULATORY_FLOORS: tuple[tuple[str, str, float], ...] = (
    ("disponibilidade_spi_pct", "Disponibilidade SPI abaixo do piso regulatório BCB (99,80%)", 99.80),
    (
        "disponibilidade_open_finance_pct",
        "Disponibilidade Open Finance abaixo do piso regulatório Fase 1 (99,50%)",
        99.50,
    ),
    ("indice_basileia_pct", "Índice de Basileia III abaixo do patamar prudencial S1 (11,50%)", 11.50),
)

_VALUE_DRIVER_TEMPLATES: dict[str, tuple[str, str, list[str]]] = {
    "reclamacoes_deati": (
        "Redução de custo operacional de Ouvidoria, FCR e risco reputacional no BCB",
        "Diminuir reclamações procedentes no Deati reduz retrabalho humano, custos de contestação/jurídico "
        "e acelera resolução no primeiro contato com IA conversacional em PT-BR e agentes auditáveis.",
        ["Customer Engagement Suite (Dialogflow CX / Agent Assist)", "Vertex AI Agent Engine + Model Armor", "Cloud DLP"],
    ),
    "taxas_credito": (
        "Eficiência de precificação, margem líquida de crédito e conversão digital",
        "Modelos dinâmicos de risco e elasticidade com features em tempo real permitem ofertar taxas mais "
        "competitivas para bons pagadores enquanto preservam spread ajustado ao risco.",
        ["BigQuery + BigQuery ML", "Vertex AI Feature Store", "Vertex AI Online Prediction"],
    ),
    "pix_med_spi": (
        "Proteção contra perdas de fraude Pix/MED e resiliência crítica no SPI",
        "Detecção sub-segundo de golpes Pix amplia o bloqueio cautelar dentro da janela regulatória do MED "
        "e elimina indisponibilidades em picos de pagamento (5º dia útil, Black Friday).",
        ["Pub/Sub + Dataflow", "Cloud Spanner (Ativo-Ativo)", "Vertex AI Feature Store"],
    ),
    "prudencial_ifdata_open_finance": (
        "Expansão de ROE via eficiência de TI, menor inadimplência e monetização Open Finance",
        "Offload progressivo de jornadas do legado, renegociação inteligente e APIs Open Finance em alta "
        "disponibilidade elevam eficiência operacional e qualidade da carteira de crédito.",
        ["AlloyDB for PostgreSQL + Datastream", "Apigee API Management (FAPI/mTLS)", "GKE + Cloud Run"],
    ),
}


def _clamp(value: float, low: float = 1.0, high: float = 10.0) -> float:
    return round(max(low, min(high, value)), 2)


def compute_pillar_scores(snap: InstitutionBenchmarkSnapshot) -> dict[str, float]:
    """Exact 0–10 pillar scoring formulas matching ``mcp_bacen`` ``comparar_instituicoes_financeiras``."""
    rec_val = snap.indice_reclamacoes if snap.indice_reclamacoes is not None else 30.0
    tax_val = snap.taxa_juros_mensal_pct if snap.taxa_juros_mensal_pct is not None else 12.0
    spi_val = snap.disponibilidade_spi_pct if snap.disponibilidade_spi_pct is not None else 99.85
    dev_val = snap.taxa_devolucao_med_pct if snap.taxa_devolucao_med_pct is not None else 22.0
    med_val = snap.med_por_100k if snap.med_por_100k is not None else 7.5
    bas_val = snap.indice_basileia_pct if snap.indice_basileia_pct is not None else 15.0
    roe_val = snap.roe_anualizado_pct if snap.roe_anualizado_pct is not None else 15.0
    of_val = snap.disponibilidade_open_finance_pct if snap.disponibilidade_open_finance_pct is not None else 99.8

    score_rec = _clamp(10.0 - rec_val / 6.0)
    score_tax = _clamp(10.0 - (tax_val - 2.0) * 0.45)
    score_pix = _clamp(5.0 + (spi_val - 99.80) * 20.0 + (dev_val / 15.0) - (med_val / 8.0))
    score_pru = _clamp(3.5 + (bas_val - 10.5) * 0.45 + (roe_val / 10.0) + (of_val - 99.5) * 3.0)

    return {
        "reclamacoes": score_rec,
        "taxas_credito": score_tax,
        "pix_med": score_pix,
        "prudencial": score_pru,
    }


def _weighted_score(scores: dict[str, float], norm_weights: dict[str, float]) -> float:
    return round(sum(scores[k] * norm_weights[k] for k in norm_weights), 2)


def _rank_snapshots(
    snapshots: list[InstitutionBenchmarkSnapshot],
    norm_weights: dict[str, float],
) -> tuple[list[RankedInstitution], dict[str, dict[str, float]]]:
    scored: list[tuple[str, float]] = []
    by_inst_pillars: dict[str, dict[str, float]] = {}
    pillars_used = sorted(k for k, v in norm_weights.items() if v > 0)
    for snap in snapshots:
        ps = compute_pillar_scores(snap)
        by_inst_pillars[snap.instituicao] = ps
        scored.append((snap.instituicao, _weighted_score(ps, norm_weights)))

    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    ranking = [
        RankedInstitution(
            position=idx + 1,
            instituicao=name,
            weighted_score_0_10=val,
            pillars_used=pillars_used,
        )
        for idx, (name, val) in enumerate(scored)
    ]
    return ranking, by_inst_pillars


def _match_blueprints_for_changes(
    segment: str,
    improved_metrics: set[str],
    improved_pillars: set[str],
    max_items: int = 4,
) -> list[dict[str, Any]]:
    catalog = load_gcp_fsi_catalog()
    scored: list[tuple[float, dict[str, Any]]] = []
    for bp in catalog:
        score = 0.0
        if segment in bp.target_segments:
            score += 2.0
        elif "TODOS" in bp.target_segments:
            score += 1.0
        metric_hits = [m for m in bp.trigger_metrics if m in improved_metrics]
        pillar_hits = [p for p in bp.bcb_pillars if p in improved_pillars]
        score += len(metric_hits) * 4.0 + len(pillar_hits) * 2.5
        if metric_hits or pillar_hits:
            scored.append(
                (
                    score,
                    {
                        "solution_id": bp.solution_id,
                        "title": bp.title,
                        "category": bp.category,
                        "horizon": bp.horizon,
                        "gcp_services": bp.gcp_services[:4],
                        "impacted_bcb_kpis": bp.impacted_bcb_kpis,
                        "compliance_brazil": bp.compliance_brazil,
                        "matched_metrics": metric_hits,
                    },
                )
            )
    scored.sort(key=lambda item: (-item[0], item[1]["solution_id"]))
    return [item[1] for item in scored[:max_items]]


def simulate_bcb_what_if_scenario(
    target_institution: str,
    benchmark_records: list[InstitutionBenchmarkSnapshot],
    overrides: WhatIfOverrides | dict[str, Any],
    weights: BenchmarkWeights | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Simulates a What-If BCB/Open Finance target scenario for one institution deterministically.

    Recomputes 0–10 pillar scores and full competitive ranking when selected BCB
    metrics of ``target_institution`` improve (or deteriorate), identifying exact
    ranking position gains, overtaken competitors, BCB regulatory floor alerts,
    enabling Google Cloud FSI blueprints and transparent business-value drivers.

    Args:
      target_institution: Canonical or alias name of the simulated bank (e.g. ``"BRADESCO"``).
      benchmark_records: Full list of verbatim per-institution benchmark snapshots
        from ``comparar_instituicoes_financeiras`` (target bank + peers).
      overrides: Dict or ``WhatIfOverrides`` specifying simulated target values for
        one or more BCB metrics (e.g. ``{"indice_reclamacoes": 20.0, "med_por_100k": 5.5}``).
      weights: Optional custom ``BenchmarkWeights`` (defaults to BCB consolidated weights:
        30% Reclamações, 25% Crédito, 25% Pix/MED, 20% Prudencial).

    Returns:
      A ``WhatIfSimulationResult`` dict with ``position_before``, ``position_after``,
      ``positions_gained``, ``overtaken_competitors``, ``pillar_deltas``,
      ``ranking_before``, ``ranking_after``, ``recommended_gcp_blueprints`` and
      ``business_value_drivers``, or ``status="error"`` plus a ``recovery_hint``.
    """
    try:
        target_code = normalize_institution(target_institution)
    except ValueError as exc:
        return WhatIfSimulationResult(
            status="error",
            error_message=str(exc),
            recovery_hint=(
                "Pass a supported institution name (NUBANK, ITAU, BRADESCO, BANCO_DO_BRASIL, "
                "SANTANDER, CAIXA, INTER, C6_BANK, MERCADO_PAGO, BTG_PACTUAL)."
            ),
        ).model_dump()

    if not target_code:
        return WhatIfSimulationResult(
            status="error",
            error_message="Empty target_institution.",
            recovery_hint="Specify which financial institution to simulate.",
        ).model_dump()

    try:
        snapshots = [
            item
            if isinstance(item, InstitutionBenchmarkSnapshot)
            else InstitutionBenchmarkSnapshot.model_validate(_normalize_record_aliases(item))
            for item in benchmark_records
        ]
        ov = overrides if isinstance(overrides, WhatIfOverrides) else WhatIfOverrides.model_validate(overrides or {})
        w = weights if isinstance(weights, BenchmarkWeights) else BenchmarkWeights.model_validate(weights or {})
    except ValidationError as exc:
        return WhatIfSimulationResult(
            status="error",
            error_message=f"Invalid simulation input: {exc.errors()[0]['msg']}",
            recovery_hint=(
                "Ensure overrides stay within realistic bounds (e.g. disponibilidade_spi_pct 95–100, "
                "indice_reclamacoes 0–200, taxa_juros_mensal_pct 0.5–30)."
            ),
        ).model_dump()

    target_idx = next((i for i, s in enumerate(snapshots) if s.instituicao == target_code), None)
    if target_idx is None:
        return WhatIfSimulationResult(
            status="error",
            target_institution=target_code,
            error_message=f"Institution '{target_code}' not found in benchmark_records.",
            recovery_hint=f"Include '{target_code}' in benchmark_records from comparar_instituicoes_financeiras.",
        ).model_dump()

    total_w = w.reclamacoes + w.taxas_credito + w.pix_med + w.prudencial
    if total_w <= 0:
        return WhatIfSimulationResult(
            status="error",
            target_institution=target_code,
            error_message="All benchmark weights are zero.",
            recovery_hint="Provide positive weights summing > 0.",
        ).model_dump()

    norm_w = {
        "reclamacoes": w.reclamacoes / total_w,
        "taxas_credito": w.taxas_credito / total_w,
        "pix_med": w.pix_med / total_w,
        "prudencial": w.prudencial / total_w,
    }

    target_before = snapshots[target_idx]
    segment = _infer_segment(target_code, target_before.segmento)

    # Apply non-null overrides cleanly to a copy of the target bank snapshot.
    override_dict = {k: v for k, v in ov.model_dump().items() if v is not None}
    target_after = target_before.model_copy(update=override_dict)
    simulated_snapshots = list(snapshots)
    simulated_snapshots[target_idx] = target_after

    ranking_before, pillars_before_map = _rank_snapshots(snapshots, norm_w)
    ranking_after, pillars_after_map = _rank_snapshots(simulated_snapshots, norm_w)

    pos_before = next(r.position for r in ranking_before if r.instituicao == target_code)
    pos_after = next(r.position for r in ranking_after if r.instituicao == target_code)
    score_before = next(r.weighted_score_0_10 for r in ranking_before if r.instituicao == target_code)
    score_after = next(r.weighted_score_0_10 for r in ranking_after if r.instituicao == target_code)

    ahead_before = {r.instituicao for r in ranking_before if r.position < pos_before}
    behind_after = {r.instituicao for r in ranking_after if r.position > pos_after}
    overtaken = [r.instituicao for r in ranking_before if r.instituicao in (ahead_before & behind_after)]

    p_before = pillars_before_map[target_code]
    p_after = pillars_after_map[target_code]
    pillar_deltas = [
        WhatIfPillarDelta(
            pillar=key,  # type: ignore[arg-type]
            label=_PILLAR_LABELS[key],
            before_score=p_before[key],
            after_score=p_after[key],
            delta_score=round(p_after[key] - p_before[key], 2),
        )
        for key in ("reclamacoes", "taxas_credito", "pix_med", "prudencial")
    ]

    metric_changes: list[WhatIfMetricChange] = []
    improved_metrics: set[str] = set()
    improved_pillars: set[str] = set()

    for field_name, label, bcb_pillar, unit, direction in _METRIC_META:
        if field_name not in override_dict:
            continue
        before_val = getattr(target_before, field_name)
        after_val = getattr(target_after, field_name)
        if before_val is None or after_val is None:
            continue
        delta_abs = round(after_val - before_val, 3)
        if abs(delta_abs) < 1e-6:
            continue
        delta_pct = round(((after_val - before_val) / abs(before_val)) * 100.0, 2) if before_val != 0 else 0.0
        improved = (delta_abs < 0) if direction == "lower_is_better" else (delta_abs > 0)
        if improved:
            improved_metrics.add(field_name)
            improved_pillars.add(bcb_pillar)
        metric_changes.append(
            WhatIfMetricChange(
                metric=field_name,
                label=label,
                pillar=bcb_pillar,
                unit=unit,
                direction=direction,  # type: ignore[arg-type]
                before_value=round(float(before_val), 3),
                after_value=round(float(after_val), 3),
                delta_abs=delta_abs,
                delta_pct=delta_pct,
                improved=improved,
            )
        )

    regulatory_alerts: list[str] = []
    for field_name, msg, floor_val in _REGULATORY_FLOORS:
        val = getattr(target_after, field_name)
        if val is not None and val < floor_val:
            regulatory_alerts.append(f"{msg} (simulado: {val:.2f}%).")

    blueprints = _match_blueprints_for_changes(segment, improved_metrics, improved_pillars, max_items=4)

    value_drivers: list[WhatIfValueDriver] = []
    for bcb_pillar in (
        "reclamacoes_deati",
        "taxas_credito",
        "pix_med_spi",
        "prudencial_ifdata_open_finance",
    ):
        if bcb_pillar in improved_pillars:
            headline, mechanism, enablers = _VALUE_DRIVER_TEMPLATES[bcb_pillar]
            value_drivers.append(
                WhatIfValueDriver(
                    pillar=bcb_pillar,
                    headline=headline,
                    mechanism=mechanism,
                    gcp_enablers=enablers,
                    assumption_note=(
                        "Alavanca direcional baseada em meta simulada pelo usuário; quantificação "
                        "financeira definitiva requer discovery com dados internos de volumetria do banco."
                    ),
                )
            )

    with get_tracer().start_as_current_span("bacen.tool.simulate_bcb_what_if_scenario") as span:
        span.set_attribute("bacen.whatif.institution", target_code)
        span.set_attribute("bacen.whatif.positions_gained", pos_before - pos_after)
        span.set_attribute("bacen.whatif.score_delta", round(score_after - score_before, 2))
        span.set_attribute("bacen.whatif.changes_count", len(metric_changes))
        return WhatIfSimulationResult(
            status="success",
            target_institution=target_code,
            segment=segment,
            position_before=pos_before,
            position_after=pos_after,
            positions_gained=pos_before - pos_after,
            score_before_0_10=score_before,
            score_after_0_10=score_after,
            score_delta=round(score_after - score_before, 2),
            overtaken_competitors=overtaken,
            pillar_deltas=pillar_deltas,
            metric_changes=metric_changes,
            ranking_before=ranking_before,
            ranking_after=ranking_after,
            regulatory_alerts=regulatory_alerts,
            recommended_gcp_blueprints=blueprints,
            business_value_drivers=value_drivers,
            weights_normalized={k: round(v, 3) for k, v in norm_w.items()},
        ).model_dump()


simulate_bcb_what_if_scenario_tool = FunctionTool(simulate_bcb_what_if_scenario)
