"""Explicit Pydantic schemas that constrain tool inputs/outputs and agent outputs.

These models are the single source of truth for:

* validating arguments the LLM sends to the remote Bacen MCP tools *before* the
  network call (see :class:`bacen_advisor.plugins.tool_guard.ToolGuardPlugin`);
* typing the inputs/outputs of local function tools (ADK derives the JSON schema
  exposed to Gemini from these annotations);
* forcing structured output from the critic agent (``output_schema=CriticVerdict``);
* exporting materialized JSON Schemas (Draft 2020-12) for all 10 tools via
  ``TOOL_JSON_SCHEMAS``.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --------------------------------------------------------------------------------------
# Domain vocabularies (Brazilian Financial System / Banco Central do Brasil)
# --------------------------------------------------------------------------------------

KNOWN_INSTITUTIONS: tuple[str, ...] = (
    "NUBANK",
    "ITAU",
    "BRADESCO",
    "BANCO_DO_BRASIL",
    "SANTANDER",
    "CAIXA",
    "INTER",
    "C6_BANK",
    "MERCADO_PAGO",
    "BTG_PACTUAL",
)

INSTITUTION_ALIASES: dict[str, str] = {
    "NUBANK": "NUBANK",
    "NU": "NUBANK",
    "NU PAGAMENTOS": "NUBANK",
    "NU HOLDINGS": "NUBANK",
    "NU FINANCEIRA": "NUBANK",
    "ITAU": "ITAU",
    "ITAU UNIBANCO": "ITAU",
    "BRADESCO": "BRADESCO",
    "BCO BRADESCO": "BRADESCO",
    "BANCO DO BRASIL": "BANCO_DO_BRASIL",
    "BANCO_DO_BRASIL": "BANCO_DO_BRASIL",
    "BB": "BANCO_DO_BRASIL",
    "SANTANDER": "SANTANDER",
    "BCO SANTANDER": "SANTANDER",
    "CAIXA": "CAIXA",
    "CEF": "CAIXA",
    "CAIXA ECONOMICA FEDERAL": "CAIXA",
    "INTER": "INTER",
    "BANCO INTER": "INTER",
    "C6": "C6_BANK",
    "C6 BANK": "C6_BANK",
    "C6_BANK": "C6_BANK",
    "BANCO C6": "C6_BANK",
    "MERCADO PAGO": "MERCADO_PAGO",
    "MERCADO_PAGO": "MERCADO_PAGO",
    "MP": "MERCADO_PAGO",
    "BTG": "BTG_PACTUAL",
    "BTG PACTUAL": "BTG_PACTUAL",
    "BTG_PACTUAL": "BTG_PACTUAL",
}

SEGMENT_ALIASES: dict[str, str] = {
    "TODOS": "TODOS",
    "ALL": "TODOS",
    "GERAL": "TODOS",
    "MERCADO": "TODOS",
    "NEOBANKS": "NEOBANKS",
    "NEOBANK": "NEOBANKS",
    "DIGITAIS": "NEOBANKS",
    "BANCOS DIGITAIS": "NEOBANKS",
    "FINTECHS": "NEOBANKS",
    "INCUMBENTES": "INCUMBENTES",
    "INCUMBENTE": "INCUMBENTES",
    "TRADICIONAIS": "INCUMBENTES",
    "GRANDES BANCOS": "INCUMBENTES",
    "BANCOS TRADICIONAIS": "INCUMBENTES",
    "S1": "INCUMBENTES",
}

CREDIT_MODALITY_ALIASES: dict[str, str] = {
    "CARTAO_ROTATIVO": "CARTAO_ROTATIVO",
    "ROTATIVO": "CARTAO_ROTATIVO",
    "CARTAO DE CREDITO ROTATIVO": "CARTAO_ROTATIVO",
    "ROTATIVO CARTAO": "CARTAO_ROTATIVO",
    "CREDITO_PESSOAL_NAO_CONSIGNADO": "CREDITO_PESSOAL_NAO_CONSIGNADO",
    "CREDITO PESSOAL": "CREDITO_PESSOAL_NAO_CONSIGNADO",
    "EMPRESTIMO PESSOAL": "CREDITO_PESSOAL_NAO_CONSIGNADO",
    "CONSIGNADO_PRIVADO": "CONSIGNADO_PRIVADO",
    "CONSIGNADO": "CONSIGNADO_PRIVADO",
    "CREDITO CONSIGNADO": "CONSIGNADO_PRIVADO",
    "CHEQUE_ESPECIAL": "CHEQUE_ESPECIAL",
    "CHEQUE ESPECIAL": "CHEQUE_ESPECIAL",
    "PARCELADO_CARTAO": "PARCELADO_CARTAO",
    "CARTAO PARCELADO": "PARCELADO_CARTAO",
    "PARCELADO CARTAO": "PARCELADO_CARTAO",
}

GLOSSARY_TOPICS: tuple[str, ...] = (
    "geral",
    "ranking_reclamacoes",
    "taxas_juros",
    "pix_med",
    "ifdata_open_finance",
    "instituicoes_segmentos",
)

_ANO_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_TRIMESTRE = re.compile(r"^\d{4}-Q[1-4]$")


def _ascii_upper(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", normalized.strip().upper())


def normalize_institution(value: str | None) -> str | None:
    """Maps free-text bank/fintech names (e.g. 'Nu Pagamentos', 'BB') to canonical codes."""
    if value is None:
        return None
    key = _ascii_upper(value)
    if not key:
        return None
    if key in INSTITUTION_ALIASES:
        return INSTITUTION_ALIASES[key]
    for alias, canonical in INSTITUTION_ALIASES.items():
        if alias in key:
            return canonical
    raise ValueError(
        f"Unknown financial institution '{value}'. Supported institutions: "
        f"{', '.join(KNOWN_INSTITUTIONS)}."
    )


def normalize_segment(value: str | None) -> str | None:
    """Maps free-text market segments ('bancos digitais', 'grandes bancos') to canonical codes."""
    if value is None:
        return None
    key = _ascii_upper(value)
    if key not in SEGMENT_ALIASES:
        raise ValueError(
            f"Invalid segment '{value}'. Use TODOS, NEOBANKS (bancos digitais) "
            "or INCUMBENTES (grandes bancos tradicionais)."
        )
    return SEGMENT_ALIASES[key]


def normalize_credit_modality(value: str | None) -> str | None:
    """Maps free-text credit modalities ('rotativo', 'crédito pessoal') to canonical codes."""
    if value is None:
        return None
    key = _ascii_upper(value)
    if key in CREDIT_MODALITY_ALIASES:
        return CREDIT_MODALITY_ALIASES[key]
    raise ValueError(
        f"Unknown credit modality '{value}'. Use one of: "
        f"{', '.join(sorted(set(CREDIT_MODALITY_ALIASES.values())))}."
    )


# --------------------------------------------------------------------------------------
# MCP tool argument schemas (client-side validation before remote MCP round-trip)
# --------------------------------------------------------------------------------------


class _McpArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("instituicao", mode="before", check_fields=False)
    @classmethod
    def _instituicao(cls, v: str | None) -> str | None:
        return normalize_institution(v)

    @field_validator("segmento", mode="before", check_fields=False)
    @classmethod
    def _segmento(cls, v: str | None) -> str | None:
        return normalize_segment(v)

    @field_validator("modalidade", mode="before", check_fields=False)
    @classmethod
    def _modalidade(cls, v: str | None) -> str | None:
        return normalize_credit_modality(v)

    @field_validator("ano_mes", mode="before", check_fields=False)
    @classmethod
    def _ano_mes(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip()
        if not _ANO_MES.match(clean):
            raise ValueError(f"Invalid ano_mes '{v}'. Use YYYY-MM format, e.g. 2026-09.")
        return clean

    @field_validator("trimestre", mode="before", check_fields=False)
    @classmethod
    def _trimestre(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip().upper()
        if not _TRIMESTRE.match(clean):
            raise ValueError(f"Invalid trimestre '{v}'. Use YYYY-Q# format, e.g. 2026-Q3.")
        return clean


class ComplaintsRankingArgs(_McpArgs):
    """Input schema for ``consultar_ranking_reclamacoes_bcb`` (BCB Deati Complaints Ranking)."""

    instituicao: str | None = Field(
        default=None, description="Institution name, e.g. 'Nubank', 'Itau', 'Inter'."
    )
    segmento: str | None = Field(
        default=None, description="Market segment: TODOS, NEOBANKS or INCUMBENTES."
    )
    motivo: str | None = Field(
        default=None, description="Optional substring filter for primary complaint driver (e.g. 'Pix', 'cartão')."
    )
    trimestre: str | None = Field(
        default=None, description="Reference quarter in YYYY-Q# format (e.g. 2026-Q3)."
    )
    limite: int = Field(default=25, ge=1, le=100, description="Max records to return (1-100).")


class CreditRatesArgs(_McpArgs):
    """Input schema for ``consultar_taxas_juros_credito`` (BCB Olinda TaxasJuros v2)."""

    instituicao: str | None = Field(
        default=None, description="Institution name, e.g. 'Nubank', 'Bradesco', 'C6_BANK'."
    )
    segmento: str | None = Field(
        default=None, description="Market segment: TODOS, NEOBANKS or INCUMBENTES."
    )
    modalidade: str | None = Field(
        default=None,
        description=(
            "Credit modality: CARTAO_ROTATIVO, CREDITO_PESSOAL_NAO_CONSIGNADO, "
            "CONSIGNADO_PRIVADO, CHEQUE_ESPECIAL or PARCELADO_CARTAO."
        ),
    )
    ano_mes: str | None = Field(
        default=None, description="Reference month in YYYY-MM format (e.g. 2026-09)."
    )
    limite: int = Field(default=25, ge=1, le=100, description="Max records to return (1-100).")


class PixMedStatsArgs(_McpArgs):
    """Input schema for ``consultar_estatisticas_pix_med`` (BCB Olinda Pix_DadosAbertos v1 & SPI)."""

    instituicao: str | None = Field(
        default=None, description="Institution name, e.g. 'Nubank', 'Mercado_Pago', 'Itau'."
    )
    segmento: str | None = Field(
        default=None, description="Market segment: TODOS, NEOBANKS or INCUMBENTES."
    )
    ano_mes: str | None = Field(
        default=None, description="Reference month in YYYY-MM format (e.g. 2026-09)."
    )
    limite: int = Field(default=25, ge=1, le=100, description="Max records to return (1-100).")


class PrudentialOpenFinanceArgs(_McpArgs):
    """Input schema for ``consultar_saude_prudencial_ifdata`` (BCB IF.data + Open Finance Phase 1)."""

    instituicao: str | None = Field(
        default=None, description="Institution name, e.g. 'Nubank', 'BTG_Pactual', 'Itau'."
    )
    segmento: str | None = Field(
        default=None, description="Market segment: TODOS, NEOBANKS or INCUMBENTES."
    )
    trimestre: str | None = Field(
        default=None, description="Reference quarter in YYYY-Q# format (e.g. 2026-Q3)."
    )
    limite: int = Field(default=25, ge=1, le=100, description="Max records to return (1-100).")


class CompareInstitutionsArgs(_McpArgs):
    """Input schema for ``comparar_instituicoes_financeiras`` (4-pillar BCB benchmark)."""

    segmento: str = Field(
        default="TODOS", description="Market segment to compare: TODOS, NEOBANKS or INCUMBENTES."
    )
    modalidade_credito: str = Field(
        default="CARTAO_ROTATIVO",
        description="Credit modality used for the interest-rate pillar in the comparison.",
    )
    instituicoes: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Optional list of up to 10 institutions to compare side by side.",
    )

    @field_validator("modalidade_credito", mode="before")
    @classmethod
    def _modalidade_credito(cls, v: str | None) -> str:
        return normalize_credit_modality(v) or "CARTAO_ROTATIVO"

    @field_validator("instituicoes", mode="before")
    @classmethod
    def _instituicoes(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return [normalize_institution(item) for item in v if item]  # type: ignore[misc]


class BcbCkanSearchArgs(_McpArgs):
    """Input schema for ``buscar_datasets_dados_abertos_bcb`` (BCB Open-Data CKAN search)."""

    termo_busca: str = Field(
        default="pix taxas juros reclamacoes",
        min_length=2,
        max_length=200,
        description="Search terms for the Banco Central open-data catalog (dadosabertos.bcb.gov.br).",
    )
    limite: int = Field(default=10, ge=1, le=50, description="Max datasets to return (1-50).")


class BcbGlossaryArgs(_McpArgs):
    """Input schema for ``consultar_glossario_metodologia_bcb`` (BCB regulatory glossary)."""

    topico: Literal[GLOSSARY_TOPICS] | None = Field(  # type: ignore[valid-type]
        default="geral", description="Glossary topic identifier."
    )


MCP_ARG_SCHEMAS: dict[str, type[BaseModel]] = {
    "consultar_ranking_reclamacoes_bcb": ComplaintsRankingArgs,
    "consultar_taxas_juros_credito": CreditRatesArgs,
    "consultar_estatisticas_pix_med": PixMedStatsArgs,
    "consultar_saude_prudencial_ifdata": PrudentialOpenFinanceArgs,
    "comparar_instituicoes_financeiras": CompareInstitutionsArgs,
    "buscar_datasets_dados_abertos_bcb": BcbCkanSearchArgs,
    "consultar_glossario_metodologia_bcb": BcbGlossaryArgs,
}


class McpSourceMetadata(BaseModel):
    """Provenance metadata returned inside ``structuredContent.metadados_fonte``."""

    model_config = ConfigDict(extra="allow")

    pilar: str | None = Field(default=None, description="BCB / Open Finance pillar identifier.")
    origem_leitura: str | None = Field(
        default=None, description="Effective data origin (live Olinda/CKAN HTTP, RAM cache or seed fallback)."
    )
    periodo_referencia: str | None = Field(
        default=None, description="Reference period (YYYY-MM or YYYY-Q#)."
    )


class McpStructuredContent(BaseModel):
    """Structured payload inside a Bacen MCP tool response."""

    model_config = ConfigDict(extra="allow")

    registros: list[dict] | None = Field(default=None, description="Returned data rows.")
    metadados_fonte: McpSourceMetadata | None = Field(default=None, description="Source provenance.")


class McpToolOutput(BaseModel):
    """Output schema for responses returned by the remote Bacen MCP server."""

    model_config = ConfigDict(extra="allow")

    isError: bool = Field(default=False, description="True when the MCP server reports a tool error.")
    structuredContent: McpStructuredContent | None = Field(
        default=None, description="Structured tool output payload."
    )
    recovery_hint: str | None = Field(
        default=None, description="Actionable instruction added when recovery is needed."
    )


# --------------------------------------------------------------------------------------
# Local tool schemas
# --------------------------------------------------------------------------------------


class SupportedFiltersResult(BaseModel):
    """Output schema for ``list_supported_bacen_filters``."""

    status: Literal["success"] = "success"
    instituicoes: list[str] = Field(description="Canonical institution identifiers.")
    segmentos: dict[str, str] = Field(description="Free-text alias -> canonical market segment.")
    modalidades_credito: dict[str, str] = Field(
        description="Free-text alias -> canonical BCB credit modality."
    )
    topicos_glossario: list[str] = Field(description="Valid glossary topic identifiers.")
    formato_ano_mes: str = Field(description="Expected YYYY-MM monthly period format.")
    formato_trimestre: str = Field(description="Expected YYYY-Q# quarterly period format.")


class InstitutionMetrics(BaseModel):
    """Per-institution 0-10 normalized pillar scores copied verbatim from Bacen MCP outputs."""

    instituicao: str = Field(description="Canonical institution name, e.g. 'NUBANK' or 'ITAU'.")
    score_reclamacoes_0_10: float | None = Field(
        default=None, ge=0, le=10, description="Complaints pillar score 0-10 (higher = fewer complaints)."
    )
    score_taxas_credito_0_10: float | None = Field(
        default=None, ge=0, le=10, description="Credit pricing competitiveness 0-10 (higher = lower rates)."
    )
    score_pix_med_0_10: float | None = Field(
        default=None, ge=0, le=10, description="Pix scale, SPI uptime and MED efficiency score 0-10."
    )
    score_prudencial_0_10: float | None = Field(
        default=None, ge=0, le=10, description="Basel capital, ROE and Open Finance uptime score 0-10."
    )


class BenchmarkWeights(BaseModel):
    """Relative weights (any non-negative numbers; normalized to sum to 1)."""

    reclamacoes: float = Field(default=0.30, ge=0, description="Weight for BCB Complaints (default 0.30).")
    taxas_credito: float = Field(default=0.25, ge=0, description="Weight for Credit Rates (default 0.25).")
    pix_med: float = Field(default=0.25, ge=0, description="Weight for Pix/SPI/MED (default 0.25).")
    prudencial: float = Field(default=0.20, ge=0, description="Weight for IF.data/Open Finance (default 0.20).")


class RankedInstitution(BaseModel):
    """Single row in the computed weighted competitive ranking."""

    position: int = Field(ge=1, description="1-based rank position.")
    instituicao: str = Field(description="Institution name in uppercase.")
    weighted_score_0_10: float = Field(ge=0, le=10, description="Normalized weighted score (0-10).")
    pillars_used: list[str] = Field(description="Pillars included in this institution's score.")


class RankingResult(BaseModel):
    """Output schema for ``calculate_weighted_institution_ranking``."""

    status: Literal["success", "error"]
    ranking: list[RankedInstitution] = Field(default_factory=list)
    weights_normalized: dict[str, float] = Field(default_factory=dict)
    error_message: str | None = None
    recovery_hint: str | None = None


class ExportReportResult(BaseModel):
    """Output schema for ``export_report_to_gcs``."""

    status: Literal["success", "error", "rejected"]
    gcs_uri: str | None = None
    report_id: str | None = None
    error_message: str | None = None
    recovery_hint: str | None = None


# --------------------------------------------------------------------------------------
# Agent output schemas
# --------------------------------------------------------------------------------------


class CriticIssue(BaseModel):
    """Single grounding or policy issue flagged by ``quality_critic``."""

    claim: str = Field(description="Exact sentence or number from the draft being challenged.")
    problem: Literal[
        "number_not_in_tool_output",
        "missing_source_or_period",
        "wrong_interpretation",
        "unsupported_recommendation",
        "off_topic_or_unsafe",
    ]
    fix: str = Field(description="Concrete correction the publisher must apply.")


class CriticVerdict(BaseModel):
    """Structured self-evaluation produced by the LLM-as-judge critic agent."""

    approved: bool = Field(description="True only if every number and directionality is grounded.")
    groundedness_score: int = Field(ge=1, le=5, description="1 = hallucinated, 5 = fully grounded.")
    issues: list[CriticIssue] = Field(default_factory=list)
    summary: str = Field(description="One-sentence justification of the verdict.")


#: Materialized JSON Schemas (Draft 2020-12) for every MCP and local tool.
TOOL_JSON_SCHEMAS: dict[str, dict[str, dict]] = {
    **{
        name: {
            "input": model.model_json_schema(),
            "output": McpToolOutput.model_json_schema(),
        }
        for name, model in MCP_ARG_SCHEMAS.items()
    },
    "list_supported_bacen_filters": {
        "input": {"type": "object", "properties": {}, "additionalProperties": False},
        "output": SupportedFiltersResult.model_json_schema(),
    },
    "calculate_weighted_institution_ranking": {
        "input": {
            "type": "object",
            "properties": {
                "institutions": {"type": "array", "items": InstitutionMetrics.model_json_schema()},
                "weights": BenchmarkWeights.model_json_schema(),
            },
            "required": ["institutions"],
            "additionalProperties": False,
        },
        "output": RankingResult.model_json_schema(),
    },
    "export_report_to_gcs": {
        "input": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "markdown_report": {"type": "string"},
            },
            "required": ["title", "markdown_report"],
            "additionalProperties": False,
        },
        "output": ExportReportResult.model_json_schema(),
    },
}
