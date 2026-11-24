"""Official MCPServer (mcp 2.x) exposing 7 BCB / Open Finance tools, 2 resources and 2 prompts."""

import json
from typing import Any

from mcp.server.mcpserver import MCPServer

from src.application.bacen_service import bacen_service
from src.core.observability import ObservabilityMiddleware
from src.domain.glossary import get_glossary_content
from src.infrastructure.fallback_seed import FALLBACK_CKAN_PACKAGES

mcp = MCPServer(
    name="mcp-bacen",
    instructions=(
        "Servidor MCP especialista em dados abertos do Banco Central do Brasil (BCB / Olinda) "
        "e Open Finance Brasil: Ranking de Reclamações (Deati), Taxas de Juros de Crédito "
        "(Olinda taxaJuros v2), Estatísticas do Pix / SPI / MED (Olinda Pix_DadosAbertos v1) "
        "e Saúde Prudencial (IF.data / Basileia III / Open Finance Fase 1)."
    ),
    middleware=[ObservabilityMiddleware()],
)


@mcp.tool(
    name="consultar_ranking_reclamacoes_bcb",
    description=(
        "Consulta o Ranking de Reclamações do Banco Central (Deati) por instituição financeira "
        "(Nubank, Itaú, Bradesco, Banco do Brasil, Santander, Caixa, Inter, C6 Bank, Mercado Pago, BTG Pactual) "
        "ou segmento (TODOS, NEOBANKS, INCUMBENTES): retorna índice de reclamações procedentes por milhão "
        "de clientes (menor é melhor), volume de reclamações, total de clientes CCS e principal motivo."
    ),
)
async def consultar_ranking_reclamacoes_bcb(
    instituicao: str | None = None,
    segmento: str | None = None,
    motivo: str | None = None,
    trimestre: str | None = None,
    limite: int = 25,
) -> dict[str, Any]:
    """Queries the BCB Deati Substantiated Complaints Ranking by institution or segment."""
    return await bacen_service.consultar_ranking_reclamacoes_bcb(
        instituicao=instituicao,
        segmento=segmento,
        motivo=motivo,
        trimestre=trimestre,
        limite=limite,
    )


@mcp.tool(
    name="consultar_taxas_juros_credito",
    description=(
        "Consulta as taxas médias mensais e anuais de juros de operações de crédito publicadas "
        "pela API Olinda do Banco Central (taxaJuros v2) por instituição, segmento e modalidade "
        "(CARTAO_ROTATIVO, CREDITO_PESSOAL_NAO_CONSIGNADO, CONSIGNADO_PRIVADO, CHEQUE_ESPECIAL, PARCELADO_CARTAO)."
    ),
)
async def consultar_taxas_juros_credito(
    instituicao: str | None = None,
    segmento: str | None = None,
    modalidade: str | None = None,
    ano_mes: str | None = None,
    limite: int = 25,
) -> dict[str, Any]:
    """Queries BCB Olinda average credit interest rates by institution and credit modality."""
    return await bacen_service.consultar_taxas_juros_credito(
        instituicao=instituicao,
        segmento=segmento,
        modalidade=modalidade,
        ano_mes=ano_mes,
        limite=limite,
    )


@mcp.tool(
    name="consultar_estatisticas_pix_med",
    description=(
        "Consulta estatísticas públicas do ecossistema Pix (API Olinda Pix_DadosAbertos v1 e SPI): "
        "chaves DICT ativas (milhões), transações mensais, volume financeiro (R$ bi), disponibilidade "
        "operacional SPI (meta BCB >= 99,8%), solicitações MED por 100 mil transações e taxa de devolução MED (%)."
    ),
)
async def consultar_estatisticas_pix_med(
    instituicao: str | None = None,
    segmento: str | None = None,
    ano_mes: str | None = None,
    limite: int = 25,
) -> dict[str, Any]:
    """Queries Pix volume, DICT keys, SPI availability and MED fraud metrics per institution."""
    return await bacen_service.consultar_estatisticas_pix_med(
        instituicao=instituicao,
        segmento=segmento,
        ano_mes=ano_mes,
        limite=limite,
    )


@mcp.tool(
    name="consultar_saude_prudencial_ifdata",
    description=(
        "Consulta indicadores prudenciais trimestrais do IF.data do Banco Central e disponibilidade "
        "das APIs públicas do Open Finance Brasil (Fase 1): Índice de Basileia (%), carteira de crédito "
        "(R$ bi), ROE anualizado (%), inadimplência > 90 dias (%) e disponibilidade Open Finance (%)."
    ),
)
async def consultar_saude_prudencial_ifdata(
    instituicao: str | None = None,
    segmento: str | None = None,
    trimestre: str | None = None,
    limite: int = 25,
) -> dict[str, Any]:
    """Queries quarterly IF.data prudential health (Basel III, ROE, credit book) and Open Finance uptime."""
    return await bacen_service.consultar_saude_prudencial_ifdata(
        instituicao=instituicao,
        segmento=segmento,
        trimestre=trimestre,
        limite=limite,
    )


