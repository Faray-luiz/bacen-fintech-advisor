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

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import VertexAiSearchTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from .config import build_model, get_settings
from .prompts import (
    ANALYST_INSTRUCTION,
    BOARDROOM_ROLEPLAY_INSTRUCTION,
    COLLECTOR_INSTRUCTION,
    CONSTITUTION,
    CRITIC_INSTRUCTION,
    GCP_CONSULTANT_INSTRUCTION,
    GCP_CRITIC_INSTRUCTION,
    GCP_DATA_PREP_INSTRUCTION,
    GCP_PUBLISHER_INSTRUCTION,
    KNOWLEDGE_INSTRUCTION,
    PUBLISHER_INSTRUCTION,
    QUICK_DATA_INSTRUCTION,
    WARROOM_CFO_INSTRUCTION,
    WARROOM_COACH_INSTRUCTION,
    WARROOM_CRITIC_INSTRUCTION,
    WARROOM_CRO_INSTRUCTION,
    WARROOM_CTO_INSTRUCTION,
    WARROOM_DATA_PREP_INSTRUCTION,
    WARROOM_PUBLISHER_INSTRUCTION,
)
from .schemas import CriticVerdict
from .tools.gcp_advisory_tools import (
    diagnose_institution_gaps_tool,
    match_gcp_solutions_catalog_tool,
)
from .tools.mcp_bacen import (
    BACEN_DATA_TOOLS,
    BACEN_REFERENCE_TOOLS,
    build_bacen_toolset,
)
from .tools.report_tools import (
    calculate_weighted_institution_ranking_tool,
    list_supported_bacen_filters_tool,
)
from .tools.simulation_tools import simulate_bcb_what_if_scenario_tool

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
        tools=[calculate_weighted_institution_ranking_tool, simulate_bcb_what_if_scenario_tool],
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


def build_gcp_advisory_pipeline() -> SequentialAgent:
    """Data prep (reuse or 1x MCP) -> Google Cloud Senior FSI Consultant (Pro) -> Critic -> Publisher."""
    settings = get_settings()

    data_prep = LlmAgent(
        **_NO_TRANSFER,
        name="gcp_data_prep",
        description="Reuses session BCB benchmark data or fetches 4-pillar metrics for the target bank and peers.",
        model=build_model(settings.models.collector),
        static_instruction=CONSTITUTION,
        instruction=GCP_DATA_PREP_INSTRUCTION,
        tools=[PreloadMemoryTool(), build_bacen_toolset(BACEN_DATA_TOOLS), list_supported_bacen_filters_tool],
        output_key="collected_data",
        generate_content_config=_DETERMINISTIC,
    )

    consultant_tools: list = [
        diagnose_institution_gaps_tool,
        match_gcp_solutions_catalog_tool,
        simulate_bcb_what_if_scenario_tool,
    ]
    if settings.vertex_search_datastore:
        consultant_tools.append(
            VertexAiSearchTool(
                data_store_id=settings.vertex_search_datastore,
                max_results=5,
                bypass_multi_tools_limit=True,
            )
        )

    consultant = LlmAgent(
        **_NO_TRANSFER,
        name="gcp_cloud_consultant",
        description=(
            "Senior Google Cloud FSI Architect & Consultant generating grounded cloud "
            "initiatives, reference architectures, differentiators and discovery plays "
            "to address a bank's BCB and Open Finance gaps."
        ),
        model=build_model(settings.models.consultant),
        static_instruction=CONSTITUTION,
        instruction=GCP_CONSULTANT_INSTRUCTION,
        tools=consultant_tools,
        output_key="gcp_opportunities_draft",
        generate_content_config=_ANALYTICAL,
        include_contents="default",
    )

    critic = LlmAgent(
        **_NO_TRANSFER,
        name="gcp_advisory_critic",
        description="Independent LLM-as-judge auditing BCB numbers and Google Cloud catalog grounding.",
        model=build_model(settings.models.critic),
        static_instruction=CONSTITUTION,
        instruction=GCP_CRITIC_INSTRUCTION,
        output_schema=CriticVerdict,
        output_key="critic_verdict",
        include_contents="default",
        generate_content_config=_DETERMINISTIC,
    )

    publisher = LlmAgent(
        **_NO_TRANSFER,
        name="gcp_advisory_publisher",
        description="Applies critic fixes and publishes the final Google Cloud FSI Advisory Brief.",
        model=build_model(settings.models.critic),
        static_instruction=CONSTITUTION,
        instruction=GCP_PUBLISHER_INSTRUCTION,
        output_key="final_report",
        include_contents="none",
        generate_content_config=_DETERMINISTIC,
    )

    return SequentialAgent(
        name="gcp_advisory_pipeline",
        description=(
            "Senior Google Cloud FSI advisory pipeline: diagnoses a bank's BCB/Open Finance "
            "gaps and proposes grounded Google Cloud initiatives, architectures and differentiators."
        ),
        sub_agents=[data_prep, consultant, critic, publisher],
    )


