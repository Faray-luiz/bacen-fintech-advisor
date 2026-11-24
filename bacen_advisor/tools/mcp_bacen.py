"""Connection to the Bacen MCP server (Cloud Run) as an ADK ``McpToolset``.

The MCP server (``mcp-bacen``) is deployed as a private Cloud Run service: every
request carries a Google-signed OIDC ID token whose audience is the service URL, and
the caller must hold ``roles/run.invoker`` (provisioned by Terraform in ``terraform/``).

The service URL is never hardcoded: it is fetched from Secret Manager
(``bacen-mcp-url``) through :func:`bacen_advisor.secrets.get_secret`.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from urllib.parse import urlparse

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from ..config import get_settings, is_managed_runtime
from ..secrets import SecretNotFoundError, get_secret

logger = logging.getLogger(__name__)

#: Every tool exposed by the Bacen MCP server, grouped by least-privilege role.
BACEN_DATA_TOOLS: list[str] = [
    "consultar_ranking_reclamacoes_bcb",   # BCB Deati complaints index & drivers
    "consultar_taxas_juros_credito",       # BCB Olinda TaxasJuros v2 credit rates
    "consultar_estatisticas_pix_med",      # BCB Olinda Pix_DadosAbertos v1, SPI & MED
    "consultar_saude_prudencial_ifdata",   # BCB IF.data Basel/ROE + Open Finance uptime
    "comparar_instituicoes_financeiras",   # 4-pillar consolidated competitive benchmark
]
BACEN_REFERENCE_TOOLS: list[str] = [
    "consultar_glossario_metodologia_bcb", # BCB & Open Finance regulatory glossary
    "buscar_datasets_dados_abertos_bcb",   # BCB Open-Data CKAN catalog search
]
ALL_BACEN_TOOLS: list[str] = BACEN_DATA_TOOLS + BACEN_REFERENCE_TOOLS
_OFFLINE_PLACEHOLDER_URL = "https://mcp-bacen.placeholder.invalid/mcp"

_TOKEN_TTL_SECONDS = 45 * 60  # Google ID tokens live 60 min; refresh proactively.


class _IdTokenProvider:
    """Thread-safe cached provider of OIDC ID tokens for a private Cloud Run audience."""

    def __init__(self, audience: str):
        self._audience = audience
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def _fetch(self) -> str:
        # 1) Explicit override - developer machines / CI only, ignored in production.
        if os.getenv("MCP_ID_TOKEN") and not is_managed_runtime():
            return os.environ["MCP_ID_TOKEN"]
        # 2) Workload identity: Agent Runtime / Cloud Run / GCE metadata server.
        try:
            import google.auth.transport.requests
            import google.oauth2.id_token

            request = google.auth.transport.requests.Request()
            return google.oauth2.id_token.fetch_id_token(request, self._audience)
        except Exception as exc:  # noqa: BLE001
            logger.info("id_token_metadata_unavailable", extra={"error": str(exc)})
        # 2b) IAM Credentials generateIdToken for the ADC service account itself (Cloud Build).
        try:
            return self._fetch_via_iam_credentials()
        except Exception as exc:  # noqa: BLE001
            if is_managed_runtime():
                raise RuntimeError(
                    "Workload identity could not mint an ID token for the Bacen MCP "
                    f"server ({exc}). Check the Agent Runtime service account."
                ) from exc
            logger.info("id_token_workload_identity_unavailable", extra={"error": str(exc)})
        # 3) Local developer fallback: end-user gcloud credentials (never in production).
        gcloud = shutil.which("gcloud")
        if gcloud:
            out = subprocess.run(
                [gcloud, "auth", "print-identity-token"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return out.stdout.strip()
        raise RuntimeError(
            "Could not obtain an ID token for the Bacen MCP server. Run "
            "'gcloud auth login' locally or deploy with a service account that has "
            "roles/run.invoker on the mcp-bacen Cloud Run service."
        )

    def _fetch_via_iam_credentials(self) -> str:
        import google.auth
        import google.auth.transport.requests
        from google.auth import impersonated_credentials

        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        request = google.auth.transport.requests.Request()
        source, _ = google.auth.default(scopes=scopes)
        source.refresh(request)
        email = getattr(source, "service_account_email", None)
        if not email or "@" not in email or email == "default":
            raise RuntimeError("ADC is not a service account; cannot use generateIdToken")
        target = impersonated_credentials.Credentials(
            source_credentials=source, target_principal=email, target_scopes=scopes
        )
        id_creds = impersonated_credentials.IDTokenCredentials(
            target, target_audience=self._audience, include_email=True
        )
        id_creds.refresh(request)
        return id_creds.token

    def get(self) -> str:
        with self._lock:
            if not self._token or time.time() >= self._expires_at:
                self._token = self._fetch()
                self._expires_at = time.time() + _TOKEN_TTL_SECONDS
            return self._token


def _resolve_mcp_url() -> str:
    """Resolves the Bacen MCP endpoint from Secret Manager, with offline placeholder for tests."""
    try:
        url = get_secret(get_settings().mcp_url_secret_id, env_override="BACEN_MCP_URL")
    except SecretNotFoundError:
        if is_managed_runtime():
            raise  # fail fast on Agent Runtime / Cloud Run
        logger.warning("mcp_url_unresolved_offline_placeholder")
        return _OFFLINE_PLACEHOLDER_URL
    return url if url.rstrip("/").endswith("/mcp") else url.rstrip("/") + "/mcp"


def build_bacen_toolset(tool_filter: list[str] | None = None) -> McpToolset:
    """Creates an ``McpToolset`` bound to the private Bacen MCP server.

    Args:
      tool_filter: Optional subset of tool names to expose to the agent. Each agent
        receives only the minimum tools required for its role.

    Returns:
      A configured :class:`McpToolset` that injects a fresh OIDC ID token on every
      request via ``header_provider``.
    """
    url = _resolve_mcp_url()
    parsed = urlparse(url)
    audience = f"{parsed.scheme}://{parsed.netloc}"
    token_provider = _IdTokenProvider(audience)

    def _auth_headers(_ctx: ReadonlyContext) -> dict[str, str]:
        return {"Authorization": f"Bearer {token_provider.get()}"}

    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url,
            timeout=get_settings().mcp_timeout_seconds,
        ),
        tool_filter=tool_filter or ALL_BACEN_TOOLS,
        header_provider=_auth_headers,
        tool_list_cache_ttl_seconds=600,
    )
