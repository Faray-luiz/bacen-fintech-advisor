# Production container for Bacen Fintech Advisor Google Material Design 3 Web UI
# Bundles bacen_advisor (ADK multi-agent system + Senior Google Cloud FSI Consultant),
# web_ui (FastAPI SSE backend + M3 frontend + Executive PDF Exporter) and Roboto/DejaVu fonts.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml README.md ./
COPY bacen_advisor ./bacen_advisor
COPY web_ui ./web_ui

RUN uv venv /app/.venv --python 3.12 && \
    uv pip install --python /app/.venv/bin/python --no-cache \
      . \
      "fastapi>=0.115.0" \
      "uvicorn[standard]>=0.32.0" \
      "httpx>=0.28.0" \
      "reportlab>=4.2.0,<5"

# Minimal runtime image with Roboto & DejaVu fonts for UTF-8 Portuguese + Unicode arrow PDFs
FROM python:3.12-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-roboto fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --chown=appuser:appgroup ./bacen_advisor ./bacen_advisor
COPY --chown=appuser:appgroup ./web_ui ./web_ui

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    GOOGLE_GENAI_USE_VERTEXAI=TRUE \
    ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false \
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=NO_CONTENT

USER appuser

# Single worker per container preserves SQLite session locality with Cloud Run --session-affinity.
CMD ["sh", "-c", "exec uvicorn web_ui.server:app --host 0.0.0.0 --port ${PORT} --workers 1"]