@mcp.tool(
    name="comparar_instituicoes_financeiras",
    description=(
        "Compara instituições financeiras (ex.: Nubank vs. Itaú, Bradesco, Inter, C6 Bank, Mercado Pago) "
        "cruzando automaticamente os 4 pilares públicos do BCB e Open Finance (Reclamações Deati + "
        "Taxas de Juros + Pix/SPI/MED + IF.data/Open Finance) com normalização 0-10 e ranking consolidado."
    ),
)
async def comparar_instituicoes_financeiras(
    segmento: str = "TODOS",
    modalidade_credito: str = "CARTAO_ROTATIVO",
    instituicoes: list[str] | None = None,
) -> dict[str, Any]:
    """Compares Brazilian banks and fintechs across all 4 BCB / Open Finance pillars."""
    return await bacen_service.comparar_instituicoes_financeiras(
        segmento=segmento,
        modalidade_credito=modalidade_credito,
        instituicoes=instituicoes,
    )


@mcp.tool(
    name="buscar_datasets_dados_abertos_bcb",
    description=(
        "Busca conjuntos de dados abertos, metadados e URLs oficiais (OData Olinda / CSV / JSON) "
        "diretamente no catálogo CKAN do Portal de Dados Abertos do Banco Central do Brasil."
    ),
)
async def buscar_datasets_dados_abertos_bcb(
    termo_busca: str = "pix taxas juros reclamacoes",
    limite: int = 10,
) -> dict[str, Any]:
    """Searches official BCB open-data datasets and Olinda API endpoints."""
    return await bacen_service.buscar_datasets_dados_abertos_bcb(
        termo_busca=termo_busca,
        limite=limite,
    )


@mcp.tool(
    name="consultar_glossario_metodologia_bcb",
    description=(
        "Consulta o glossário regulatório e metodologia oficial do Banco Central e Open Finance Brasil: "
        "Índice de Reclamações Deati, TaxasJuros Olinda, Pix/SPI/MED (Res. BCB 1/2020), IF.data/Basileia III "
        "e segmentação de neobanks vs. bancos S1. Tópicos aceitos: 'geral', 'ranking_reclamacoes', "
        "'taxas_juros', 'pix_med', 'ifdata_open_finance', 'instituicoes_segmentos'."
    ),
)
async def consultar_glossario_metodologia_bcb(
    topico: str | None = "geral",
) -> dict[str, Any]:
    """Returns official BCB and Open Finance regulatory definitions and thresholds."""
    return await bacen_service.consultar_glossario_metodologia_bcb(topico=topico)


# ----------------------------------------------------------------------------
# MCP resources & prompts (for desktop MCP clients & Gemini Enterprise)
# ----------------------------------------------------------------------------


@mcp.resource(
    "bacen://glossario/regulatorio",
    name="Glossário Regulatório BCB & Open Finance Brasil",
    description="Definições oficiais de Deati, TaxasJuros, Pix/MED, Basileia III e Open Finance.",
    mime_type="application/json",
)
def resource_glossario_bcb() -> str:
    return json.dumps(get_glossary_content("geral"), ensure_ascii=False, indent=2)


@mcp.resource(
    "bacen://catalogo/datasets",
    name="Catálogo de Dados Abertos do Banco Central do Brasil",
    description="Lista de endpoints OData Olinda e datasets públicos oficiais do BCB.",
    mime_type="application/json",
)
def resource_catalogo_bcb() -> str:
    return json.dumps(FALLBACK_CKAN_PACKAGES, ensure_ascii=False, indent=2)


@mcp.prompt(
    name="benchmark_neobanks_vs_incumbentes",
    description="Gera diagnóstico competitivo comparando Nubank e bancos digitais contra grandes bancos S1 nos 4 pilares do BCB.",
)
def prompt_benchmark_fintech(
    instituicao_foco: str = "NUBANK", modalidade_credito: str = "CARTAO_ROTATIVO"
) -> str:
    return (
        f"Elabore um diagnóstico executivo comparando '{instituicao_foco}' com seus principais "
        f"concorrentes neobanks e bancos S1 usando as tools do MCP Bacen:\n"
        f"1. Chame `comparar_instituicoes_financeiras` (modalidade_credito='{modalidade_credito}').\n"
        "2. Detalhe os principais motivos de reclamação com `consultar_ranking_reclamacoes_bcb`.\n"
        "3. Avalie escala Pix, disponibilidade SPI e fraude MED com `consultar_estatisticas_pix_med`.\n"
        "4. Verifique solidez prudencial (Basileia, ROE, Open Finance) com `consultar_saude_prudencial_ifdata`.\n"
        "Apresente tabela comparativa, pontos fortes, gaps competitivos e fontes BCB."
    )


@mcp.prompt(
    name="diagnostico_pix_med",
    description="Analisa performance operacional Pix, disponibilidade SPI e eficiência MED por instituição.",
)
def prompt_diagnostico_pix_med(segmento: str = "NEOBANKS") -> str:
    return (
        f"Analise o segmento '{segmento}' utilizando `consultar_estatisticas_pix_med` e "
        "`consultar_ranking_reclamacoes_bcb` com foco em Pix/MED, destacando conformidade "
        "com o piso regulatório SPI (>= 99,8%) e taxas de recuperação MED."
    )
