"""Structural tests: agent graph, model routing, HITL wiring, memory redaction & prod hardening."""

import asyncio
import json
import sys
import types as pytypes
from pathlib import Path
from types import SimpleNamespace

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.events.event import Event
from google.adk.sessions.session import Session
from google.genai import types

from bacen_advisor.agent import app, root_agent
from bacen_advisor.memory import MemoryPlugin, RedactingMemoryService
from bacen_advisor.plugins import GuardrailsPlugin, ObservabilityPlugin, ToolGuardPlugin
from bacen_advisor.schemas import MCP_ARG_SCHEMAS, TOOL_JSON_SCHEMAS, CriticVerdict


def _by_name(agent, name):
    if agent.name == name:
        return agent
    for sub in agent.sub_agents:
        found = _by_name(sub, name)
        if found:
            return found
    return None


def test_coordinator_routes_to_specialists():
    names = [a.name for a in root_agent.sub_agents]
    assert names == [
        "knowledge_agent",
        "quick_data_agent",
        "report_pipeline",
        "gcp_advisory_pipeline",
    ]


def test_gcp_advisory_pipeline_is_sequential_with_pro_consultant_and_critic():
    pipeline = _by_name(root_agent, "gcp_advisory_pipeline")
    assert isinstance(pipeline, SequentialAgent)
    assert [a.name for a in pipeline.sub_agents] == [
        "gcp_data_prep",
        "gcp_cloud_consultant",
        "gcp_advisory_critic",
        "gcp_advisory_publisher",
    ]
    consultant = _by_name(root_agent, "gcp_cloud_consultant")
    critic = _by_name(root_agent, "gcp_advisory_critic")
    assert "pro" in consultant.model.model
    assert "flash" in critic.model.model
    assert critic.output_schema is CriticVerdict
    consultant_tools = {getattr(t, "name", "") for t in consultant.tools}
    assert {"diagnose_institution_gaps", "match_gcp_solutions_catalog"} <= consultant_tools
    assert "export_report_to_gcs" not in consultant_tools


def test_report_pipeline_is_sequential_with_critic():
    pipeline = _by_name(root_agent, "report_pipeline")
    assert isinstance(pipeline, SequentialAgent)
    assert [a.name for a in pipeline.sub_agents] == [
        "data_collector",
        "fintech_analyst",
        "quality_critic",
        "report_publisher",
    ]
    critic = _by_name(root_agent, "quality_critic")
    assert critic.output_schema is CriticVerdict


def test_model_routing_flash_vs_pro():
    analyst = _by_name(root_agent, "fintech_analyst")
    collector = _by_name(root_agent, "data_collector")
    critic = _by_name(root_agent, "quality_critic")
    assert "pro" in analyst.model.model
    assert "flash" in collector.model.model
    assert "flash" in critic.model.model
    assert analyst.model.retry_options.attempts >= 3


def test_hitl_export_only_on_coordinator():
    for agent in [root_agent, *root_agent.sub_agents]:
        tools = [getattr(t, "name", "") for t in getattr(agent, "tools", [])]
        if agent is root_agent:
            assert "export_report_to_gcs" in tools
        else:
            assert "export_report_to_gcs" not in tools


def test_app_wires_plugins_compaction_and_cache():
    kinds = {type(p) for p in app.plugins}
    assert {GuardrailsPlugin, ToolGuardPlugin, ObservabilityPlugin, MemoryPlugin} <= kinds
    assert app.events_compaction_config is not None
    assert app.context_cache_config is not None


def test_observability_plugin_runs_first():
    """ADK stops at the first plugin returning a value; ObservabilityPlugin must go first."""
    assert isinstance(app.plugins[0], ObservabilityPlugin)


def test_only_coordinator_can_transfer():
    """Specialists must disable transfer so routing loops are structurally impossible."""

    def walk(a):
        yield a
        for s in a.sub_agents:
            yield from walk(s)

    for agent in walk(root_agent):
        if isinstance(agent, LlmAgent) and agent is not root_agent:
            assert agent.disallow_transfer_to_parent and agent.disallow_transfer_to_peers, agent.name


def test_all_llm_agents_share_constitution():
    def walk(a):
        yield a
        for s in a.sub_agents:
            yield from walk(s)

    for agent in walk(root_agent):
        if isinstance(agent, LlmAgent):
            assert "Hard rules" in agent.static_instruction


def test_no_proactive_save_offer_in_instructions():
    from bacen_advisor.prompts import CONSTITUTION, PUBLISHER_INSTRUCTION

    assert "Never proactively offer or suggest saving/exporting" in CONSTITUTION
    assert "Do not offer, suggest or ask about\n  saving, exporting or sharing" in PUBLISHER_INSTRUCTION


class _CaptureMemory:
    def __init__(self):
        self.session = None

    async def add_session_to_memory(self, session):
        self.session = session

    async def search_memory(self, **_):
        return None


