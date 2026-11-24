"""Agent graph: coordinator + specialists + sequential benchmark pipeline.

Topology (Coordinator / Dispatcher + Sequential Pipeline + LLM-as-Judge Critic)::

    bacen_coordinator (Flash)             routes by intent, owns HITL GCS export
    ├── knowledge_agent (Flash)           BCB/Open Finance glossary + CKAN + Agent Search
    ├── quick_data_agent (Flash)          single-pillar factual lookups via MCP
    └── report_pipeline (SequentialAgent)
        ├── data_collector (Flash)        multi-pillar MCP retrieval   -> state.collected_data
        ├── fintech_analyst (Pro)         reasoning + custom ranking   -> state.analysis_draft
        ├── quality_critic (Flash)        structured CriticVerdict     -> state.critic_verdict
        └── report_publisher (Flash)      applies fixes, final answer  -> state.final_report

Each specialist receives only the tools required for its role (least privilege) and
disables transfer back to parent/peers so agent routing loops are structurally impossible.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import VertexAiSearchTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from .config import build_model, get_settings
from .prompts import (
    ANALYST_INSTRUCTION,
    COLLECTOR_INSTRUCTION,
    CONSTITUTION,
    CRITIC_INSTRUCTION,
    KNOWLEDGE_INSTRUCTION,
    PUBLISHER_INSTRUCTION,
    QUICK_DATA_INSTRUCTION,
)
from .schemas import CriticVerdict
from .tools.mcp_bacen import (
    BACEN_DATA_TOOLS,
    BACEN_REFERENCE_TOOLS,
    build_bacen_toolset,
)
from .tools.report_tools import (
    calculate_weighted_institution_ranking_tool,
    list_supported_bacen_filters_tool,
)

_DETERMINISTIC = types.GenerateContentConfig(temperature=0.1)
_ANALYTICAL = types.GenerateContentConfig(temperature=0.3)

# Only the coordinator may route. Specialists answer and return control cleanly.
_NO_TRANSFER = {"disallow_transfer_to_parent": True, "disallow_transfer_to_peers": True}


def build_knowledge_agent() -> LlmAgent:
    """Explains BCB / Open Finance regulations via MCP glossary, CKAN catalog and Agent Search."""
    settings = get_settings()
    tools: list = [build_bacen_toolset(BACEN_REFERENCE_TOOLS)]
    if settings.vertex_search_datastore:
        tools.append(
            VertexAiSearchTool(
                data_store_id=settings.vertex_search_datastore,
                max_results=5,
                bypass_multi_tools_limit=True,
            )
        )
    return LlmAgent(
        **_NO_TRANSFER,
        name="knowledge_agent",
        description=(
            "Explains Banco Central (BCB) & Open Finance concepts, acronyms "
            "(Deati complaints index, TaxasJuros, Pix/MED/SPI, IF.data, Basel III) "
            "and locates official open-data datasets."
        ),
        model=build_model(settings.models.router),
        static_instruction=CONSTITUTION,
        instruction=KNOWLEDGE_INSTRUCTION,
        tools=tools,
        generate_content_config=_DETERMINISTIC,
    )


def build_quick_data_agent() -> LlmAgent:
    """Answers single-pillar factual lookups rapidly with Gemini Flash."""
    settings = get_settings()
    return LlmAgent(
        **_NO_TRANSFER,
        name="quick_data_agent",
        description=(
            "Fast single-pillar BCB lookup for one institution or credit modality "
            "(complaints index, credit rate, Pix/MED metrics or IF.data Basel/ROE)."
        ),
        model=build_model(settings.models.collector),
        static_instruction=CONSTITUTION,
        instruction=QUICK_DATA_INSTRUCTION,
        tools=[PreloadMemoryTool(), build_bacen_toolset(BACEN_DATA_TOOLS), list_supported_bacen_filters_tool],
        generate_content_config=_DETERMINISTIC,
    )


def build_report_pipeline() -> SequentialAgent:
    """Collect -> analyze (Pro) -> self-evaluate (CriticVerdict) -> publish."""
    settings = get_settings()

    collector = LlmAgent(
        **_NO_TRANSFER,
        name="data_collector",
        description="Retrieves every BCB and Open Finance dataset required for a benchmark report.",
        model=build_model(settings.models.collector),
        static_instruction=CONSTITUTION,
        instruction=COLLECTOR_INSTRUCTION,
        tools=[PreloadMemoryTool(), build_bacen_toolset(BACEN_DATA_TOOLS), list_supported_bacen_filters_tool],
        output_key="collected_data",
        generate_content_config=_DETERMINISTIC,
    )
    analyst = LlmAgent(
        **_NO_TRANSFER,
        name="fintech_analyst",
        description="Senior banking/fintech analyst turning BCB data into grounded competitive insights.",
        model=build_model(settings.models.analyst),
        static_instruction=CONSTITUTION,
        instruction=ANALYST_INSTRUCTION,
        tools=[calculate_weighted_institution_ranking_tool],
        output_key="analysis_draft",
        generate_content_config=_ANALYTICAL,
        include_contents="default",
    )
    critic = LlmAgent(
        **_NO_TRANSFER,
        name="quality_critic",
        description="Independent LLM-as-judge checking every number and metric directionality against tool outputs.",
        model=build_model(settings.models.critic),
        static_instruction=CONSTITUTION,
        instruction=CRITIC_INSTRUCTION,
        output_schema=CriticVerdict,
        output_key="critic_verdict",
        include_contents="default",
        generate_content_config=_DETERMINISTIC,
    )
    publisher = LlmAgent(
        **_NO_TRANSFER,
        name="report_publisher",
        description="Applies critic fixes and presents the final grounded executive report.",
        model=build_model(settings.models.critic),
        static_instruction=CONSTITUTION,
        instruction=PUBLISHER_INSTRUCTION,
        output_key="final_report",
        include_contents="none",
        generate_content_config=_DETERMINISTIC,
    )
    return SequentialAgent(
        name="report_pipeline",
        description="Multi-pillar fintech/bank comparisons, weighted rankings and executive reports with fact-checking.",
        sub_agents=[collector, analyst, critic, publisher],
    )
