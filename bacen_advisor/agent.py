"""Root agent and ADK ``App`` for the Bacen Fintech Advisor.

``root_agent`` is discovered by ``adk web`` / ``adk run``; ``app`` bundles the agent
with ordered plugins (observability, guardrails, tool guard, async memory), sliding-window
history compaction and Gemini context caching for deployment to Agent Runtime on
Gemini Enterprise Agent Platform (Vertex AI Agent Engine).
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps import App
from google.adk.apps.app import EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from .config import build_model, get_settings
from .memory import MemoryPlugin
from .observability import configure_logging, configure_tracing
from .plugins import GuardrailsPlugin, ObservabilityPlugin, ToolGuardPlugin
from .prompts import CONSTITUTION, COORDINATOR_INSTRUCTION
from .sub_agents import build_knowledge_agent, build_quick_data_agent, build_report_pipeline
from .tools.report_tools import export_report_to_gcs_tool

configure_logging()
configure_tracing()

settings = get_settings()

root_agent = LlmAgent(
    name="bacen_coordinator",
    description="Entry point: classifies the banking/fintech query and delegates to the right specialist.",
    model=build_model(settings.models.router),
    static_instruction=CONSTITUTION,
    instruction=COORDINATOR_INSTRUCTION,
    tools=[PreloadMemoryTool(), export_report_to_gcs_tool],
    sub_agents=[build_knowledge_agent(), build_quick_data_agent(), build_report_pipeline()],
    generate_content_config=types.GenerateContentConfig(temperature=0.1),
)

app = App(
    name=settings.app_name,
    root_agent=root_agent,
    # Order matters: ADK stops at the first plugin returning a value. ObservabilityPlugin
    # never returns a value, so it MUST run first to observe every call (including blocked ones).
    plugins=[ObservabilityPlugin(), GuardrailsPlugin(), ToolGuardPlugin(), MemoryPlugin()],
    # Context-bloat management: sliding window with overlap summarized asynchronously by Flash.
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=settings.compaction_interval,
        overlap_size=settings.compaction_overlap,
        summarizer=LlmEventSummarizer(llm=build_model(settings.models.summarizer)),
    ),
    # Gemini context caching for the static CONSTITUTION + tool declarations.
    context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
)
