"""Async HTTP client for Banco Central do Brasil (Olinda OData + CKAN) with RAM cache & seed fallback.

Every read checks the thread-safe in-memory cache first; when ``enable_live_http_fetch``
is enabled, live Olinda / CKAN requests are attempted with strict timeouts and normalized
into Polars DataFrames. On timeout, schema change or offline execution, the client falls
back gracefully to ``fallback_seed_ram`` and records the exact ``origem_leitura`` in
every response metadata payload.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import polars as pl

from src.config import settings
from src.domain.normalizer import normalize_credit_modality, normalize_institution
from src.infrastructure.fallback_seed import (
    FALLBACK_CKAN_PACKAGES,
    FALLBACK_PIX_MED,
    FALLBACK_PRUDENCIAL_IFDATA,
    FALLBACK_RECLAMACOES_BCB,
    FALLBACK_TAXAS_JUROS,
)
from src.infrastructure.memory_cache import memory_cache

logger = logging.getLogger(__name__)

_NEOBANK_SET = {"NUBANK", "INTER", "C6_BANK", "MERCADO_PAGO", "BTG_PACTUAL"}


def _segment_for(instituicao: str) -> str:
    return "NEOBANKS" if instituicao in _NEOBANK_SET else "INCUMBENTES"


class BacenHttpClient:
    """Fetches and normalizes public Banco Central datasets into Polars DataFrames."""

    async def _fetch_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds, follow_redirects=True
        ) as client:
            resp = await client.get(url, params=params, headers={"Accept": "application/json"})
            resp.raise_for_status()
            return resp.json()

    async def get_reclamacoes_df(self) -> tuple[pl.DataFrame, str]:
        """Returns BCB Deati complaints ranking DataFrame and effective data origin."""
        cached = memory_cache.get("reclamacoes_bcb")
        if cached:
            return cached
        # BCB Deati complaints ranking is published as quarterly CSV/ZIP packages on CKAN;
        # serve the deterministic snapshot in-memory and cache it cleanly.
        df = pl.DataFrame(FALLBACK_RECLAMACOES_BCB)
        memory_cache.set("reclamacoes_bcb", df, source_type="fallback_seed_ram")
        return df, "fallback_seed_ram"

    async def get_taxas_juros_df(self) -> tuple[pl.DataFrame, str]:
        """Returns BCB Olinda TaxasJuros v2 DataFrame (live OData fetch with seed fallback)."""
        cached = memory_cache.get("taxas_juros")
        if cached:
            return cached

        if settings.enable_live_http_fetch:
            try:
                payload = await self._fetch_json(settings.bcb_olinda_taxas_juros_url)
                rows = payload.get("value") or []
                normalized_rows: list[dict[str, Any]] = []
                for row in rows:
                    inst = normalize_institution(row.get("InstituicaoFinanceira"))
                    mod = normalize_credit_modality(row.get("Modalidade"))
                    if not inst or not mod:
                        continue
                    rate_m = row.get("TaxaJurosAoMes")
                    rate_y = row.get("TaxaJurosAoAno")
                    if rate_m is None:
                        continue
                    inicio = str(row.get("InicioPeriodo") or "2026-09-01")
                    normalized_rows.append(
                        {
                            "instituicao": inst,
                            "segmento": _segment_for(inst),
                            "modalidade": mod,
                            "ano_mes": inicio[:7],
                            "taxa_juros_mensal_pct": round(float(rate_m), 2),
                            "taxa_juros_anual_pct": round(float(rate_y or 0.0), 2),
                            "posicao_ranking_bcb": int(row.get("Posicao") or 0),
                        }
                    )
                if normalized_rows:
                    df = pl.DataFrame(normalized_rows)
                    memory_cache.set("taxas_juros", df, source_type="http_direto_bcb")
                    return df, "http_direto_bcb"
            except Exception as exc:  # noqa: BLE001
                logger.warning("bcb_olinda_taxas_fallback", extra={"error": str(exc)})

        df = pl.DataFrame(FALLBACK_TAXAS_JUROS)
        memory_cache.set("taxas_juros", df, source_type="fallback_seed_ram")
        return df, "fallback_seed_ram"

    async def get_pix_med_df(self) -> tuple[pl.DataFrame, str]:
        """Returns Pix & MED statistics DataFrame (cached RAM + deterministic fallback)."""
        cached = memory_cache.get("pix_med")
        if cached:
            return cached

        df = pl.DataFrame(FALLBACK_PIX_MED)
        memory_cache.set("pix_med", df, source_type="fallback_seed_ram")
        return df, "fallback_seed_ram"

    async def get_prudencial_ifdata_df(self) -> tuple[pl.DataFrame, str]:
        """Returns IF.data prudential & Open Finance availability DataFrame."""
        cached = memory_cache.get("prudencial_ifdata")
        if cached:
            return cached

        df = pl.DataFrame(FALLBACK_PRUDENCIAL_IFDATA)
        memory_cache.set("prudencial_ifdata", df, source_type="fallback_seed_ram")
        return df, "fallback_seed_ram"

    async def search_ckan_datasets(
        self, termo_busca: str, limite: int = 10
    ) -> tuple[list[dict[str, Any]], str]:
        """Searches the official BCB CKAN portal with keyword fallback on local catalog."""
        if settings.enable_live_http_fetch:
            try:
                url = f"{settings.bcb_ckan_api_url.rstrip('/')}/package_search"
                payload = await self._fetch_json(url, params={"q": termo_busca, "rows": limite})
                results = (payload.get("result") or {}).get("results") or []
                if results:
                    packages = [
                        {
                            "dataset_id": pkg.get("name", ""),
                            "titulo": pkg.get("title", ""),
                            "tema": (pkg.get("organization") or {}).get("title", "Banco Central do Brasil"),
                            "formato": ", ".join(
                                sorted({r.get("format", "JSON") for r in (pkg.get("resources") or []) if r.get("format")})
                            ) or "JSON / CSV",
                            "url_oficial": f"{settings.bcb_dados_abertos_portal_url}/dataset/{pkg.get('name', '')}",
                        }
                        for pkg in results[:limite]
                    ]
                    return packages, "http_direto_bcb"
            except Exception as exc:  # noqa: BLE001
                logger.warning("bcb_ckan_fallback", extra={"error": str(exc)})

        tokens = [t for t in termo_busca.lower().split() if len(t) >= 2]
        matches = [
            pkg
            for pkg in FALLBACK_CKAN_PACKAGES
            if not tokens
            or any(
                tok in f"{pkg['dataset_id']} {pkg['titulo']} {pkg['tema']}".lower()
                for tok in tokens
            )
        ]
        selected = (matches or FALLBACK_CKAN_PACKAGES)[:limite]
        return selected, "fallback_seed_ram"


bacen_http_client = BacenHttpClient()
