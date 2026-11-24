"""Deterministic public-domain reference snapshots for offline tests, CI and fallback resilience.

Whenever the live Banco Central do Brasil APIs (``olinda.bcb.gov.br`` /
``dadosabertos.bcb.gov.br``) are unreachable, rate-limited or disabled in offline tests,
``bacen_http_client`` serves these snapshots and explicitly tags
``metadados_fonte.origem_leitura = "fallback_seed_ram"``.

All values are illustrative public-benchmark snapshots covering major Brazilian digital
banks (neobanks) and S1 incumbent banks — never confidential or customer-specific data.
"""

from __future__ import annotations

from typing import Any

# Pillar 1: Ranking de Reclamações BCB (Deati) — lower `indice_reclamacoes` is better.
FALLBACK_RECLAMACOES_BCB: list[dict[str, Any]] = [
    {
        "instituicao": "NUBANK",
        "nome_oficial_bcb": "NU PAGAMENTOS S.A. - INSTITUICAO DE PAGAMENTO",
        "segmento": "NEOBANKS",
        "trimestre": "2026-Q3",
        "indice_reclamacoes": 14.8,
        "reclamacoes_procedentes": 1598,
        "total_clientes_ccs": 108_000_000,
        "principal_motivo": "Irregularidades relacionadas a Pix e Mecanismo Especial de Devolução (MED)",
    },
    {
        "instituicao": "ITAU",
        "nome_oficial_bcb": "ITAU UNIBANCO S.A.",
        "segmento": "INCUMBENTES",
        "trimestre": "2026-Q3",
        "indice_reclamacoes": 21.4,
        "reclamacoes_procedentes": 2161,
        "total_clientes_ccs": 101_000_000,
        "principal_motivo": "Irregularidades relativas a integridade, confiabilidade ou segurança",
    },
    {
        "instituicao": "BANCO_DO_BRASIL",
        "nome_oficial_bcb": "BANCO DO BRASIL S.A.",
        "segmento": "INCUMBENTES",
        "trimestre": "2026-Q3",
        "indice_reclamacoes": 24.6,
        "reclamacoes_procedentes": 1918,
        "total_clientes_ccs": 78_000_000,
        "principal_motivo": "Oferta ou prestação de informação sobre crédito de forma inadequada",
    },
    {
        "instituicao": "CAIXA",
        "nome_oficial_bcb": "CAIXA ECONOMICA FEDERAL",
        "segmento": "INCUMBENTES",
        "trimestre": "2026-Q3",
        "indice_reclamacoes": 19.2,
        "reclamacoes_procedentes": 2918,
        "total_clientes_ccs": 152_000_000,
        "principal_motivo": "Irregularidades relacionadas a Pix e bloqueio cautelar",
    },
    {
        "instituicao": "BRADESCO",
        "nome_oficial_bcb": "BANCO BRADESCO S.A.",
        "segmento": "INCUMBENTES",
        "trimestre": "2026-Q3",
        "indice_reclamacoes": 32.1,
        "reclamacoes_procedentes": 3434,
        "total_clientes_ccs": 107_000_000,
        "principal_motivo": "Cobrança irregular de tarifa ou encargo em cartão de crédito",
    },
    {
        "instituicao": "SANTANDER",
        "nome_oficial_bcb": "BANCO SANTANDER (BRASIL) S.A.",
        "segmento": "INCUMBENTES",
        "trimestre": "2026-Q3",
        "indice_reclamacoes": 35.4,
        "reclamacoes_procedentes": 2407,
        "total_clientes_ccs": 68_000_000,
        "principal_motivo": "Oferta ou prestação de informação sobre crédito consignado",
    },
    {
        "instituicao": "INTER",
        "nome_oficial_bcb": "BANCO INTER S.A.",
        "segmento": "NEOBANKS",
        "trimestre": "2026-Q3",
        "indice_reclamacoes": 41.2,
        "reclamacoes_procedentes": 1483,
        "total_clientes_ccs": 36_000_000,
        "principal_motivo": "Irregularidades relacionadas a cartão de crédito e contestação",
    },
    {
        "instituicao": "C6_BANK",
        "nome_oficial_bcb": "BANCO C6 S.A.",
        "segmento": "NEOBANKS",
        "trimestre": "2026-Q3",
        "indice_reclamacoes": 48.9,
        "reclamacoes_procedentes": 1614,
        "total_clientes_ccs": 33_000_000,
        "principal_motivo": "Cobrança irregular de tarifa e oferta de crédito consignado",
    },
    {
        "instituicao": "MERCADO_PAGO",
        "nome_oficial_bcb": "MERCADO PAGO INSTITUICAO DE PAGAMENTO LTDA.",
        "segmento": "NEOBANKS",
        "trimestre": "2026-Q3",
        "indice_reclamacoes": 27.5,
        "reclamacoes_procedentes": 1568,
        "total_clientes_ccs": 57_000_000,
        "principal_motivo": "Irregularidades relacionadas a Pix e Mecanismo Especial de Devolução (MED)",
    },
    {
        "instituicao": "BTG_PACTUAL",
        "nome_oficial_bcb": "BANCO BTG PACTUAL S.A.",
        "segmento": "NEOBANKS",
        "trimestre": "2026-Q3",
        "indice_reclamacoes": 16.5,
        "reclamacoes_procedentes": 297,
        "total_clientes_ccs": 18_000_000,
        "principal_motivo": "Irregularidades relativas a atendimento e portabilidade",
    },
]