async def test_memory_is_redacted_before_storage():
    inner = _CaptureMemory()
    svc = RedactingMemoryService(inner)
    session = Session(
        id="s1",
        app_name="bacen_advisor",
        user_id="u1",
        events=[
            Event(
                author="user",
                content=types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            text="Acompanho o Nubank e neobanks, meu email é maria@fintech.com e chave 550e8400-e29b-41d4-a716-446655440000"
                        )
                    ],
                ),
            )
        ],
    )
    await svc.add_session_to_memory(session)
    stored = inner.session.events[0].content.parts[0].text
    assert "maria@fintech.com" not in stored
    assert "550e8400-e29b-41d4-a716-446655440000" not in stored
    assert "[REDACTED_EMAIL_ADDRESS]" in stored
    assert "[REDACTED_PIX_EVP_KEY]" in stored
    assert "Nubank" in stored
    # Original session object stays untouched
    assert "maria@fintech.com" in session.events[0].content.parts[0].text


async def test_memory_plugin_persists_every_invocation():
    inner = _CaptureMemory()
    session = Session(id="s1", app_name="bacen_advisor", user_id="u1", events=[])
    ctx = SimpleNamespace(memory_service=inner, session=session, invocation_id="i1")
    await MemoryPlugin().after_run_callback(invocation_context=ctx)
    await asyncio.sleep(0)
    assert inner.session is session


def test_dev_overrides_ignored_in_managed_runtime(monkeypatch):
    from bacen_advisor import secrets

    class _FakeSM:
        def access_secret_version(self, request):
            return SimpleNamespace(payload=SimpleNamespace(data=b"https://mcp-bacen-sm.run.app"))

    fake_module = pytypes.SimpleNamespace(SecretManagerServiceClient=lambda: _FakeSM())
    monkeypatch.setitem(sys.modules, "google.cloud.secretmanager", fake_module)
    monkeypatch.setenv("GOOGLE_CLOUD_AGENT_ENGINE_ID", "999")
    monkeypatch.setenv("BACEN_MCP_URL", "https://attacker.invalid")
    secrets.get_secret.cache_clear()
    try:
        value = secrets.get_secret("bacen-mcp-url", env_override="BACEN_MCP_URL")
    finally:
        secrets.get_secret.cache_clear()
    assert value == "https://mcp-bacen-sm.run.app"


def test_mcp_url_uses_offline_placeholder_outside_managed_runtime(monkeypatch):
    from bacen_advisor.secrets import SecretNotFoundError, get_secret
    from bacen_advisor.tools import mcp_bacen

    monkeypatch.delenv("BACEN_MCP_URL", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_AGENT_ENGINE_ID", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setattr(
        mcp_bacen,
        "get_secret",
        lambda *_a, **_kw: (_ for _ in ()).throw(SecretNotFoundError("no secret")),
    )
    assert mcp_bacen._resolve_mcp_url() == mcp_bacen._OFFLINE_PLACEHOLDER_URL

    monkeypatch.setenv("GOOGLE_CLOUD_AGENT_ENGINE_ID", "999")
    try:
        mcp_bacen._resolve_mcp_url()
        raise AssertionError("Expected SecretNotFoundError in managed runtime")
    except SecretNotFoundError:
        pass
    finally:
        get_secret.cache_clear()


def test_export_returns_guided_error_when_bucket_unconfigured(monkeypatch):
    from bacen_advisor.tools import report_tools

    monkeypatch.setattr(report_tools, "get_settings", lambda: SimpleNamespace(reports_bucket="", project_id="p"))
    out = report_tools.export_report_to_gcs("Benchmark", "Conteúdo", SimpleNamespace(user_id="../u", state={}))
    assert out["status"] == "error"
    assert out["recovery_hint"]


def test_golden_dataset_trajectories_and_schemas_are_valid():
    data_dir = Path(__file__).resolve().parents[1] / "eval" / "data"
    evalset = json.loads((data_dir / "bacen_golden.evalset.json").read_text(encoding="utf-8"))
    config = json.loads((data_dir / "test_config.json").read_text(encoding="utf-8"))

    assert "tool_trajectory_avg_score" in config["criteria"]
    assert "final_response_match_v2" in config["criteria"]
    assert len(evalset["eval_cases"]) >= 4

    specialist_names = {a.name for a in root_agent.sub_agents}
    for case in evalset["eval_cases"]:
        assert case["session_input"]["app_name"] == app.name
        for turn in case["conversation"]:
            assert turn["user_content"]["parts"][0]["text"]
            assert turn["final_response"]["parts"][0]["text"]
            for tool_use in turn["intermediate_data"]["tool_uses"]:
                name = tool_use["name"]
                args = tool_use.get("args", {})
                if name == "transfer_to_agent":
                    assert args["agent_name"] in specialist_names
                elif name in MCP_ARG_SCHEMAS:
                    MCP_ARG_SCHEMAS[name].model_validate(args)
                elif name in TOOL_JSON_SCHEMAS:
                    assert isinstance(args, dict)
                else:
                    raise AssertionError(f"Unknown tool in golden dataset: {name}")
