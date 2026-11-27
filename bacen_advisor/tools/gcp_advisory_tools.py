"""Deterministic local function tools for the Senior Google Cloud FSI Consultant agent.

Every tool follows the AgentOps rubric contract:

* specific, action-oriented names (``diagnose_institution_gaps``,
  ``match_gcp_solutions_catalog``);
* strict Pydantic input/output validation with zero crashes (errors return
  ``status="error"`` plus a descriptive ``recovery_hint``);
* OpenTelemetry spans tracing every invocation without capturing raw user PII.
"""

from __future__ import annotations

import statistics
import unicodedata
from typing import Any

from google.adk.tools import FunctionTool
from pydantic import ValidationError

from ..catalog import load_gcp_fsi_catalog
from ..observability.tracing import get_tracer
from ..schemas import (
    BCB_PILLAR_IDS,
    GapDiagnosisResult,
    GcpSolutionMatchResult,
    InstitutionBenchmarkSnapshot,
    InstitutionGap,
    MatchedGcpSolution,
    normalize_institution,
    normalize_segment,
)

_NEOBANK_CODES = {"NUBANK", "INTER", "C6_BANK", "MERCADO_PAGO", "BTG_PACTUAL"}

# Alias normalization so verbatim records from either comparar_instituicoes_financeiras
# OR single-pillar MCP tools validate cleanly into InstitutionBenchmarkSnapshot.
_FIELD_ALIASES: dict[str, str] = {
    "principal_motivo": "principal_motivo_reclamacao",
    "taxa_disponibilidade_spi_pct": "disponibilidade_spi_pct",
    "solicitacoes_med_por_100k": "med_por_100k",
    "taxa_inadimplencia_90d_pct": "inadimplencia_90d_pct",
}

# Canonical BCB metric rules: (pillar, field_name, label, direction, regulatory_floor, critical_rel_gap, high_rel_gap)
_METRIC_RULES: tuple[tuple[str, str, str, str, float | None, float, float], ...] = (
    (
        "reclamacoes_deati",
        "indice_reclamacoes",
        "Índice de Reclamações BCB/Deati (por 1M clientes)",
        "lower_is_better",
        None,
        0.25,
        0.08,
    ),
    (
        "taxas_credito",
        "taxa_juros_mensal_pct",
        "Taxa de Juros Mensal de Crédito (% a.m.)",
        "lower_is_better",
        None,
        0.20,
        0.06,
    ),
    (
        "pix_med_spi",
        "disponibilidade_spi_pct",
        "Disponibilidade Operacional SPI (%)",
        "higher_is_better",
        99.80,
        0.001,
        0.0003,
    ),
    (
        "pix_med_spi",
        "med_por_100k",
        "Solicitações de Fraude MED (por 100k transações Pix)",
        "lower_is_better",
        None,
        0.25,
        0.08,
    ),
    (
        "pix_med_spi",
        "taxa_devolucao_med_pct",
        "Taxa de Recuperação/Devolução MED (%)",
        "higher_is_better",
        None,
        0.20,
        0.07,
    ),
    (
        "prudencial_ifdata_open_finance",
        "indice_basileia_pct",
        "Índice de Basileia III (%)",
        "higher_is_better",
        11.5,
        0.15,
        0.05,
    ),
    (
        "prudencial_ifdata_open_finance",
        "inadimplencia_90d_pct",
        "Inadimplência > 90 dias (%)",
        "lower_is_better",
        None,
        0.25,
        0.08,
    ),
    (
        "prudencial_ifdata_open_finance",
        "roe_anualizado_pct",
        "ROE Anualizado (%)",
        "higher_is_better",
        None,
        0.25,
        0.10,
    ),
    (
        "prudencial_ifdata_open_finance",
        "disponibilidade_open_finance_pct",
        "Disponibilidade APIs Open Finance Fase 1 (%)",
        "higher_is_better",
        99.50,
        0.003,
        0.001,
    ),
)

_SEVERITY_ORDER = {"CRITICO": 0, "ALTO": 1, "OPORTUNIDADE": 2}


