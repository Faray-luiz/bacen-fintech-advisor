"""Secure secret resolution backed by Google Secret Manager.

No credentials or endpoints are hardcoded in this repository. Every sensitive value
is fetched at runtime with the workload identity (ADC) of the process:

* locally: the developer's ``gcloud auth application-default login`` credentials;
* on Agent Runtime (Gemini Enterprise Agent Platform): the runtime service account,
  which holds ``roles/secretmanager.secretAccessor`` via Terraform (``terraform/``).

For local development and offline tests only, a value may be overridden with an
environment variable (e.g. ``BACEN_MCP_URL``). Developer overrides are strictly
ignored when :func:`bacen_advisor.config.is_managed_runtime` is ``True``.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from .config import get_settings, is_managed_runtime

logger = logging.getLogger(__name__)


class SecretNotFoundError(RuntimeError):
    """Raised when a secret cannot be resolved from any configured source."""


@lru_cache(maxsize=32)
def get_secret(secret_id: str, *, env_override: str | None = None, version: str = "latest") -> str:
    """Fetches a secret value from Google Secret Manager.

    Args:
      secret_id: Secret Manager secret id (not the full resource name).
      env_override: Optional environment variable name that, when set locally, takes
        precedence. Ignored on managed runtimes.
      version: Secret version to access. Defaults to ``latest``.

    Returns:
      The decoded secret payload.

    Raises:
      SecretNotFoundError: If the secret cannot be resolved.
    """
    if env_override and os.getenv(env_override) and not is_managed_runtime():
        logger.info("secret_resolved", extra={"secret_id": secret_id, "source": "env"})
        return os.environ[env_override]

    settings = get_settings()
    if not settings.project_id:
        raise SecretNotFoundError(
            f"GOOGLE_CLOUD_PROJECT is not set; cannot read secret '{secret_id}'."
        )

    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{settings.project_id}/secrets/{secret_id}/versions/{version}"
        payload = client.access_secret_version(request={"name": name}).payload.data
        logger.info("secret_resolved", extra={"secret_id": secret_id, "source": "secret_manager"})
        return payload.decode("utf-8").strip()
    except Exception as exc:  # noqa: BLE001 - surface a single actionable error
        raise SecretNotFoundError(
            f"Unable to access secret '{secret_id}' in project '{settings.project_id}': {exc}"
        ) from exc
