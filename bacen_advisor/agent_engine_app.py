"""Agent Runtime entrypoint on Gemini Enterprise Agent Platform (source-based deployment).

Agent Runtime (Vertex AI Agent Engine) imports ``bacen_advisor.agent_engine_app:agent_engine``
directly from the uploaded source package.

Telemetry is enabled via ``GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true`` (set by
``deployment/deploy.py``) rather than the legacy ``enable_tracing=True`` flag so
prompts, responses and tool arguments are never copied into Cloud Trace span attributes.
"""

from vertexai.agent_engines import AdkApp

from .agent import app
from .runtime import build_memory_service, build_session_service

agent_engine = AdkApp(
    app=app,
    session_service_builder=build_session_service,
    memory_service_builder=build_memory_service,
)
