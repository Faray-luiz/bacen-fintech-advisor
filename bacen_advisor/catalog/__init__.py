"""Declarative Google Cloud FSI Solution Catalog loader.

The catalog lives in ``gcp_fsi_solutions.json`` and is validated against
:class:`bacen_advisor.schemas.GcpSolutionBlueprint` on load so adding new Google Cloud
services, architectures or BCB regulatory plays requires zero Python or prompt rewrites.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..schemas import GcpSolutionBlueprint

_CATALOG_PATH = Path(__file__).resolve().parent / "gcp_fsi_solutions.json"


@lru_cache(maxsize=1)
def load_gcp_fsi_catalog() -> tuple[GcpSolutionBlueprint, ...]:
    """Loads and validates all declarative Google Cloud FSI blueprints."""
    raw = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("gcp_fsi_solutions.json must contain a non-empty JSON list.")
    return tuple(GcpSolutionBlueprint.model_validate(item) for item in raw)