def _ascii_lower(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()


def _infer_segment(institution_code: str, explicit_segment: str | None) -> str:
    if explicit_segment and explicit_segment in ("NEOBANKS", "INCUMBENTES"):
        return explicit_segment
    return "NEOBANKS" if institution_code in _NEOBANK_CODES else "INCUMBENTES"


def _normalize_record_aliases(item: Any) -> Any:
    if isinstance(item, InstitutionBenchmarkSnapshot):
        return item
    if not isinstance(item, dict):
        return item
    normalized = dict(item)
    for alias, canonical in _FIELD_ALIASES.items():
        if alias in normalized and canonical not in normalized:
            normalized[canonical] = normalized[alias]
    return normalized


def diagnose_institution_gaps(
    target_institution: str,
    benchmark_records: list[InstitutionBenchmarkSnapshot],
) -> dict[str, Any]:
    """Deterministically diagnoses BCB/Open Finance competitive and regulatory gaps for one bank.

    Compares the target institution's verbatim 4-pillar metrics against peer medians,
    market leaders and official BCB regulatory floors (SPI >= 99.8%, Open Finance >= 99.5%,
    Basel III >= 11.5%) without ever inverting metric directionality.

    Call this FIRST inside ``gcp_cloud_consultant`` before matching Google Cloud solutions.

    Args:
      target_institution: Target Brazilian bank or fintech (e.g. ``"BRADESCO"``, ``"NUBANK"``).
      benchmark_records: List of verbatim per-institution metric records copied from
        ``comparar_instituicoes_financeiras`` (including the target bank and peer banks).

    Returns:
      A ``GapDiagnosisResult`` dict with ranked ``gaps`` (``CRITICO``, ``ALTO``,
      ``OPORTUNIDADE``), ``strengths``, ``priority_pillars`` and ``complaint_driver``,
      or ``status="error"`` plus a ``recovery_hint``.
    """
    try:
        target_code = normalize_institution(target_institution)
    except ValueError as exc:
        return GapDiagnosisResult(
            status="error",
            error_message=str(exc),
            recovery_hint=(
                "Pass a supported canonical Brazilian financial institution name "
                "(e.g. NUBANK, ITAU, BRADESCO, BANCO_DO_BRASIL, SANTANDER, CAIXA, "
                "INTER, C6_BANK, MERCADO_PAGO, BTG_PACTUAL)."
            ),
        ).model_dump()

    if not target_code:
        return GapDiagnosisResult(
            status="error",
            error_message="Empty target_institution.",
            recovery_hint="Specify the target institution name to diagnose.",
        ).model_dump()

    try:
        snapshots = [
            item
            if isinstance(item, InstitutionBenchmarkSnapshot)
            else InstitutionBenchmarkSnapshot.model_validate(_normalize_record_aliases(item))
            for item in benchmark_records
        ]
    except ValidationError as exc:
        return GapDiagnosisResult(
            status="error",
            error_message=f"Invalid benchmark_records: {exc.errors()[0]['msg']}",
            recovery_hint=(
                "Copy numeric fields verbatim from comparar_instituicoes_financeiras "
                "(instituicao, segmento, indice_reclamacoes, taxa_juros_mensal_pct, "
                "disponibilidade_spi_pct, med_por_100k, taxa_devolucao_med_pct, "
                "indice_basileia_pct, roe_anualizado_pct, inadimplencia_90d_pct, "
                "disponibilidade_open_finance_pct)."
            ),
        ).model_dump()

    target_row = next((s for s in snapshots if s.instituicao == target_code), None)
    if target_row is None:
        return GapDiagnosisResult(
            status="error",
            target_institution=target_code,
            error_message=f"Target institution '{target_code}' was not found in benchmark_records.",
            recovery_hint=(
                f"Ensure '{target_code}' is included in benchmark_records returned by "
                "comparar_instituicoes_financeiras before running gap diagnosis."
            ),
        ).model_dump()

    segment = _infer_segment(target_code, target_row.segmento)
    peers = [s for s in snapshots if s.instituicao != target_code]
    all_rows = snapshots

    gaps: list[InstitutionGap] = []
    strengths: list[str] = []

    for pillar, field_name, label, direction, reg_floor, crit_rel, high_rel in _METRIC_RULES:
        val = getattr(target_row, field_name)
        if val is None:
            continue

        peer_vals = [getattr(p, field_name) for p in peers if getattr(p, field_name) is not None]
        all_pairs = [(r.instituicao, getattr(r, field_name)) for r in all_rows if getattr(r, field_name) is not None]

        peer_median = round(float(statistics.median(peer_vals)), 3) if peer_vals else None
        if all_pairs:
            if direction == "lower_is_better":
                leader_inst, leader_val = min(all_pairs, key=lambda pair: pair[1])
            else:
                leader_inst, leader_val = max(all_pairs, key=lambda pair: pair[1])
        else:
            leader_inst, leader_val = target_code, val

        delta_vs_median = round(val - peer_median, 3) if peer_median is not None else None
        breaches_floor = reg_floor is not None and val < reg_floor

        # Compute directional "badness" relative to peer median & market leader.
        if peer_median is not None and abs(peer_median) > 1e-9:
            rel_worse_vs_median = (
                (val - peer_median) / abs(peer_median)
                if direction == "lower_is_better"
                else (peer_median - val) / abs(peer_median)
            )
        else:
            rel_worse_vs_median = 0.0

        if abs(leader_val) > 1e-9:
            rel_worse_vs_leader = (
                (val - leader_val) / abs(leader_val)
                if direction == "lower_is_better"
                else (leader_val - val) / abs(leader_val)
            )
        else:
            rel_worse_vs_leader = 0.0

        severity: str | None = None
        if breaches_floor or rel_worse_vs_median >= crit_rel:
            severity = "CRITICO"
        elif rel_worse_vs_median >= high_rel:
            severity = "ALTO"
        elif leader_inst != target_code and rel_worse_vs_leader >= max(high_rel, 0.05):
            severity = "OPORTUNIDADE"

        if severity:
            parts = [f"{target_code}: {val}"]
            if peer_median is not None:
                parts.append(f"mediana pares: {peer_median}")
            if leader_inst != target_code:
                parts.append(f"líder {leader_inst}: {leader_val}")
            if reg_floor is not None:
                parts.append(f"piso BCB: {reg_floor}")
            rationale = (
                f"{label} abaixo da referência competitiva ({' | '.join(parts)})."
                if direction == "higher_is_better"
                else f"{label} acima da referência competitiva ({' | '.join(parts)})."
            )
            gaps.append(
                InstitutionGap(
                    pillar=pillar,  # type: ignore[arg-type]
                    metric=field_name,
                    metric_label=label,
                    direction=direction,  # type: ignore[arg-type]
                    severity=severity,  # type: ignore[arg-type]
                    institution_value=val,
                    peer_median=peer_median,
                    market_leader_value=leader_val,
                    market_leader_institution=leader_inst,
                    regulatory_floor=reg_floor,
                    delta_vs_peer_median=delta_vs_median,
                    rationale=rationale,
                )
            )
        elif peer_median is not None and rel_worse_vs_median > 0:
            # Slightly behind peer median (below ALTO threshold, still not a strength!).
            parts = [f"{target_code}: {val}", f"mediana pares: {peer_median}"]
            if leader_inst != target_code:
                parts.append(f"líder {leader_inst}: {leader_val}")
            if reg_floor is not None:
                parts.append(f"piso BCB: {reg_floor}")
            gaps.append(
                InstitutionGap(
                    pillar=pillar,  # type: ignore[arg-type]
                    metric=field_name,
                    metric_label=label,
                    direction=direction,  # type: ignore[arg-type]
                    severity="OPORTUNIDADE",
                    institution_value=val,
                    peer_median=peer_median,
                    market_leader_value=leader_val,
                    market_leader_institution=leader_inst,
                    regulatory_floor=reg_floor,
                    delta_vs_peer_median=delta_vs_median,
                    rationale=f"{label} ligeiramente aquém da mediana dos pares ({' | '.join(parts)}).",
                )
            )
        else:
            if leader_inst == target_code:
                leader_note = " (líder no recorte)"
            elif peer_median is not None:
                cmp_word = "melhor que a mediana" if rel_worse_vs_median < 0 else "em linha com a mediana"
                leader_note = f" ({cmp_word} {peer_median})"
            else:
                leader_note = ""
            strengths.append(f"{label}: {val}{leader_note}")

    gaps.sort(key=lambda g: (_SEVERITY_ORDER[g.severity], BCB_PILLAR_IDS.index(g.pillar)))

    priority_pillars: list[str] = []
    for g in gaps:
        if g.pillar not in priority_pillars:
            priority_pillars.append(g.pillar)

    with get_tracer().start_as_current_span("bacen.tool.diagnose_institution_gaps") as span:
        span.set_attribute("bacen.advisory.target_institution", target_code)
        span.set_attribute("bacen.advisory.segment", segment)
        span.set_attribute("bacen.advisory.gaps_count", len(gaps))
        return GapDiagnosisResult(
            status="success",
            target_institution=target_code,
            segment=segment,
            complaint_driver=target_row.principal_motivo_reclamacao,
            peer_count=len(peers),
            gaps=gaps,
            strengths=strengths,
            priority_pillars=priority_pillars,
        ).model_dump()


def match_gcp_solutions_catalog(
    target_institution: str,
    segment: str | None = None,
    gap_pillars: list[str] | None = None,
    gap_metrics: list[str] | None = None,
    complaint_driver: str | None = None,
    max_solutions: int = 5,
) -> dict[str, Any]:
    """Matches diagnosed BCB gaps to grounded public Google Cloud FSI solution blueprints.

    Queries the declarative catalog (``bacen_advisor/catalog/gcp_fsi_solutions.json``) and
    ranks Google Cloud initiatives by BCB pillar fit, specific metric triggers, bank segment
    (``NEOBANKS`` vs. ``INCUMBENTES``), complaint driver keywords and horizon balance
    (Quick Win 0-90d, Core Scale 3-6m, Transformational 6-12m).

    Call this AFTER ``diagnose_institution_gaps`` so every recommended Google Cloud service,
    architectural differentiator and discovery question is strictly grounded in the catalog.

    Args:
      target_institution: Canonical bank or fintech identifier (e.g. ``"BRADESCO"``, ``"NUBANK"``).
      segment: Market segment (``"NEOBANKS"`` or ``"INCUMBENTES"``). Auto-inferred if omitted.
      gap_pillars: Ordered BCB pillar identifiers from ``diagnose_institution_gaps``
        (``reclamacoes_deati``, ``taxas_credito``, ``pix_med_spi``,
        ``prudencial_ifdata_open_finance``).
      gap_metrics: Specific BCB metric names flagged as gaps (e.g. ``indice_reclamacoes``,
        ``med_por_100k``, ``taxa_juros_mensal_pct``).
      complaint_driver: Top BCB Deati complaint driver text (e.g. ``"Irregularidades Pix/MED"``).
      max_solutions: Number of top initiatives to return (1 to 8; default 5).

    Returns:
      A ``GcpSolutionMatchResult`` dict with ranked ``MatchedGcpSolution`` blueprints,
      or ``status="error"`` plus a ``recovery_hint``.
    """
    try:
        target_code = normalize_institution(target_institution)
        seg_norm = normalize_segment(segment) if segment else None
    except ValueError as exc:
        return GcpSolutionMatchResult(
            status="error",
            error_message=str(exc),
            recovery_hint="Provide a canonical institution name and valid segment (NEOBANKS or INCUMBENTES).",
        ).model_dump()

    if not target_code:
        return GcpSolutionMatchResult(
            status="error",
            error_message="Empty target_institution.",
            recovery_hint="Specify the target institution to match Google Cloud blueprints.",
        ).model_dump()

    effective_segment = _infer_segment(target_code, seg_norm)
    clamped_max = max(1, min(int(max_solutions), 8))
    catalog = load_gcp_fsi_catalog()

    valid_pillars = [p for p in (gap_pillars or []) if p in BCB_PILLAR_IDS]
    metrics_set = set(gap_metrics or [])
    driver_norm = _ascii_lower(complaint_driver or "")

    advisory_mode = "gap_remediation" if valid_pillars or metrics_set else "leadership_expansion"
    scored_candidates: list[tuple[float, list[str], str, Any]] = []

    for bp in catalog:
        # Respect segment specialization (e.g. incumbent mainframe modernization vs neobank multicloud).
        if "TODOS" not in bp.target_segments and effective_segment not in bp.target_segments:
            continue

        score = 0.0
        matched_pillars: list[str] = []
        reasons: list[str] = []

        if advisory_mode == "gap_remediation":
            for rank_idx, pillar in enumerate(valid_pillars):
                if pillar in bp.bcb_pillars:
                    weight = max(1.5, 4.5 - rank_idx * 0.9)
                    score += weight
                    matched_pillars.append(pillar)
            matched_metrics = sorted(metrics_set.intersection(bp.trigger_metrics))
            if matched_metrics:
                score += 2.0 * len(matched_metrics)
                reasons.append(f"ataca métricas {', '.join(matched_metrics)}")
        else:
            # Leadership expansion mode: prioritize high-leverage AI, Pix resilience & segment-specific plays.
            score += 2.0
            matched_pillars = list(bp.bcb_pillars)
            reasons.append("expansão de liderança e escala")

        if driver_norm and bp.complaint_keywords:
            hits = [kw for kw in bp.complaint_keywords if kw in driver_norm]
            if hits:
                score += min(3.0, 1.5 * len(hits))
                reasons.append(f"alinhado ao ofensor Deati ({', '.join(hits[:2])})")

        # Segment-specific specialization bonus.
        if bp.target_segments == [effective_segment]:
            score += 2.2
            reasons.append(f"especializado para perfil {effective_segment}")

        if score <= 0:
            score = 0.5
            reasons.append("alavanca transversal Google Cloud FSI")

        if matched_pillars:
            reasons.insert(0, f"endereça pilar(es) {', '.join(matched_pillars)}")

        scored_candidates.append((round(score, 2), matched_pillars, "; ".join(reasons), bp))

    scored_candidates.sort(key=lambda item: (-item[0], item[3].horizon, item[3].solution_id))

    # Select top solutions while encouraging horizon balance (Quick Win + Core + Transformational).
    selected: list[tuple[float, list[str], str, Any]] = []
    seen_horizons: set[str] = set()
    remaining = list(scored_candidates)

    if clamped_max >= 3:
        for horizon_pref in (
            "Quick Win (0-90 dias)",
            "Escala Core (3-6 meses)",
            "Transformacional (6-12 meses)",
        ):
            pick = next(
                (c for c in remaining if c[3].horizon == horizon_pref and c[0] >= 2.0),
                None,
            )
            if pick and len(selected) < clamped_max:
                selected.append(pick)
                seen_horizons.add(horizon_pref)
                remaining.remove(pick)

    for cand in remaining:
        if len(selected) >= clamped_max:
            break
        selected.append(cand)

    selected.sort(key=lambda item: (-item[0], item[3].horizon))

    matched = [
        MatchedGcpSolution(
            rank=idx + 1,
            relevance_score=score,
            matched_pillars=mp,
            match_rationale=rationale,
            blueprint=bp,
        )
        for idx, (score, mp, rationale, bp) in enumerate(selected)
    ]

    with get_tracer().start_as_current_span("bacen.tool.match_gcp_solutions_catalog") as span:
        span.set_attribute("bacen.advisory.target_institution", target_code)
        span.set_attribute("bacen.advisory.segment", effective_segment)
        span.set_attribute("bacen.advisory.mode", advisory_mode)
        span.set_attribute("bacen.advisory.solutions_returned", len(matched))
        return GcpSolutionMatchResult(
            status="success",
            target_institution=target_code,
            segment=effective_segment,
            total_catalog_size=len(catalog),
            advisory_mode=advisory_mode,
            solutions=matched,
        ).model_dump()


# ADK FunctionTool wrappers (read-only deterministic advisory tools).
diagnose_institution_gaps_tool = FunctionTool(diagnose_institution_gaps)
match_gcp_solutions_catalog_tool = FunctionTool(match_gcp_solutions_catalog)
