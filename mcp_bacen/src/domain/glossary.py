"""Official Banco Central do Brasil (BCB) & Open Finance regulatory glossary."""

from __future__ import annotations

from typing import Any

GLOSSARY_SECTIONS: dict[str, dict[str, Any]] = {
    "ranking_reclamacoes": {
        "titulo": "Ranking de Reclamações do Banco Central (Deati)",
        "normativo": "Circular BCB / Metodologia Deati (Departamento de Atendimento Institucional)",
        "definicao": (
            "Consolida trimestralmente as reclamações reguladas consideradas procedentes "
            "contra instituições financeiras e de pagamento autorizadas pelo BCB."
        ),
        "formula": "Índice = (Reclamações Reguladas Procedentes / Total de Clientes no CCS) × 1.000.000",
        "interpretacao": "Quanto MENOR o índice, melhor o desempenho de atendimento e conformidade da instituição.",
        "exemplos_motivos": [
            "Irregularidades relativas a integridade, confiabilidade, segurança ou sigilo",
            "Oferta ou prestação de informação sobre crédito de forma inadequada",
            "Irregularidades relacionadas a Pix e Mecanismo Especial de Devolução (MED)",
            "Cobrança irregular de tarifa ou encargo em cartão de crédito",
        ],
    },
    "taxas_juros": {
        "titulo": "Taxas de Juros de Operações de Crédito (API Olinda taxaJuros v2)",
        "normativo": "Circular BCB nº 3.957 / Resolução CMN nº 5.112 (teto do rotativo de 100%)",
        "definicao": (
            "Taxas médias mensais e anualizadas efetivamente cobradas pelas instituições "
            "financeiras por modalidade de crédito (recursos livres e direcionados), "
            "publicadas via API OData em olinda.bcb.gov.br."
        ),
        "modalidades_principais": {
            "CARTAO_ROTATIVO": "Cartão de crédito - rotativo total (sujeito ao teto legal de 100% sobre o principal desde 2024)",
            "CREDITO_PESSOAL_NAO_CONSIGNADO": "Empréstimo pessoal sem garantia em folha",
            "CONSIGNADO_PRIVADO": "Crédito pessoal consignado para trabalhadores do setor privado",
            "CHEQUE_ESPECIAL": "Cheque especial PF (limitado a 8% a.m. pela Resolução CMN 4.765)",
            "PARCELADO_CARTAO": "Parcelamento de fatura / compras no cartão de crédito",
        },
        "interpretacao": "Para competitividade ao consumidor, taxas MENORES geram pontuação mais alta no benchmark.",
    },
    "pix_med": {
        "titulo": "Pix, SPI, DICT e Mecanismo Especial de Devolução (MED)",
        "normativo": "Resolução BCB nº 1/2020 (Regulamento do Pix) e atualizações do MED",
        "definicao": (
            "O Pix é o arranjo de pagamentos instantâneos gerido pelo BCB, liquidado no SPI "
            "(Sistema de Pagamentos Instantâneos) com diretório de chaves no DICT. "
            "O MED permite bloqueio cautelar e devolução de recursos em caso de fundada suspeita "
            "de fraude ou falha operacional."
        ),
        "metas_regulatorias": {
            "disponibilidade_spi_pct": ">= 99,8% de disponibilidade operacional exigida dos participantes diretos",
            "prazo_analise_med": "Até 7 dias corridos para análise da notificação de infração e devolução",
        },
        "interpretacao": (
            "Maior disponibilidade SPI e maior taxa de devolução MED são positivos; "
            "menor volume de solicitações MED por 100 mil transações indica melhor prevenção à fraude."
        ),
    },
    "ifdata_open_finance": {
        "titulo": "IF.data (Saúde Prudencial / Basileia III) & Open Finance Brasil",
        "normativo": "Resoluções CMN 4.193 (Basileia III), 4.553 (Segmentação S1–S5) e Resolução Conjunta nº 1/2020 (Open Finance)",
        "definicao": (
            "O IF.data divulga demonstrações financeiras e indicadores prudenciais trimestrais "
            "dos conglomerados financeiros (Índice de Basileia, Carteira de Crédito, ROE, Inadimplência > 90d). "
            "O Open Finance Brasil padroniza APIs abertas de dados institucionais (Fase 1) e compartilhamento "
            "consentido de dados e iniciação de pagamentos."
        ),
        "limites_regulatorios": {
            "indice_basileia_minimo_pct": "10,5% a 11,5% (inclui adicional de capital principal e sistêmico para S1)",
            "disponibilidade_open_finance_pct": ">= 99,5% de disponibilidade trimestral das APIs públicas Fase 1",
        },
    },
    "instituicoes_segmentos": {
        "titulo": "Segmentação de Instituições Financeiras e Bancos Digitais",
        "normativo": "Resolução CMN nº 4.553/2017 (Segmentos Prudenciais S1 a S5)",
        "segmentos_benchmark": {
            "NEOBANKS": "Bancos digitais e plataformas nativas em nuvem: Nubank (Nu Pagamentos/Nu Financeira), Inter, C6 Bank, Mercado Pago, BTG Pactual.",
            "INCUMBENTES": "Grandes bancos tradicionais (S1): Itaú Unibanco, Bradesco, Banco do Brasil, Santander Brasil, Caixa Econômica Federal.",
            "TODOS": "Visão consolidada do mercado comparando neobanks e incumbentes lado a lado.",
        },
        "pesos_score_padrao": {
            "reclamacoes_bcb": "30%",
            "taxas_juros_credito": "25%",
            "pix_spi_med": "25%",
            "prudencial_open_finance": "20%",
        },
    },
}


def get_glossary_content(topico: str | None = "geral") -> dict[str, Any]:
    """Returns one glossary section or all sections when ``topico`` is ``'geral'``."""
    key = (topico or "geral").strip().lower()
    if key == "geral" or key not in GLOSSARY_SECTIONS:
        return GLOSSARY_SECTIONS
    return {key: GLOSSARY_SECTIONS[key]}
