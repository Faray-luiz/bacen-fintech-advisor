"""Unit tests for Feature 1 (What-If Simulator) and Feature 2 (Boardroom War Room & Roleplay)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from bacen_advisor.schemas import TOOL_JSON_SCHEMAS
from bacen_advisor.tools.simulation_tools import (
    compute_pillar_scores,
    simulate_bcb_what_if_scenario,
)
from web_ui.server import create_app

_SAMPLE_RECORDS = [
    {
        "instituicao": "NUBANK",
        "segmento": "NEOBANKS",
        "indice_reclamacoes": 14.8,
        "principal_motivo_reclamacao": "Irregularidades Pix/MED",
        "taxa_juros_mensal_pct": 11.45,
        "disponibilidade_spi_pct": 99.96,
        "med_por_100k": 6.4,
        "taxa_devolucao_med_pct": 26.5,
        "indice_basileia_pct": 16.4,
        "roe_anualizado_pct": 28.4,
        "inadimplencia_90d_pct": 6.1,
        "disponibilidade_open_finance_pct": 99.91,
    },
    {
        "instituicao": "ITAU",
        "segmento": "INCUMBENTES",
        "indice_reclamacoes": 21.4,
        "principal_motivo_reclamacao": "Integridade e segurança",
        "taxa_juros_mensal_pct": 12.80,
        "disponibilidade_spi_pct": 99.94,
        "med_por_100k": 5.9,
        "taxa_devolucao_med_pct": 27.1,
        "indice_basileia_pct": 16.8,
        "roe_anualizado_pct": 22.1,
        "inadimplencia_90d_pct": 2.7,
        "disponibilidade_open_finance_pct": 99.88,
    },
    {
        "instituicao": "BRADESCO",
        "segmento": "INCUMBENTES",
        "indice_reclamacoes": 32.1,
        "principal_motivo_reclamacao": "Cobrança irregular de tarifa ou encargo em cartão",
        "taxa_juros_mensal_pct": 13.40,
        "disponibilidade_spi_pct": 99.89,
        "med_por_100k": 7.5,
        "taxa_devolucao_med_pct": 22.9,
        "indice_basileia_pct": 15.6,
        "roe_anualizado_pct": 12.8,
        "inadimplencia_90d_pct": 4.2,
        "disponibilidade_open_finance_pct": 99.79,
    },
    {
        "instituicao": "INTER",
        "segmento": "NEOBANKS",
        "indice_reclamacoes": 41.2,
        "principal_motivo_reclamacao": "Cartão de crédito e contestação",
        "taxa_juros_mensal_pct": 11.90,
        "disponibilidade_spi_pct": 99.92,
        "med_por_100k": 8.2,
        "taxa_devolucao_med_pct": 20.5,
        "indice_basileia_pct": 15.8,
        "roe_anualizado_pct": 14.5,
        "inadimplencia_90d_pct": 4.5,
        "disponibilidade_open_finance_pct": 99.84,
    },
]


def test_tool_json_schemas_includes_what_if_simulator():
    assert "simulate_bcb_what_if_scenario" in TOOL_JSON_SCHEMAS
    schema = TOOL_JSON_SCHEMAS["simulate_bcb_what_if_scenario"]
    assert "target_institution" in schema["input"]["properties"]
    assert "overrides" in schema["input"]["properties"]
    assert "positions_gained" in schema["output"]["properties"]


def test_what_if_simulation_moves_bradesco_ahead_of_itau_and_matches_blueprints():
    res = simulate_bcb_what_if_scenario(
        target_institution="Bradesco",
        benchmark_records=_SAMPLE_RECORDS,
        overrides={
            "indice_reclamacoes": 16.0,
            "taxa_juros_mensal_pct": 11.0,
            "disponibilidade_spi_pct": 99.97,
            "med_por_100k": 5.0,
            "taxa_devolucao_med_pct": 34.0,
            "roe_anualizado_pct": 21.0,
        },
    )
    assert res["status"] == "success"
    assert res["target_institution"] == "BRADESCO"
    assert res["position_before"] == 3
    assert res["position_after"] < res["position_before"]
    assert res["positions_gained"] >= 1
    assert "ITAU" in res["overtaken_competitors"]
    assert res["score_delta"] > 1.0
    assert len(res["pillar_deltas"]) == 4
    assert all(p["delta_score"] >= 0 for p in res["pillar_deltas"])
    assert len(res["recommended_gcp_blueprints"]) >= 1
    assert len(res["business_value_drivers"]) >= 1
    assert res["regulatory_alerts"] == []


def test_what_if_flags_bcb_regulatory_floor_violations():
    res = simulate_bcb_what_if_scenario(
        target_institution="BRADESCO",
        benchmark_records=_SAMPLE_RECORDS,
        overrides={
            "disponibilidade_spi_pct": 99.65,
            "disponibilidade_open_finance_pct": 99.20,
            "indice_basileia_pct": 10.8,
        },
    )
    assert res["status"] == "success"
    assert len(res["regulatory_alerts"]) == 3
    assert any("99,80%" in a for a in res["regulatory_alerts"])
    assert any("99,50%" in a for a in res["regulatory_alerts"])
    assert any("11,50%" in a for a in res["regulatory_alerts"])


def test_what_if_returns_guided_error_on_unknown_bank_or_bad_bounds():
    bad_bank = simulate_bcb_what_if_scenario(
        target_institution="BANCO_INEXISTENTE_999",
        benchmark_records=_SAMPLE_RECORDS,
        overrides={"indice_reclamacoes": 10.0},
    )
    assert bad_bank["status"] == "error"
    assert bad_bank["recovery_hint"]

    bad_override = simulate_bcb_what_if_scenario(
        target_institution="NUBANK",
        benchmark_records=_SAMPLE_RECORDS,
        overrides={"disponibilidade_spi_pct": 120.0},
    )
    assert bad_override["status"] == "error"
    assert bad_override["recovery_hint"]


def test_compute_pillar_scores_matches_mcp_bacen_formula():
    from bacen_advisor.schemas import InstitutionBenchmarkSnapshot

    snap = InstitutionBenchmarkSnapshot.model_validate(_SAMPLE_RECORDS[0])
    scores = compute_pillar_scores(snap)
    assert scores["reclamacoes"] == round(10.0 - 14.8 / 6.0, 2)
    assert scores["taxas_credito"] == round(10.0 - (11.45 - 2.0) * 0.45, 2)
    assert 1.0 <= scores["pix_med"] <= 10.0
    assert 1.0 <= scores["prudencial"] <= 10.0


def test_web_ui_simulator_endpoints_and_auth_protection():
    fake_baseline = {
        "modalidade_credito": "CARTAO_ROTATIVO",
        "periodo_referencia": "2026-Q3",
        "origem_leitura": "unit_test",
        "pilar": "Benchmark Consolidado 4 Pilares",
        "records": _SAMPLE_RECORDS,
        "weights_default": {"reclamacoes": 0.30, "taxas_credito": 0.25, "pix_med": 0.25, "prudencial": 0.20},
    }

    # Open mode (dev): works directly
    app_open = create_app(baseline_provider=lambda _mod: fake_baseline)
    client = TestClient(app_open)

    home = client.get("/")
    assert home.status_code == 200
    assert "whatIfModalBackdrop" in home.text
    assert "warRoomModalBackdrop" in home.text
    assert "openWhatIfBtn" in home.text
    assert "openWarRoomBtn" in home.text
    assert "accountPopover" in home.text
    assert "homeBankStrip" in home.text
    assert "whatIfMoreToggle" in home.text
    assert "roleplayBanner" in home.text
    assert "sidebarStatusBtn" in home.text
    assert "sessionSearchInput" in home.text

    base_resp = client.get("/api/simulator/baseline")
    assert base_resp.status_code == 200
    assert len(base_resp.json()["records"]) == 4

    sim_resp = client.post(
        "/api/simulator/what-if",
        json={
            "target_institution": "BRADESCO",
            "overrides": {
                "indice_reclamacoes": 15.0,
                "taxa_juros_mensal_pct": 11.2,
                "disponibilidade_spi_pct": 99.97,
                "med_por_100k": 4.5,
                "taxa_devolucao_med_pct": 35.0,
            },
        },
    )
    assert sim_resp.status_code == 200
    body = sim_resp.json()
    assert body["positions_gained"] >= 1
    assert body["baseline_meta"]["periodo_referencia"] == "2026-Q3"

    # Protected mode (prod): endpoints strictly enforce 401 without session cookie
    app_locked = create_app(
        access_token="super-secret-token-1234",
        baseline_provider=lambda _mod: fake_baseline,
    )
    locked = TestClient(app_locked)
    assert locked.get("/api/simulator/baseline").status_code == 401
    assert (
        locked.post(
            "/api/simulator/what-if",
            json={"target_institution": "BRADESCO", "overrides": {"indice_reclamacoes": 15.0}},
        ).status_code
        == 401
    )
