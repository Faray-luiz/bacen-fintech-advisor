"""In-memory Polars query service across the 4 official Banco Central / Open Finance pillars.

Pillars:
1. Ranking de Reclamações BCB (Deati)
2. Taxas de Juros de Crédito (Olinda taxaJuros v2)
3. Estatísticas Pix & Fraudes MED (Olinda Pix_DadosAbertos v1 + SPI)
4. Saúde Prudencial (IF.data) & Open Finance Fase 1
5. Consolidated 4-pillar competitive benchmark (Nubank, neobanks and incumbent S1 banks)
"""

from __future__ import annotations

from typing import Any

import polars as pl

from src.config import settings
from src.domain.entities import FonteMetadados, RespostaPadraoBacen
from src.domain.glossary import get_glossary_content
from src.domain.normalizer import (
    normalize_credit_modality,
    normalize_institution,
    normalize_segment,
)
from src.infrastructure.bacen_http_client import bacen_http_client


def _clamp_limit(limite: int | None) -> int:
    if limite is None or limite <= 0:
        return settings.default_max_rows
    return min(limite, settings.max_allowed_rows)


def _records_to_markdown_table(records: list[dict[str, Any]], max_rows: int = 15) -> str:
    """Renders records as a compact Markdown table."""
    if not records:
        return "_Nenhum registro encontrado para os filtros informados._"
    sample = records[:max_rows]
    headers = list(sample[0].keys())
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_lines = [
        "| " + " | ".join(str(row.get(h, "")) for h in headers) + " |" for row in sample
    ]
    return "\n".join([header_line, separator_line, *body_lines])


