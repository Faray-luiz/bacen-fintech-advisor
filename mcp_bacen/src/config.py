"""Runtime configuration for the Bacen MCP Server (100% in-memory, 12-factor)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings injected as environment variables on Cloud Run."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "mcp-bacen"
    environment: str = "production"
    port: int = 8080
    log_level: str = "INFO"

    # Observability (Cloud Logging + Cloud Trace)
    google_cloud_project: str = ""
    enable_cloud_trace: bool | None = None
    otel_service_name: str = "mcp-bacen"

    # In-memory RAM cache and pagination limits
    cache_ttl_seconds: int = 3600
    http_timeout_seconds: float = 12.0
    default_max_rows: int = 25
    max_allowed_rows: int = 50
    enable_live_http_fetch: bool = True

    # Official Banco Central do Brasil (Olinda OData + CKAN) & Open Finance endpoints
    bcb_ckan_api_url: str = "https://dadosabertos.bcb.gov.br/api/3/action"
    bcb_olinda_taxas_juros_url: str = (
        "https://olinda.bcb.gov.br/olinda/servico/taxaJuros/versao/v2/odata/"
        "TaxasJurosDiariaPorInicioPeriodo?$top=500&$format=json"
    )
    bcb_olinda_pix_chaves_url: str = (
        "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/"
        "ChavesPix?$top=200&$format=json"
    )
    bcb_ranking_reclamacoes_url: str = (
        "https://www.bcb.gov.br/ranking/index.asp?rel=outbound&frame=1"
    )
    bcb_ifdata_open_finance_url: str = (
        "https://www3.bcb.gov.br/ifdata/index.html"
    )
    bcb_dados_abertos_portal_url: str = "https://dadosabertos.bcb.gov.br"


settings = Settings()
