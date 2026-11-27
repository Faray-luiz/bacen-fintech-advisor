"""Google Material Design 3 Web UI and Executive PDF Exporter for Bacen Fintech Advisor.

Loads repository-root ``.env`` before any ``bacen_advisor`` module is imported so
``Settings`` and MCP toolset URLs pick up local configuration automatically when
launched via ``uvicorn web_ui.server:app`` or ``make ui``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_dotenv_early() -> None:
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        return
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv_early()