class BacenService:
    """Executes analytical queries and cross-pillar joins in memory with Polars."""

    async def consultar_ranking_reclamacoes_bcb(
        self,
        instituicao: str | None = None,
        segmento: str | None = None,
        motivo: str | None = None,
        trimestre: str | None = None,
        limite: int = 25,
    ) -> dict[str, Any]:
        df, origin = await bacen_http_client.get_reclamacoes_df()
        inst_norm = normalize_institution(instituicao)
        seg_norm = normalize_segment(segmento)
        row_limit = _clamp_limit(limite)

        filtered = df
        if inst_norm:
            filtered = filtered.filter(pl.col("instituicao") == inst_norm)
        if seg_norm and seg_norm != "TODOS":
            filtered = filtered.filter(pl.col("segmento") == seg_norm)
        if motivo and motivo.strip():
            filtered = filtered.filter(
                pl.col("principal_motivo").str.to_lowercase().str.contains(motivo.strip().lower())
            )
        if trimestre and trimestre.strip():
            filtered = filtered.filter(pl.col("trimestre") == trimestre.strip().upper())

        # Lower complaint index is better.
        filtered = filtered.sort(["trimestre", "indice_reclamacoes"], descending=[True, False])
        total_found = filtered.height
        records = filtered.head(row_limit).to_dicts()
        periodo = records[0]["trimestre"] if records else None

        if total_found > 0:
            media_ind = round(float(filtered["indice_reclamacoes"].mean() or 0.0), 2)
            melhor = filtered.row(0, named=True)
            pior = filtered.sort("indice_reclamacoes", descending=True).row(0, named=True)
            resumo = (
                f"Analisadas {total_found} instituições no Ranking de Reclamações BCB ({periodo}). "
                f"Índice médio: {media_ind} reclamações procedentes por milhão de clientes (menor é melhor). "
                f"Melhor desempenho no recorte: {melhor['instituicao']} (índice {melhor['indice_reclamacoes']})."
            )
            stats = {
                "media_indice_reclamacoes": media_ind,
                "melhor_desempenho_menor_indice": {
                    "instituicao": melhor["instituicao"],
                    "indice_reclamacoes": melhor["indice_reclamacoes"],
                    "principal_motivo": melhor["principal_motivo"],
                },
                "maior_indice_reclamacoes": {
                    "instituicao": pior["instituicao"],
                    "indice_reclamacoes": pior["indice_reclamacoes"],
                    "principal_motivo": pior["principal_motivo"],
                },
            }
        else:
            resumo = "Nenhum registro do Ranking de Reclamações BCB encontrado para os filtros informados."
            stats = {"media_indice_reclamacoes": None}

        return RespostaPadraoBacen(
            resumo_executivo=resumo,
            estatisticas_agregadas=stats,
            registros=records,
            tabela_markdown=_records_to_markdown_table(records),
            metadados_fonte=FonteMetadados(
                pilar="BCB Ranking de Reclamações (Deati)",
                url_oficial_bcb=settings.bcb_ranking_reclamacoes_url,
                origem_leitura=origin,
                periodo_referencia=periodo,
                filtros_aplicados={
                    "instituicao": inst_norm,
                    "segmento": seg_norm,
                    "motivo": motivo,
                    "trimestre": trimestre,
                },
                total_registros_encontrados=total_found,
                registros_retornados=len(records),
            ),
        ).model_dump()

    async def consultar_taxas_juros_credito(
        self,
        instituicao: str | None = None,
        segmento: str | None = None,
        modalidade: str | None = None,
        ano_mes: str | None = None,
        limite: int = 25,
    ) -> dict[str, Any]:
        df, origin = await bacen_http_client.get_taxas_juros_df()
        inst_norm = normalize_institution(instituicao)
        seg_norm = normalize_segment(segmento)
        mod_norm = normalize_credit_modality(modalidade)
        row_limit = _clamp_limit(limite)

        filtered = df
        if inst_norm:
            filtered = filtered.filter(pl.col("instituicao") == inst_norm)
        if seg_norm and seg_norm != "TODOS":
            filtered = filtered.filter(pl.col("segmento") == seg_norm)
        if mod_norm:
            filtered = filtered.filter(pl.col("modalidade") == mod_norm)
        if ano_mes and ano_mes.strip():
            filtered = filtered.filter(pl.col("ano_mes") == ano_mes.strip())

        # Lower monthly interest rate is more competitive for borrowers.
        filtered = filtered.sort(["ano_mes", "taxa_juros_mensal_pct"], descending=[True, False])
        total_found = filtered.height
        records = filtered.head(row_limit).to_dicts()
        periodo = records[0]["ano_mes"] if records else None

        if total_found > 0:
            media_mensal = round(float(filtered["taxa_juros_mensal_pct"].mean() or 0.0), 2)
            menor_taxa = filtered.row(0, named=True)
            resumo = (
                f"Consultados {total_found} registros de Taxas de Juros BCB/Olinda ({periodo}). "
                f"Taxa mensal média no recorte: {media_mensal}% a.m. "
                f"Menor taxa: {menor_taxa['instituicao']} em {menor_taxa['modalidade']} "
                f"({menor_taxa['taxa_juros_mensal_pct']}% a.m. / {menor_taxa['taxa_juros_anual_pct']}% a.a.)."
            )
            stats = {
                "media_taxa_mensal_pct": media_mensal,
                "menor_taxa_recorte": {
                    "instituicao": menor_taxa["instituicao"],
                    "modalidade": menor_taxa["modalidade"],
                    "taxa_juros_mensal_pct": menor_taxa["taxa_juros_mensal_pct"],
                    "taxa_juros_anual_pct": menor_taxa["taxa_juros_anual_pct"],
                },
            }
        else:
            resumo = "Nenhum registro de taxas de juros encontrado para os filtros informados."
            stats = {"media_taxa_mensal_pct": None}

        return RespostaPadraoBacen(
            resumo_executivo=resumo,
            estatisticas_agregadas=stats,
            registros=records,
            tabela_markdown=_records_to_markdown_table(records),
            metadados_fonte=FonteMetadados(
                pilar="BCB Olinda Taxas de Juros de Crédito (v2)",
                url_oficial_bcb=settings.bcb_olinda_taxas_juros_url,
                origem_leitura=origin,
                periodo_referencia=periodo,
                filtros_aplicados={
                    "instituicao": inst_norm,
                    "segmento": seg_norm,
                    "modalidade": mod_norm,
                    "ano_mes": ano_mes,
                },
                total_registros_encontrados=total_found,
                registros_retornados=len(records),
            ),
        ).model_dump()

    async def consultar_estatisticas_pix_med(
        self,
        instituicao: str | None = None,
        segmento: str | None = None,
        ano_mes: str | None = None,
        limite: int = 25,
    ) -> dict[str, Any]:
        df, origin = await bacen_http_client.get_pix_med_df()
        inst_norm = normalize_institution(instituicao)
        seg_norm = normalize_segment(segmento)
        row_limit = _clamp_limit(limite)

        filtered = df
        if inst_norm:
            filtered = filtered.filter(pl.col("instituicao") == inst_norm)
        if seg_norm and seg_norm != "TODOS":
            filtered = filtered.filter(pl.col("segmento") == seg_norm)
        if ano_mes and ano_mes.strip():
            filtered = filtered.filter(pl.col("ano_mes") == ano_mes.strip())

        filtered = filtered.sort(["ano_mes", "transacoes_pix_milhoes"], descending=[True, True])
        total_found = filtered.height
        records = filtered.head(row_limit).to_dicts()
        periodo = records[0]["ano_mes"] if records else None

        if total_found > 0:
            total_chaves = round(float(filtered["chaves_pix_ativas_milhoes"].sum() or 0.0), 1)
            media_spi = round(float(filtered["taxa_disponibilidade_spi_pct"].mean() or 0.0), 2)
            media_med = round(float(filtered["solicitacoes_med_por_100k"].mean() or 0.0), 2)
            lider_tx = filtered.row(0, named=True)
            resumo = (
                f"Analisadas {total_found} instituições no ecossistema Pix/MED ({periodo}). "
                f"Total de chaves DICT no recorte: {total_chaves}M | Disponibilidade média SPI: {media_spi}% "
                f"(meta BCB >= 99,8%) | Média MED: {media_med}/100k transações. "
                f"Líder em volume transacional: {lider_tx['instituicao']} ({lider_tx['transacoes_pix_milhoes']}M tx/mês)."
            )
            stats = {
                "total_chaves_pix_milhoes": total_chaves,
                "media_disponibilidade_spi_pct": media_spi,
                "media_solicitacoes_med_por_100k": media_med,
                "meta_regulatoria_spi_pct": 99.8,
                "lider_transacoes_pix": {
                    "instituicao": lider_tx["instituicao"],
                    "transacoes_pix_milhoes": lider_tx["transacoes_pix_milhoes"],
                    "taxa_disponibilidade_spi_pct": lider_tx["taxa_disponibilidade_spi_pct"],
                },
            }
        else:
            resumo = "Nenhum registro de estatísticas Pix/MED encontrado para os filtros informados."
            stats = {"total_chaves_pix_milhoes": None}

        return RespostaPadraoBacen(
            resumo_executivo=resumo,
            estatisticas_agregadas=stats,
            registros=records,
            tabela_markdown=_records_to_markdown_table(records),
            metadados_fonte=FonteMetadados(
                pilar="BCB Olinda Pix Dados Abertos, SPI e Fraudes MED",
                url_oficial_bcb=settings.bcb_olinda_pix_chaves_url,
                origem_leitura=origin,
                periodo_referencia=periodo,
                filtros_aplicados={
                    "instituicao": inst_norm,
                    "segmento": seg_norm,
                    "ano_mes": ano_mes,
                },
                total_registros_encontrados=total_found,
                registros_retornados=len(records),
            ),
        ).model_dump()

    async def consultar_saude_prudencial_ifdata(
        self,
        instituicao: str | None = None,
        segmento: str | None = None,
        trimestre: str | None = None,
        limite: int = 25,
    ) -> dict[str, Any]:
        df, origin = await bacen_http_client.get_prudencial_ifdata_df()
        inst_norm = normalize_institution(instituicao)
        seg_norm = normalize_segment(segmento)
        row_limit = _clamp_limit(limite)

        filtered = df
        if inst_norm:
            filtered = filtered.filter(pl.col("instituicao") == inst_norm)
        if seg_norm and seg_norm != "TODOS":
            filtered = filtered.filter(pl.col("segmento") == seg_norm)
        if trimestre and trimestre.strip():
            filtered = filtered.filter(pl.col("trimestre") == trimestre.strip().upper())

        filtered = filtered.sort(["trimestre", "roe_anualizado_pct"], descending=[True, True])
        total_found = filtered.height
        records = filtered.head(row_limit).to_dicts()
        periodo = records[0]["trimestre"] if records else None

        if total_found > 0:
            media_basileia = round(float(filtered["indice_basileia_pct"].mean() or 0.0), 2)
            media_roe = round(float(filtered["roe_anualizado_pct"].mean() or 0.0), 2)
            media_of = round(float(filtered["disponibilidade_open_finance_pct"].mean() or 0.0), 2)
            lider_roe = filtered.row(0, named=True)
            resumo = (
                f"Consultados {total_found} conglomerados no IF.data & Open Finance ({periodo}). "
                f"Basileia médio: {media_basileia}% (mínimo regulatório >= 10,5%) | ROE médio: {media_roe}% | "
                f"Disponibilidade Open Finance média: {media_of}% (meta >= 99,5%). "
                f"Maior ROE no recorte: {lider_roe['instituicao']} ({lider_roe['roe_anualizado_pct']}%)."
            )
            stats = {
                "media_indice_basileia_pct": media_basileia,
                "media_roe_anualizado_pct": media_roe,
                "media_disponibilidade_open_finance_pct": media_of,
                "piso_regulatorio_basileia_pct": 10.5,
                "meta_open_finance_pct": 99.5,
                "lider_roe": {
                    "instituicao": lider_roe["instituicao"],
                    "roe_anualizado_pct": lider_roe["roe_anualizado_pct"],
                    "indice_basileia_pct": lider_roe["indice_basileia_pct"],
                },
            }
        else:
            resumo = "Nenhum indicador prudencial IF.data / Open Finance encontrado para os filtros informados."
            stats = {"media_indice_basileia_pct": None}

        return RespostaPadraoBacen(
            resumo_executivo=resumo,
            estatisticas_agregadas=stats,
            registros=records,
            tabela_markdown=_records_to_markdown_table(records),
            metadados_fonte=FonteMetadados(
                pilar="BCB IF.data (Prudencial / Basileia III) & Open Finance Fase 1",
                url_oficial_bcb=settings.bcb_ifdata_open_finance_url,
                origem_leitura=origin,
                periodo_referencia=periodo,
                filtros_aplicados={
                    "instituicao": inst_norm,
                    "segmento": seg_norm,
                    "trimestre": trimestre,
                },
                total_registros_encontrados=total_found,
                registros_retornados=len(records),
            ),
        ).model_dump()

    async def comparar_instituicoes_financeiras(
        self,
        segmento: str = "TODOS",
        modalidade_credito: str = "CARTAO_ROTATIVO",
        instituicoes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Joins all 4 BCB / Open Finance pillars and produces a normalized 0-10 benchmark."""
        seg_norm = normalize_segment(segmento) or "TODOS"
        mod_norm = normalize_credit_modality(modalidade_credito) or "CARTAO_ROTATIVO"
        insts_norm = [
            normalize_institution(item) for item in (instituicoes or []) if normalize_institution(item)
        ]

        df_rec, origin_rec = await bacen_http_client.get_reclamacoes_df()
        df_tax, origin_tax = await bacen_http_client.get_taxas_juros_df()
        df_pix, _ = await bacen_http_client.get_pix_med_df()
        df_pru, _ = await bacen_http_client.get_prudencial_ifdata_df()

        base = df_rec
        if seg_norm != "TODOS":
            base = base.filter(pl.col("segmento") == seg_norm)
        if insts_norm:
            base = base.filter(pl.col("instituicao").is_in(insts_norm))

        rec_agg = (
            base.sort("trimestre", descending=True)
            .group_by("instituicao")
            .agg(
                pl.col("segmento").first().alias("segmento"),
                pl.col("indice_reclamacoes").first().alias("indice_reclamacoes"),
                pl.col("principal_motivo").first().alias("principal_motivo_reclamacao"),
                pl.col("trimestre").first().alias("trimestre_ref"),
            )
        )

        tax_sub = df_tax.filter(pl.col("modalidade") == mod_norm)
        tax_agg = (
            tax_sub.sort("ano_mes", descending=True)
            .group_by("instituicao")
            .agg(
                pl.col("taxa_juros_mensal_pct").first().alias("taxa_juros_mensal_pct"),
                pl.col("taxa_juros_anual_pct").first().alias("taxa_juros_anual_pct"),
                pl.col("ano_mes").first().alias("mes_taxas_ref"),
            )
        )

        pix_agg = (
            df_pix.sort("ano_mes", descending=True)
            .group_by("instituicao")
            .agg(
                pl.col("chaves_pix_ativas_milhoes").first().alias("chaves_pix_milhoes"),
                pl.col("taxa_disponibilidade_spi_pct").first().alias("disponibilidade_spi_pct"),
                pl.col("solicitacoes_med_por_100k").first().alias("med_por_100k"),
                pl.col("taxa_devolucao_med_pct").first().alias("taxa_devolucao_med_pct"),
            )
        )

        pru_agg = (
            df_pru.sort("trimestre", descending=True)
            .group_by("instituicao")
            .agg(
                pl.col("indice_basileia_pct").first().alias("indice_basileia_pct"),
                pl.col("roe_anualizado_pct").first().alias("roe_anualizado_pct"),
                pl.col("taxa_inadimplencia_90d_pct").first().alias("inadimplencia_90d_pct"),
                pl.col("disponibilidade_open_finance_pct").first().alias("disponibilidade_open_finance_pct"),
            )
        )

        # Normalize each pillar to a 0-10 scale (higher is ALWAYS better; inverse metrics inverted):
        # - Complaints: 10 - (indice_reclamacoes / 6.0), clamped [1.0, 10.0]
        # - Credit rate: 10 - ((taxa_juros_mensal_pct - 2.0) * 0.45), clamped [1.0, 10.0]
        # - Pix/MED: SPI uptime bonus + MED recovery - MED fraud incidence, clamped [1.0, 10.0]
        # - Prudential/OF: Basel + ROE + Open Finance uptime, clamped [1.0, 10.0]
        joined = (
            rec_agg.join(tax_agg, on="instituicao", how="left")
            .join(pix_agg, on="instituicao", how="left")
            .join(pru_agg, on="instituicao", how="left")
            .with_columns(
                (10.0 - pl.col("indice_reclamacoes").fill_null(30.0) / 6.0)
                .clip(1.0, 10.0)
                .round(2)
                .alias("score_reclamacoes_0_10"),
                (10.0 - (pl.col("taxa_juros_mensal_pct").fill_null(12.0) - 2.0) * 0.45)
                .clip(1.0, 10.0)
                .round(2)
                .alias("score_taxas_credito_0_10"),
                (
                    5.0
                    + (pl.col("disponibilidade_spi_pct").fill_null(99.85) - 99.80) * 20.0
                    + (pl.col("taxa_devolucao_med_pct").fill_null(22.0) / 15.0)
                    - (pl.col("med_por_100k").fill_null(7.5) / 8.0)
                )
                .clip(1.0, 10.0)
                .round(2)
                .alias("score_pix_med_0_10"),
                (
                    3.5
                    + (pl.col("indice_basileia_pct").fill_null(15.0) - 10.5) * 0.45
                    + (pl.col("roe_anualizado_pct").fill_null(15.0) / 10.0)
                    + (pl.col("disponibilidade_open_finance_pct").fill_null(99.8) - 99.5) * 3.0
                )
                .clip(1.0, 10.0)
                .round(2)
                .alias("score_prudencial_0_10"),
            )
            .with_columns(
                (
                    pl.col("score_reclamacoes_0_10") * 0.30
                    + pl.col("score_taxas_credito_0_10") * 0.25
                    + pl.col("score_pix_med_0_10") * 0.25
                    + pl.col("score_prudencial_0_10") * 0.20
                )
                .round(2)
                .alias("score_competitivo_0_10")
            )
            .sort("score_competitivo_0_10", descending=True)
        )

        records = joined.to_dicts()
        for idx, row in enumerate(records, start=1):
            row["posicao_ranking"] = idx

        origin = origin_tax if origin_tax == "http_direto_bcb" else origin_rec
        periodo = records[0].get("trimestre_ref") if records else None

        if records:
            top = records[0]
            resumo = (
                f"Benchmark consolidado de {len(records)} instituições ({seg_norm} | crédito: {mod_norm}): "
                f"1º lugar: {top['instituicao']} (Score {top['score_competitivo_0_10']}/10 | "
                f"Índice Reclamações {top['indice_reclamacoes']} | Taxa {top.get('taxa_juros_mensal_pct')}% a.m. | "
                f"SPI {top.get('disponibilidade_spi_pct')}% | Basileia {top.get('indice_basileia_pct')}%)."
            )
            stats = {
                "segmento_comparado": seg_norm,
                "modalidade_credito": mod_norm,
                "total_instituicoes_comparadas": len(records),
                "lider_benchmark": top,
                "pesos_score_consolidado": {
                    "reclamacoes_bcb": "30%",
                    "taxas_credito": "25%",
                    "pix_med": "25%",
                    "prudencial_open_finance": "20%",
                },
            }
        else:
            resumo = f"Nenhuma instituição encontrada para o benchmark ({seg_norm} / {mod_norm})."
            stats = {"segmento_comparado": seg_norm, "total_instituicoes_comparadas": 0}

        return RespostaPadraoBacen(
            resumo_executivo=resumo,
            estatisticas_agregadas=stats,
            registros=records,
            tabela_markdown=_records_to_markdown_table(records),
            metadados_fonte=FonteMetadados(
                pilar="Benchmark Consolidado 4 Pilares BCB & Open Finance",
                url_oficial_bcb=settings.bcb_dados_abertos_portal_url,
                origem_leitura=origin,
                periodo_referencia=periodo,
                filtros_aplicados={
                    "segmento": seg_norm,
                    "modalidade_credito": mod_norm,
                    "instituicoes": insts_norm,
                },
                total_registros_encontrados=len(records),
                registros_retornados=len(records),
            ),
        ).model_dump()

    async def buscar_datasets_dados_abertos_bcb(
        self,
        termo_busca: str = "pix taxas juros reclamacoes",
        limite: int = 10,
    ) -> dict[str, Any]:
        row_limit = min(max(1, limite), 25)
        packages, origin = await bacen_http_client.search_ckan_datasets(
            termo_busca=termo_busca, limite=row_limit
        )
        resumo = f"Encontrados {len(packages)} conjuntos de dados abertos do Banco Central para '{termo_busca}'."
        return RespostaPadraoBacen(
            resumo_executivo=resumo,
            estatisticas_agregadas={"termo_busca": termo_busca, "total_pacotes": len(packages)},
            registros=packages,
            tabela_markdown=_records_to_markdown_table(packages),
            metadados_fonte=FonteMetadados(
                pilar="Catálogo CKAN / Portal de Dados Abertos do Banco Central",
                url_oficial_bcb=settings.bcb_ckan_api_url,
                origem_leitura=origin,
                filtros_aplicados={"termo_busca": termo_busca, "limite": row_limit},
                total_registros_encontrados=len(packages),
                registros_retornados=len(packages),
            ),
        ).model_dump()

    async def consultar_glossario_metodologia_bcb(
        self,
        topico: str | None = "geral",
    ) -> dict[str, Any]:
        conteudo = get_glossary_content(topico)
        topicos_retornados = list(conteudo.keys())
        registros = [{"topico": k, **v} for k, v in conteudo.items()]
        resumo = (
            f"Glossário regulatório BCB & Open Finance carregado para os tópicos: {', '.join(topicos_retornados)}."
        )
        return RespostaPadraoBacen(
            resumo_executivo=resumo,
            estatisticas_agregadas={
                "topico_solicitado": topico or "geral",
                "topicos_retornados": topicos_retornados,
            },
            registros=registros,
            tabela_markdown=_records_to_markdown_table(
                [{"topico": k, "titulo": v.get("titulo", "")} for k, v in conteudo.items()]
            ),
            metadados_fonte=FonteMetadados(
                pilar="Glossário e Metodologia Regulatória BCB / Open Finance",
                url_oficial_bcb=settings.bcb_dados_abertos_portal_url,
                origem_leitura="memoria_interna",
                filtros_aplicados={"topico": topico},
                total_registros_encontrados=len(registros),
                registros_retornados=len(registros),
            ),
        ).model_dump()


bacen_service = BacenService()