# Pillar 2: Taxas de Juros de Crédito (Olinda taxaJuros v2) — lower monthly rate is better.
FALLBACK_TAXAS_JUROS: list[dict[str, Any]] = [
    # CARTAO_ROTATIVO
    {"instituicao": "NUBANK", "segmento": "NEOBANKS", "modalidade": "CARTAO_ROTATIVO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 11.45, "taxa_juros_anual_pct": 267.40, "posicao_ranking_bcb": 4},
    {"instituicao": "ITAU", "segmento": "INCUMBENTES", "modalidade": "CARTAO_ROTATIVO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 12.80, "taxa_juros_anual_pct": 324.50, "posicao_ranking_bcb": 7},
    {"instituicao": "BANCO_DO_BRASIL", "segmento": "INCUMBENTES", "modalidade": "CARTAO_ROTATIVO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 10.20, "taxa_juros_anual_pct": 220.70, "posicao_ranking_bcb": 2},
    {"instituicao": "CAIXA", "segmento": "INCUMBENTES", "modalidade": "CARTAO_ROTATIVO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 9.85, "taxa_juros_anual_pct": 208.60, "posicao_ranking_bcb": 1},
    {"instituicao": "BRADESCO", "segmento": "INCUMBENTES", "modalidade": "CARTAO_ROTATIVO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 13.40, "taxa_juros_anual_pct": 352.30, "posicao_ranking_bcb": 8},
    {"instituicao": "SANTANDER", "segmento": "INCUMBENTES", "modalidade": "CARTAO_ROTATIVO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 13.95, "taxa_juros_anual_pct": 379.10, "posicao_ranking_bcb": 9},
    {"instituicao": "INTER", "segmento": "NEOBANKS", "modalidade": "CARTAO_ROTATIVO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 11.90, "taxa_juros_anual_pct": 285.60, "posicao_ranking_bcb": 5},
    {"instituicao": "C6_BANK", "segmento": "NEOBANKS", "modalidade": "CARTAO_ROTATIVO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 12.60, "taxa_juros_anual_pct": 315.40, "posicao_ranking_bcb": 6},
    {"instituicao": "MERCADO_PAGO", "segmento": "NEOBANKS", "modalidade": "CARTAO_ROTATIVO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 14.30, "taxa_juros_anual_pct": 397.00, "posicao_ranking_bcb": 10},
    {"instituicao": "BTG_PACTUAL", "segmento": "NEOBANKS", "modalidade": "CARTAO_ROTATIVO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 10.90, "taxa_juros_anual_pct": 246.20, "posicao_ranking_bcb": 3},
    # CREDITO_PESSOAL_NAO_CONSIGNADO
    {"instituicao": "NUBANK", "segmento": "NEOBANKS", "modalidade": "CREDITO_PESSOAL_NAO_CONSIGNADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 4.85, "taxa_juros_anual_pct": 76.50, "posicao_ranking_bcb": 4},
    {"instituicao": "ITAU", "segmento": "INCUMBENTES", "modalidade": "CREDITO_PESSOAL_NAO_CONSIGNADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 4.60, "taxa_juros_anual_pct": 71.55, "posicao_ranking_bcb": 3},
    {"instituicao": "BANCO_DO_BRASIL", "segmento": "INCUMBENTES", "modalidade": "CREDITO_PESSOAL_NAO_CONSIGNADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 4.15, "taxa_juros_anual_pct": 62.90, "posicao_ranking_bcb": 2},
    {"instituicao": "CAIXA", "segmento": "INCUMBENTES", "modalidade": "CREDITO_PESSOAL_NAO_CONSIGNADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 3.95, "taxa_juros_anual_pct": 59.20, "posicao_ranking_bcb": 1},
    {"instituicao": "BRADESCO", "segmento": "INCUMBENTES", "modalidade": "CREDITO_PESSOAL_NAO_CONSIGNADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 5.30, "taxa_juros_anual_pct": 85.80, "posicao_ranking_bcb": 6},
    {"instituicao": "SANTANDER", "segmento": "INCUMBENTES", "modalidade": "CREDITO_PESSOAL_NAO_CONSIGNADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 5.65, "taxa_juros_anual_pct": 93.40, "posicao_ranking_bcb": 8},
    {"instituicao": "INTER", "segmento": "NEOBANKS", "modalidade": "CREDITO_PESSOAL_NAO_CONSIGNADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 5.10, "taxa_juros_anual_pct": 81.60, "posicao_ranking_bcb": 5},
    {"instituicao": "C6_BANK", "segmento": "NEOBANKS", "modalidade": "CREDITO_PESSOAL_NAO_CONSIGNADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 5.45, "taxa_juros_anual_pct": 89.05, "posicao_ranking_bcb": 7},
    {"instituicao": "MERCADO_PAGO", "segmento": "NEOBANKS", "modalidade": "CREDITO_PESSOAL_NAO_CONSIGNADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 6.20, "taxa_juros_anual_pct": 105.80, "posicao_ranking_bcb": 9},
    {"instituicao": "BTG_PACTUAL", "segmento": "NEOBANKS", "modalidade": "CREDITO_PESSOAL_NAO_CONSIGNADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 4.90, "taxa_juros_anual_pct": 77.50, "posicao_ranking_bcb": 4},
    # CONSIGNADO_PRIVADO
    {"instituicao": "NUBANK", "segmento": "NEOBANKS", "modalidade": "CONSIGNADO_PRIVADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 2.18, "taxa_juros_anual_pct": 29.52, "posicao_ranking_bcb": 2},
    {"instituicao": "ITAU", "segmento": "INCUMBENTES", "modalidade": "CONSIGNADO_PRIVADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 2.25, "taxa_juros_anual_pct": 30.60, "posicao_ranking_bcb": 3},
    {"instituicao": "BANCO_DO_BRASIL", "segmento": "INCUMBENTES", "modalidade": "CONSIGNADO_PRIVADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 2.10, "taxa_juros_anual_pct": 28.32, "posicao_ranking_bcb": 1},
    {"instituicao": "BRADESCO", "segmento": "INCUMBENTES", "modalidade": "CONSIGNADO_PRIVADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 2.48, "taxa_juros_anual_pct": 34.18, "posicao_ranking_bcb": 5},
    {"instituicao": "INTER", "segmento": "NEOBANKS", "modalidade": "CONSIGNADO_PRIVADO", "ano_mes": "2026-09", "taxa_juros_mensal_pct": 2.34, "taxa_juros_anual_pct": 32.00, "posicao_ranking_bcb": 4},
]

# Pillar 3: Estatísticas Pix & Fraudes MED (Olinda Pix_DadosAbertos v1 + SPI)
FALLBACK_PIX_MED: list[dict[str, Any]] = [
    {"instituicao": "NUBANK", "segmento": "NEOBANKS", "ano_mes": "2026-09", "chaves_pix_ativas_milhoes": 168.4, "transacoes_pix_milhoes": 1420.0, "volume_pix_bi_brl": 412.5, "taxa_disponibilidade_spi_pct": 99.96, "solicitacoes_med_por_100k": 6.4, "taxa_devolucao_med_pct": 28.5},
    {"instituicao": "ITAU", "segmento": "INCUMBENTES", "ano_mes": "2026-09", "chaves_pix_ativas_milhoes": 102.3, "transacoes_pix_milhoes": 980.0, "volume_pix_bi_brl": 540.2, "taxa_disponibilidade_spi_pct": 99.94, "solicitacoes_med_por_100k": 5.9, "taxa_devolucao_med_pct": 26.8},
    {"instituicao": "BANCO_DO_BRASIL", "segmento": "INCUMBENTES", "ano_mes": "2026-09", "chaves_pix_ativas_milhoes": 74.1, "transacoes_pix_milhoes": 690.0, "volume_pix_bi_brl": 388.0, "taxa_disponibilidade_spi_pct": 99.91, "solicitacoes_med_por_100k": 6.8, "taxa_devolucao_med_pct": 24.2},
    {"instituicao": "CAIXA", "segmento": "INCUMBENTES", "ano_mes": "2026-09", "chaves_pix_ativas_milhoes": 96.5, "transacoes_pix_milhoes": 810.0, "volume_pix_bi_brl": 310.4, "taxa_disponibilidade_spi_pct": 99.84, "solicitacoes_med_por_100k": 8.9, "taxa_devolucao_med_pct": 19.6},
    {"instituicao": "BRADESCO", "segmento": "INCUMBENTES", "ano_mes": "2026-09", "chaves_pix_ativas_milhoes": 88.0, "transacoes_pix_milhoes": 760.0, "volume_pix_bi_brl": 415.0, "taxa_disponibilidade_spi_pct": 99.89, "solicitacoes_med_por_100k": 7.5, "taxa_devolucao_med_pct": 22.9},
    {"instituicao": "SANTANDER", "segmento": "INCUMBENTES", "ano_mes": "2026-09", "chaves_pix_ativas_milhoes": 58.2, "transacoes_pix_milhoes": 510.0, "volume_pix_bi_brl": 285.1, "taxa_disponibilidade_spi_pct": 99.88, "solicitacoes_med_por_100k": 7.9, "taxa_devolucao_med_pct": 21.4},
    {"instituicao": "INTER", "segmento": "NEOBANKS", "ano_mes": "2026-09", "chaves_pix_ativas_milhoes": 44.6, "transacoes_pix_milhoes": 395.0, "volume_pix_bi_brl": 148.0, "taxa_disponibilidade_spi_pct": 99.92, "solicitacoes_med_por_100k": 8.2, "taxa_devolucao_med_pct": 23.1},
    {"instituicao": "C6_BANK", "segmento": "NEOBANKS", "ano_mes": "2026-09", "chaves_pix_ativas_milhoes": 38.9, "transacoes_pix_milhoes": 310.0, "volume_pix_bi_brl": 122.4, "taxa_disponibilidade_spi_pct": 99.86, "solicitacoes_med_por_100k": 9.4, "taxa_devolucao_med_pct": 20.5},
    {"instituicao": "MERCADO_PAGO", "segmento": "NEOBANKS", "ano_mes": "2026-09", "chaves_pix_ativas_milhoes": 82.7, "transacoes_pix_milhoes": 740.0, "volume_pix_bi_brl": 218.6, "taxa_disponibilidade_spi_pct": 99.93, "solicitacoes_med_por_100k": 8.6, "taxa_devolucao_med_pct": 24.9},
    {"instituicao": "BTG_PACTUAL", "segmento": "NEOBANKS", "ano_mes": "2026-09", "chaves_pix_ativas_milhoes": 19.4, "transacoes_pix_milhoes": 185.0, "volume_pix_bi_brl": 196.3, "taxa_disponibilidade_spi_pct": 99.95, "solicitacoes_med_por_100k": 4.8, "taxa_devolucao_med_pct": 29.4},
]

# Pillar 4: Saúde Prudencial (IF.data) & Open Finance Fase 1
FALLBACK_PRUDENCIAL_IFDATA: list[dict[str, Any]] = [
    {"instituicao": "NUBANK", "segmento": "NEOBANKS", "trimestre": "2026-Q3", "indice_basileia_pct": 16.4, "carteira_credito_bi_brl": 124.5, "roe_anualizado_pct": 28.4, "taxa_inadimplencia_90d_pct": 6.1, "disponibilidade_open_finance_pct": 99.91},
    {"instituicao": "ITAU", "segmento": "INCUMBENTES", "trimestre": "2026-Q3", "indice_basileia_pct": 16.8, "carteira_credito_bi_brl": 1280.0, "roe_anualizado_pct": 22.6, "taxa_inadimplencia_90d_pct": 2.7, "disponibilidade_open_finance_pct": 99.88},
    {"instituicao": "BANCO_DO_BRASIL", "segmento": "INCUMBENTES", "trimestre": "2026-Q3", "indice_basileia_pct": 14.9, "carteira_credito_bi_brl": 1190.0, "roe_anualizado_pct": 21.1, "taxa_inadimplencia_90d_pct": 3.1, "disponibilidade_open_finance_pct": 99.82},
    {"instituicao": "CAIXA", "segmento": "INCUMBENTES", "trimestre": "2026-Q3", "indice_basileia_pct": 16.1, "carteira_credito_bi_brl": 1175.0, "roe_anualizado_pct": 10.4, "taxa_inadimplencia_90d_pct": 2.4, "disponibilidade_open_finance_pct": 99.71},
    {"instituicao": "BRADESCO", "segmento": "INCUMBENTES", "trimestre": "2026-Q3", "indice_basileia_pct": 15.6, "carteira_credito_bi_brl": 910.0, "roe_anualizado_pct": 12.8, "taxa_inadimplencia_90d_pct": 4.2, "disponibilidade_open_finance_pct": 99.79},
    {"instituicao": "SANTANDER", "segmento": "INCUMBENTES", "trimestre": "2026-Q3", "indice_basileia_pct": 14.4, "carteira_credito_bi_brl": 665.0, "roe_anualizado_pct": 16.2, "taxa_inadimplencia_90d_pct": 3.2, "disponibilidade_open_finance_pct": 99.80},
    {"instituicao": "INTER", "segmento": "NEOBANKS", "trimestre": "2026-Q3", "indice_basileia_pct": 15.8, "carteira_credito_bi_brl": 38.4, "roe_anualizado_pct": 12.5, "taxa_inadimplencia_90d_pct": 4.5, "disponibilidade_open_finance_pct": 99.84},
    {"instituicao": "C6_BANK", "segmento": "NEOBANKS", "trimestre": "2026-Q3", "indice_basileia_pct": 14.2, "carteira_credito_bi_brl": 54.0, "roe_anualizado_pct": 15.8, "taxa_inadimplencia_90d_pct": 4.8, "disponibilidade_open_finance_pct": 99.76},
    {"instituicao": "MERCADO_PAGO", "segmento": "NEOBANKS", "trimestre": "2026-Q3", "indice_basileia_pct": 15.1, "carteira_credito_bi_brl": 31.2, "roe_anualizado_pct": 22.0, "taxa_inadimplencia_90d_pct": 5.9, "disponibilidade_open_finance_pct": 99.85},
    {"instituicao": "BTG_PACTUAL", "segmento": "NEOBANKS", "trimestre": "2026-Q3", "indice_basileia_pct": 16.2, "carteira_credito_bi_brl": 212.0, "roe_anualizado_pct": 23.4, "taxa_inadimplencia_90d_pct": 1.9, "disponibilidade_open_finance_pct": 99.90},
]

# Official BCB Open-Data CKAN catalog fallback entries
FALLBACK_CKAN_PACKAGES: list[dict[str, Any]] = [
    {
        "dataset_id": "ranking-instituicoes-por-indice-de-reclamacoes",
        "titulo": "Ranking de Instituições por Índice de Reclamações (Deati / BCB)",
        "tema": "Consumidor e Reclamações",
        "formato": "CSV / JSON",
        "url_oficial": "https://dadosabertos.bcb.gov.br/dataset/ranking-de-instituicoes-por-indice-de-reclamacoes",
    },
    {
        "dataset_id": "taxas-de-juros-de-operacoes-de-credito",
        "titulo": "Taxas de Juros de Operações de Crédito (API Olinda taxaJuros v2)",
        "tema": "Crédito e Taxas de Juros",
        "formato": "OData JSON / CSV",
        "url_oficial": "https://olinda.bcb.gov.br/olinda/servico/taxaJuros/versao/v2/swagger-ui3#/",
    },
    {
        "dataset_id": "estatisticas-do-pix-dados-abertos",
        "titulo": "Estatísticas do Pix — Chaves DICT, Transações e Fraudes MED (API Olinda Pix_DadosAbertos v1)",
        "tema": "Pix / SPI / MED",
        "formato": "OData JSON / CSV",
        "url_oficial": "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/swagger-ui3#/",
    },
    {
        "dataset_id": "ifdata-dados-selecionados-entidades-supervisionadas",
        "titulo": "IF.data — Dados Selecionados de Entidades Supervisionadas (Basileia, Carteira, ROE)",
        "tema": "Saúde Prudencial / IF.data",
        "formato": "API Olinda / CSV",
        "url_oficial": "https://www3.bcb.gov.br/ifdata/",
    },
    {
        "dataset_id": "open-finance-brasil-dados-abertos-fase-1",
        "titulo": "Open Finance Brasil — Diretório de Participantes e APIs de Dados Abertos (Fase 1)",
        "tema": "Open Finance",
        "formato": "OpenAPI JSON",
        "url_oficial": "https://openfinancebrasil.org.br/",
    },
]
