"""Unit-test fixtures: keep the suite 100% offline with a non-routable MCP URL."""

import os

os.environ.setdefault("BACEN_MCP_URL", "https://mcp-bacen.example.run.app")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")
os.environ.setdefault("PII_REDACTION_MODE", "regex")
os.environ.setdefault("LOG_LEVEL", "WARNING")