def build_boardroom_warroom_pipeline() -> SequentialAgent:
    """Data prep -> Parallel C-Level Panel (CTO + CRO + CFO) -> Pitch Coach (Pro) -> Critic -> Publisher."""
    settings = get_settings()

    data_prep = LlmAgent(
        **_NO_TRANSFER,
        name="warroom_data_prep",
        description="Ensures verbatim 4-pillar BCB benchmark records exist for the Boardroom War Room.",
        model=build_model(settings.models.collector),
        static_instruction=CONSTITUTION,
        instruction=WARROOM_DATA_PREP_INSTRUCTION,
        tools=[PreloadMemoryTool(), build_bacen_toolset(BACEN_DATA_TOOLS), list_supported_bacen_filters_tool],
        output_key="collected_data",
        generate_content_config=_DETERMINISTIC,
    )

    persona_cto = LlmAgent(
        **_NO_TRANSFER,
        name="persona_cto",
        description="Skeptical bank CTO challenging latency, SPI availability, legacy risk and multicloud lock-in.",
        model=build_model(settings.models.collector),
        static_instruction=CONSTITUTION,
        instruction=WARROOM_CTO_INSTRUCTION,
        output_key="cto_critique",
        include_contents="none",
        generate_content_config=_ANALYTICAL,
    )
    persona_cro = LlmAgent(
        **_NO_TRANSFER,
        name="persona_cro",
        description="Rigorous bank CRO/Compliance challenging CMN 4.893, LGPD, MED fraud, Deati and Basel risk.",
        model=build_model(settings.models.collector),
        static_instruction=CONSTITUTION,
        instruction=WARROOM_CRO_INSTRUCTION,
        output_key="cro_critique",
        include_contents="none",
        generate_content_config=_ANALYTICAL,
    )
    persona_cfo = LlmAgent(
        **_NO_TRANSFER,
        name="persona_cfo",
        description="Disciplined bank CFO challenging ROE impact, FinOps predictability and 0-90d payback.",
        model=build_model(settings.models.collector),
        static_instruction=CONSTITUTION,
        instruction=WARROOM_CFO_INSTRUCTION,
        output_key="cfo_critique",
        include_contents="none",
        generate_content_config=_ANALYTICAL,
    )

    c_level_panel = ParallelAgent(
        name="warroom_c_level_panel",
        description="Runs CTO, CRO and CFO executive critiques concurrently over verified BCB metrics.",
        sub_agents=[persona_cto, persona_cro, persona_cfo],
    )

    pitch_coach = LlmAgent(
        **_NO_TRANSFER,
        name="warroom_pitch_coach",
        description=(
            "Principal Google Cloud FSI Deal Strategist synthesizing CTO/CRO/CFO objections into "
            "grounded executive counter-arguments and competitive battlecards."
        ),
        model=build_model(settings.models.consultant),
        static_instruction=CONSTITUTION,
        instruction=WARROOM_COACH_INSTRUCTION,
        tools=[diagnose_institution_gaps_tool, match_gcp_solutions_catalog_tool],
        output_key="warroom_draft",
        generate_content_config=_ANALYTICAL,
        include_contents="default",
    )

    critic = LlmAgent(
        **_NO_TRANSFER,
        name="warroom_critic",
        description="Independent LLM-as-judge auditing BCB numbers and Google Cloud claims in the War Room dossier.",
        model=build_model(settings.models.critic),
        static_instruction=CONSTITUTION,
        instruction=WARROOM_CRITIC_INSTRUCTION,
        output_schema=CriticVerdict,
        output_key="critic_verdict",
        include_contents="default",
        generate_content_config=_DETERMINISTIC,
    )

    publisher = LlmAgent(
        **_NO_TRANSFER,
        name="warroom_publisher",
        description="Applies critic fixes and publishes the final Boardroom War Room Dossier.",
        model=build_model(settings.models.critic),
        static_instruction=CONSTITUTION,
        instruction=WARROOM_PUBLISHER_INSTRUCTION,
        output_key="final_report",
        include_contents="none",
        generate_content_config=_DETERMINISTIC,
    )

    return SequentialAgent(
        name="boardroom_warroom_pipeline",
        description=(
            "Multi-persona Boardroom War Room: runs CTO, CRO and CFO critiques in parallel "
            "over official BCB metrics and synthesizes grounded Google Cloud counter-arguments."
        ),
        sub_agents=[data_prep, c_level_panel, pitch_coach, critic, publisher],
    )


def build_boardroom_roleplay_agent() -> LlmAgent:
    """Interactive 1:1 Executive Roleplay simulator (CTO / CRO / CFO) with live pitch scoring."""
    settings = get_settings()
    return LlmAgent(
        **_NO_TRANSFER,
        name="boardroom_roleplay_agent",
        description=(
            "Interactive 1:1 C-Level pitch practice simulator: roleplays a bank's CTO, CRO or CFO "
            "grounded in real BCB metrics, evaluates user defenses with a 1-5 scorecard and escalates objections."
        ),
        model=build_model(settings.models.consultant),
        static_instruction=CONSTITUTION,
        instruction=BOARDROOM_ROLEPLAY_INSTRUCTION,
        tools=[
            PreloadMemoryTool(),
            build_bacen_toolset(BACEN_DATA_TOOLS),
            diagnose_institution_gaps_tool,
            match_gcp_solutions_catalog_tool,
            simulate_bcb_what_if_scenario_tool,
        ],
        generate_content_config=_ANALYTICAL,
        include_contents="default",
    )
