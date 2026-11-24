"""Response entities shared by every Bacen MCP tool (wire contract with the ADK agent)."""

from typing import Any

from pydantic import BaseModel, Field


class FonteMetadados(BaseModel):
    """Provenance metadata for the Banco Central / Open Finance source behind a response."""

    pilar: str = Field(description="BCB / Open Finance data pillar queried")
    url_oficial_bcb: str = Field(description="Official dataset or Olinda endpoint URL at bcb.gov.br")
    origem_leitura: str = Field(
        description="Effective data origin: 'cache_ram_http', 'http_direto_bcb', 'fallback_seed_ram' or 'memoria_interna'"
    )
    periodo_referencia: str | None = Field(
        default=None, description="Latest reference period present in the returned dataset"
    )
    filtros_aplicados: dict[str, Any] = Field(default_factory=dict)
    total_registros_encontrados: int = Field(description="Total rows matched before pagination")
    registros_retornados: int = Field(description="Rows returned in this response")


class RespostaPadraoBacen(BaseModel):
    """Standard JSON payload returned by every Bacen MCP tool."""

    resumo_executivo: str = Field(
        description="Concise analytical executive summary with key highlights"
    )
    estatisticas_agregadas: dict[str, Any] = Field(
        description="Consolidated aggregates (averages, leaders, regulatory floors)"
    )
    registros: list[dict[str, Any]] = Field(
        description="Filtered and sorted data rows (bounded to 25-50 rows)"
    )
    tabela_markdown: str = Field(
        description="Ready-to-render Markdown table for end users"
    )
    metadados_fonte: FonteMetadados = Field(
        description="Official BCB source provenance, cache origin and filters applied"
    )
