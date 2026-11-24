"""Unit tests for all 7 BacenService analytical queries (offline seed mode)."""

import pytest
from src.application.bacen_service import bacen_service
from src.config import settings
from src.infrastructure.memory_cache import memory_cache


@pytest.fixture(autouse=True)
def offline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "enable_live_http_fetch", False)
    memory_cache.clear()


async def test_consultar_ranking_reclamacoes_sorts_lowest_index_first() -> None:
    res = await bacen_service.consultar_ranking_reclamacoes_bcb(segmento="NEOBANKS")
    rows = res["registros"]
    assert len(rows) == 5
    assert rows[0]["instituicao"] == "NUBANK"
    assert rows[0]["indice_reclamacoes"] <= rows[1]["indice_reclamacoes"]
    assert res["metadados_fonte"]["origem_leitura"] == "fallback_seed_ram"


async def test_consultar_taxas_juros_filters_modality_and_sorts_lowest_rate() -> None:
    res = await bacen_service.consultar_taxas_juros_credito(modalidade="rotativo")
    rows = res["registros"]
    assert len(rows) == 10
    assert all(r["modalidade"] == "CARTAO_ROTATIVO" for r in rows)
    assert rows[0]["taxa_juros_mensal_pct"] <= rows[-1]["taxa_juros_mensal_pct"]


async def test_consultar_estatisticas_pix_med_highlights_nubank_scale() -> None:
    res = await bacen_service.consultar_estatisticas_pix_med(segmento="TODOS")
    assert res["registros"][0]["instituicao"] == "NUBANK"
    assert res["estatisticas_agregadas"]["meta_regulatoria_spi_pct"] == 99.8


async def test_consultar_saude_prudencial_ifdata() -> None:
    res = await bacen_service.consultar_saude_prudencial_ifdata(instituicao="Nu Pagamentos")
    assert len(res["registros"]) == 1
    row = res["registros"][0]
    assert row["instituicao"] == "NUBANK"
    assert row["indice_basileia_pct"] > 10.5
    assert row["disponibilidade_open_finance_pct"] >= 99.5


async def test_comparar_instituicoes_financeiras_joins_four_pillars() -> None:
    res = await bacen_service.comparar_instituicoes_financeiras(
        segmento="TODOS",
        modalidade_credito="CARTAO_ROTATIVO",
        instituicoes=["Nubank", "Itaú", "Bradesco", "Inter"],
    )
    rows = res["registros"]
    assert len(rows) == 4
    assert [r["posicao_ranking"] for r in rows] == [1, 2, 3, 4]
    for row in rows:
        for col in (
            "score_reclamacoes_0_10",
            "score_taxas_credito_0_10",
            "score_pix_med_0_10",
            "score_prudencial_0_10",
            "score_competitivo_0_10",
        ):
            assert 1.0 <= row[col] <= 10.0


async def test_buscar_datasets_and_glossary() -> None:
    ckan = await bacen_service.buscar_datasets_dados_abertos_bcb(termo_busca="pix")
    assert ckan["registros"]
    assert any("pix" in r["dataset_id"] for r in ckan["registros"])

    gloss = await bacen_service.consultar_glossario_metodologia_bcb(topico="pix_med")
    assert len(gloss["registros"]) == 1
    assert "Resolução BCB" in gloss["registros"][0]["normativo"]
