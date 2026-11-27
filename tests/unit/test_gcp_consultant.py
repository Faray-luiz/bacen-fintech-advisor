"""Unit tests for the Senior Google Cloud FSI Consultant catalog, tools, and UI streaming."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from fastapi.testclient import TestClient
from google.adk.sessions import InMemorySessionService
from google.genai import types

from bacen_advisor.catalog import load_gcp_fsi_catalog
from bacen_advisor.schemas import TOOL_JSON_SCHEMAS
from bacen_advisor.tools.gcp_advisory_tools import (
    diagnose_institution_gaps,
    match_gcp_solutions_catalog,
)
from web_ui.pdf_exporter import PdfReportMetadata, generate_executive_pdf
from web_ui.server import create_app

SAMPLE_RECORDS = [
    {
        "instituicao": "NUBANK",
        "segmento": "NEOBANKS",
        "indice_reclamacoes": 14.8,
        "principal_motivo_reclamacao": "Irregularidades relacionadas a cartão de crédito",
        "taxa_juros_mensal_pct": 14.2,
        "taxa_juros_anual_pct": 392.0,
        "disponibilidade_spi_pct": 99.96,
        "med_por_100k": 5.4,
        "taxa_devolucao_med_pct": 31.5,
        "indice_basileia_pct": 18.2,
        "roe_anualizado_pct": 28.4,
        "inadimplencia_90d_pct": 6.1,
        "disponibilidade_open_finance_pct": 99.85,
    },
    {
        "instituicao": "ITAU",
        "segmento": "INCUMBENTES",
        "indice_reclamacoes": 17.5,
        "principal_motivo_reclamacao": "Oferta ou prestação de informação sobre crédito",
        "taxa_juros_mensal_pct": 12.1,
        "taxa_juros_anual_pct": 294.0,
        "disponibilidade_spi_pct": 99.94,
        "med_por_100k": 6.8,
        "taxa_devolucao_med_pct": 27.0,
        "indice_basileia_pct": 16.5,
        "roe_anualizado_pct": 22.1,
        "inadimplencia_90d_pct": 3.4,
        "disponibilidade_open_finance_pct": 99.82,
    },
    {
        "instituicao": "BRADESCO",
        "segmento": "INCUMBENTES",
        "indice_reclamacoes": 34.2,
        "principal_motivo_reclamacao": "Irregularidades relacionadas a Pix e MED",
        "taxa_juros_mensal_pct": 16.5,
        "taxa_juros_anual_pct": 525.0,
        "disponibilidade_spi_pct": 99.72,
        "med_por_100k": 12.4,
        "taxa_devolucao_med_pct": 17.2,
        "indice_basileia_pct": 15.1,
        "roe_anualizado_pct": 11.4,
        "inadimplencia_90d_pct": 5.9,
        "disponibilidade_open_finance_pct": 99.41,
    },
    {
        "instituicao": "INTER",
        "segmento": "NEOBANKS",
        "indice_reclamacoes": 21.0,
        "principal_motivo_reclamacao": "Cobrança indevida em cartão",
        "taxa_juros_mensal_pct": 13.8,
        "taxa_juros_anual_pct": 371.0,
        "disponibilidade_spi_pct": 99.91,
        "med_por_100k": 7.1,
        "taxa_devolucao_med_pct": 24.5,
        "indice_basileia_pct": 19.0,
        "roe_anualizado_pct": 13.8,
        "inadimplencia_90d_pct": 4.7,
        "disponibilidade_open_finance_pct": 99.78,
    },
]


def test_gcp_fsi_catalog_is_valid_unique_and_complete():
    catalog = load_gcp_fsi_catalog()
    assert len(catalog) >= 12
    ids = [bp.solution_id for bp in catalog]
    assert len(ids) == len(set(ids))
    covered_pillars = {p for bp in catalog for p in bp.bcb_pillars}
    assert covered_pillars == {
        "reclamacoes_deati",
        "taxas_credito",
        "pix_med_spi",
        "prudencial_ifdata_open_finance",
    }
    for bp in catalog:
        assert bp.gcp_services
        assert bp.google_differentiators
        assert bp.discovery_questions
        assert any(
            token in bp.compliance_brazil
            for token in ("southamerica-east1", "Res.", "Resolução", "LGPD", "Lei", "Circular")
        )


def test_tool_json_schemas_include_all_13_tools():
    assert "diagnose_institution_gaps" in TOOL_JSON_SCHEMAS
    assert "match_gcp_solutions_catalog" in TOOL_JSON_SCHEMAS
    assert "simulate_bcb_what_if_scenario" in TOOL_JSON_SCHEMAS
    assert len(TOOL_JSON_SCHEMAS) == 13


def test_diagnose_institution_gaps_detects_critical_regulatory_and_peer_gaps():
    res = diagnose_institution_gaps("Bradesco", SAMPLE_RECORDS)
    assert res["status"] == "success"
    assert res["target_institution"] == "BRADESCO"
    assert res["segment"] == "INCUMBENTES"
    assert res["peer_count"] == 3
    assert "Pix" in (res["complaint_driver"] or "")

    gaps_by_metric = {g["metric"]: g for g in res["gaps"]}
    # SPI 99.72% < 99.80% floor & Open Finance 99.41% < 99.50% floor MUST be CRITICO.
    assert gaps_by_metric["disponibilidade_spi_pct"]["severity"] == "CRITICO"
    assert gaps_by_metric["disponibilidade_open_finance_pct"]["severity"] == "CRITICO"
    # High complaint index (34.2 vs median 17.5) and high MED fraud (12.4 vs median 6.8) -> CRITICO.
    assert gaps_by_metric["indice_reclamacoes"]["severity"] == "CRITICO"
    assert gaps_by_metric["med_por_100k"]["severity"] == "CRITICO"
    # High credit rate (16.5% vs median 13.8%) -> ALTO/CRITICO.
    assert gaps_by_metric["taxa_juros_mensal_pct"]["severity"] in {"CRITICO", "ALTO"}

    # Regression: slightly below peer median (99.79% < 99.88%) must NEVER be labeled a strength.
    slight_lag = [
        {"instituicao": "BRADESCO", "disponibilidade_open_finance_pct": 99.79},
        {"instituicao": "ITAU", "disponibilidade_open_finance_pct": 99.88},
        {"instituicao": "NUBANK", "disponibilidade_open_finance_pct": 99.91},
    ]
    diag_slight = diagnose_institution_gaps("BRADESCO", slight_lag)
    assert diag_slight["status"] == "success"
    assert not any("Open Finance" in s for s in diag_slight["strengths"])
    assert any(g["metric"] == "disponibilidade_open_finance_pct" for g in diag_slight["gaps"])


def test_diagnose_institution_gaps_accepts_single_pillar_aliases_and_guides_errors():
    alias_rows = [
        {
            "instituicao": "NUBANK",
            "principal_motivo": "Cartão de crédito",
            "taxa_disponibilidade_spi_pct": 99.96,
            "solicitacoes_med_por_100k": 5.4,
            "taxa_inadimplencia_90d_pct": 6.1,
        },
        {
            "instituicao": "ITAU",
            "principal_motivo": "Crédito",
            "taxa_disponibilidade_spi_pct": 99.92,
            "solicitacoes_med_por_100k": 7.0,
            "taxa_inadimplencia_90d_pct": 3.4,
        },
    ]
    ok = diagnose_institution_gaps("Nu Pagamentos", alias_rows)
    assert ok["status"] == "success"
    assert ok["target_institution"] == "NUBANK"
    assert ok["segment"] == "NEOBANKS"
    assert any(g["metric"] == "inadimplencia_90d_pct" for g in ok["gaps"])

    unknown = diagnose_institution_gaps("Banco Fantasma 999", SAMPLE_RECORDS)
    assert unknown["status"] == "error"
    assert unknown["recovery_hint"]

    missing = diagnose_institution_gaps("CAIXA", SAMPLE_RECORDS)
    assert missing["status"] == "error"
    assert "CAIXA" in (missing["error_message"] or "")
    assert missing["recovery_hint"]


def test_match_gcp_solutions_respects_segment_boundaries_and_complaint_drivers():
    # Incumbent with Pix/MED & Deati gaps -> may include incumbent core modernization, excludes neobank-only plays.
    inc = match_gcp_solutions_catalog(
        target_institution="BRADESCO",
        segment="INCUMBENTES",
        gap_pillars=["pix_med_spi", "reclamacoes_deati", "prudencial_ifdata_open_finance"],
        gap_metrics=["disponibilidade_spi_pct", "med_por_100k", "indice_reclamacoes"],
        complaint_driver="Irregularidades relacionadas a Pix e MED",
        max_solutions=5,
    )
    assert inc["status"] == "success"
    assert inc["advisory_mode"] == "gap_remediation"
    assert len(inc["solutions"]) == 5
    inc_ids = {s["blueprint"]["solution_id"] for s in inc["solutions"]}
    assert "fsi-neobank-multicloud-sovereign-ai" not in inc_ids
    assert "fsi-pix-med-realtime-antifraud" in inc_ids or "fsi-spi-active-active-spanner" in inc_ids

    # Neobank -> NEVER receives incumbent legacy mainframe modernization.
    neo = match_gcp_solutions_catalog(
        target_institution="NUBANK",
        segment="NEOBANKS",
        gap_pillars=["taxas_credito", "prudencial_ifdata_open_finance"],
        gap_metrics=["taxa_juros_mensal_pct", "inadimplencia_90d_pct"],
        complaint_driver="Cartão de crédito",
        max_solutions=5,
    )
    assert neo["status"] == "success"
    neo_ids = {s["blueprint"]["solution_id"] for s in neo["solutions"]}
    assert "fsi-incumbent-core-modernization-alloydb" not in neo_ids

    # Leadership expansion mode when no gaps are supplied.
    leader = match_gcp_solutions_catalog(target_institution="NUBANK", max_solutions=4)
    assert leader["status"] == "success"
    assert leader["advisory_mode"] == "leadership_expansion"
    assert len(leader["solutions"]) == 4


@dataclass
class _FakeEvent:
    author: str
    content: types.Content
    id: str = "ev-gcp-1"
    timestamp: float = 1700000100.0


@dataclass
class _FakeRunner:
    events: list[Any] = field(default_factory=list)

    async def run_async(self, *, user_id: str, session_id: str, new_message: types.Content):
        del user_id, session_id, new_message
        for ev in self.events:
            yield ev


def test_web_ui_streams_gcp_advisory_pipeline_and_exports_pdf():
    verdict_json = json.dumps(
        {
            "approved": True,
            "groundedness_score": 5,
            "issues": [],
            "summary": "Diagnóstico BCB e blueprints Google Cloud integralmente ancorados nas ferramentas.",
        }
    )
    advisory_md = (
        "# Plano de Oportunidades Google Cloud — Bradesco\n\n"
        "## Resumo Executivo\n\n"
        "Com base nos dados públicos do BCB (2026-Q3), o **Bradesco** apresenta oportunidades prioritárias "
        "em disponibilidade SPI (99,72%), antifraude Pix/MED e atendimento Deati.\n\n"
        "| Horizonte | Iniciativa Google Cloud | Pilar BCB | KPIs |\n"
        "| --- | --- | --- | --- |\n"
        "| Quick Win (0-90d) | Customer Engagement Suite PT-BR | Reclamações Deati | Índice Deati ↓ |\n"
        "| Escala Core (3-6m) | Antifraude Pix & MED (Pub/Sub + Vertex AI) | Pix / MED | MED/100k ↓ |\n"
        "| Transformacional (6-12m) | Ledger Pix Ativo-Ativo (Cloud Spanner) | Pix / SPI | Uptime SPI ↑ |\n"
    )
    fake_runner = _FakeRunner(
        events=[
            _FakeEvent(
                author="gcp_data_prep",
                content=types.Content(role="model", parts=[types.Part(text="Dados BCB reutilizados.")]),
            ),
            _FakeEvent(
                author="gcp_cloud_consultant",
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                id="call-diag",
                                name="diagnose_institution_gaps",
                                args={"target_institution": "BRADESCO", "benchmark_records": []},
                            )
                        )
                    ],
                ),
            ),
            _FakeEvent(
                author="gcp_cloud_consultant",
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                id="call-diag",
                                name="diagnose_institution_gaps",
                                response={
                                    "status": "success",
                                    "target_institution": "BRADESCO",
                                    "segment": "INCUMBENTES",
                                    "gaps": [{"severity": "CRITICO"}],
                                },
                            )
                        )
                    ],
                ),
            ),
            _FakeEvent(
                author="gcp_cloud_consultant",
                content=types.Content(role="model", parts=[types.Part(text="Rascunho consultor intermediário")]),
            ),
            _FakeEvent(
                author="gcp_advisory_critic",
                content=types.Content(role="model", parts=[types.Part(text=verdict_json)]),
            ),
            _FakeEvent(
                author="gcp_advisory_publisher",
                content=types.Content(role="model", parts=[types.Part(text=advisory_md)]),
            ),
        ]
    )
    app = create_app(
        session_service=InMemorySessionService(),
        runner=fake_runner,
        app_name="bacen_advisor",
    )
    client = TestClient(app)

    resp = client.post(
        "/api/chat/stream",
        json={"message": "Atue como consultor sênior Google Cloud para o Bradesco"},
    )
    assert resp.status_code == 200
    assert "Plano de Oportunidades Google Cloud" in resp.text
    assert "Rascunho consultor intermediário" not in resp.text
    assert "event: critic_verdict" in resp.text

    pdf_bytes = generate_executive_pdf(
        advisory_md,
        metadata=PdfReportMetadata(
            prompt="Plano Google Cloud para o Bradesco",
            agents=["bacen_coordinator", "gcp_data_prep", "gcp_cloud_consultant", "gcp_advisory_critic", "gcp_advisory_publisher"],
            models=["gemini-3-flash-preview", "gemini-3.1-pro-preview"],
            tool_calls_count=2,
            critic_verdict={"approved": True, "groundedness_score": 5, "issues": [], "summary": "OK"},
        ),
    )
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 4000
