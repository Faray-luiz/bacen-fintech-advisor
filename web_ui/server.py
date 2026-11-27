"""FastAPI backend serving the Google Material Design 3 Web UI for Bacen Fintech Advisor.

Runs the existing ADK ``app`` (:mod:`bacen_advisor.agent`) in-process via ``Runner``,
preserving all four ordered plugins (observability, guardrails, tool guard, async memory),
persistent SQLite sessions, real-time SSE multi-agent streaming, interactive Human-in-the-Loop
confirmation for ``export_report_to_gcs``, and per-output Executive PDF generation.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import re
import time
import unicodedata
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.genai import types
from pydantic import BaseModel, Field

from .auth import AccessGate
from .pdf_exporter import PdfReportMetadata, generate_executive_pdf

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_USER_ID = "default_user"
CONFIRMATION_TOOL_NAME = "adk_request_confirmation"

_INTERMEDIATE_PIPELINE_AGENTS = {
    "data_collector",
    "fintech_analyst",
    "quality_critic",
    "gcp_data_prep",
    "gcp_cloud_consultant",
    "gcp_advisory_critic",
}
_CRITIC_AGENTS = {"quality_critic", "gcp_advisory_critic"}
_PUBLISHER_AGENTS = {"report_publisher", "gcp_advisory_publisher"}

_AGENT_STAGE_LABELS: dict[str, tuple[str, str]] = {
    "bacen_coordinator": ("Roteando consulta", "Flash"),
    "knowledge_agent": ("Consultando glossário regulatório & catálogo BCB", "Flash"),
    "quick_data_agent": ("Consultando pilar específico no MCP BCB", "Flash"),
    "report_pipeline": ("Iniciando pipeline multi-agente de benchmark", "Pipeline"),
    "data_collector": ("Coletando dados oficiais dos 4 pilares BCB (MCP)", "Flash"),
    "fintech_analyst": ("Sintetizando benchmark competitivo & estratégia", "Pro"),
    "quality_critic": ("Auditando groundedness & fontes (LLM-as-Judge)", "Flash"),
    "report_publisher": ("Consolidando relatório executivo final", "Flash"),
    "gcp_advisory_pipeline": ("Iniciando consultoria estratégica Google Cloud FSI", "Pipeline"),
    "gcp_data_prep": ("Preparando dados BCB da instituição-alvo e pares", "Flash"),
    "gcp_cloud_consultant": ("Consultor Sênior Google Cloud mapeando oportunidades & arquiteturas", "Pro"),
    "gcp_advisory_critic": ("Auditando números BCB e catálogo Google Cloud (Critic)", "Flash"),
    "gcp_advisory_publisher": ("Consolidando plano executivo Google Cloud final", "Flash"),
}


# --------------------------------------------------------------------------------------
# Request / Response Schemas
# --------------------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Payload for ``POST /api/auth/login``."""

    token: str = Field(min_length=1, max_length=256)


class ConfirmationPayload(BaseModel):
    """Human-in-the-loop response to an ADK ``adk_request_confirmation`` pause."""

    call_id: str = Field(min_length=1)
    confirmed: bool


class ChatStreamRequest(BaseModel):
    """Payload for ``POST /api/chat/stream``."""

    session_id: str | None = None
    message: str | None = None
    confirmation: ConfirmationPayload | None = None


class PdfExportRequest(BaseModel):
    """Payload for ``POST /api/export/pdf``."""

    markdown: str = Field(min_length=1, max_length=250_000)
    title: str | None = Field(default=None, max_length=240)
    prompt: str | None = Field(default=None, max_length=4000)
    agents: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    tool_calls_count: int = Field(default=0, ge=0)
    latency_s: float | None = Field(default=None, ge=0)
    critic_verdict: dict[str, Any] | None = None
    session_id: str | None = None


# --------------------------------------------------------------------------------------
# Helpers for Event Parsing & Formatting
# --------------------------------------------------------------------------------------


def _slugify_filename(title: str | None) -> str:
    base = (title or "relatorio-bacen").strip()
    ascii_only = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()[:48] or "relatorio-bacen"
    ts = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M")
    return f"bacen-{slug}-{ts}.pdf"


def _safe_json_preview(value: Any, max_chars: int = 320) -> str:
    try:
        raw = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        raw = str(value)
    return raw if len(raw) <= max_chars else raw[: max_chars - 3] + "..."


def _summarize_tool_response(resp: Any) -> dict[str, Any]:
    """Extracts a lightweight UI summary from a raw MCP or local tool response."""
    if not isinstance(resp, dict):
        return {"status": "ok", "summary": _safe_json_preview(resp, 180)}

    if resp.get("isError"):
        return {
            "status": "error",
            "summary": str(resp.get("recovery_hint") or resp.get("error") or "Erro retornado pela ferramenta"),
        }
    status = str(resp.get("status") or "success")
    structured = resp.get("structuredContent") if isinstance(resp.get("structuredContent"), dict) else None
    if structured:
        records = structured.get("registros")
        meta = structured.get("metadados_fonte") or {}
        parts: list[str] = []
        if isinstance(records, list):
            parts.append(f"{len(records)} registro(s)")
        if isinstance(meta, dict):
            if meta.get("pilar"):
                parts.append(str(meta["pilar"]))
            if meta.get("periodo_referencia"):
                parts.append(str(meta["periodo_referencia"]))
            if meta.get("origem_leitura"):
                parts.append(str(meta["origem_leitura"]))
        return {
            "status": "success",
            "summary": " · ".join(parts) if parts else _safe_json_preview(structured, 180),
        }

    if "ranking" in resp and isinstance(resp["ranking"], list):
        leader = resp["ranking"][0].get("instituicao") if resp["ranking"] else "-"
        return {
            "status": status,
            "summary": f"{len(resp['ranking'])} instituições ranqueadas · Líder: {leader}",
        }
    if "gaps" in resp and isinstance(resp["gaps"], list) and resp.get("target_institution"):
        critical = sum(1 for g in resp["gaps"] if isinstance(g, dict) and g.get("severity") == "CRITICO")
        return {
            "status": status,
            "summary": (
                f"{resp['target_institution']} ({resp.get('segment', '')}) · "
                f"{len(resp['gaps'])} gap(s) detectado(s)"
                + (f" ({critical} crítico)" if critical else "")
            ),
        }
    if "solutions" in resp and isinstance(resp["solutions"], list):
        cat_size = resp.get("total_catalog_size") or len(resp["solutions"])
        return {
            "status": status,
            "summary": f"{len(resp['solutions'])} iniciativas Google Cloud FSI selecionadas (catálogo: {cat_size})",
        }
    if "gcs_uri" in resp and resp["gcs_uri"]:
        return {"status": status, "summary": f"Exportado para {resp['gcs_uri']}"}
    if "error_message" in resp and resp["error_message"]:
        return {"status": "error", "summary": str(resp["error_message"])}
    return {"status": status, "summary": _safe_json_preview(resp, 180)}


def _try_parse_critic_verdict(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(parsed, dict) and "approved" in parsed and "groundedness_score" in parsed:
        return parsed
    return None


def _agent_model_label(agent_name: str, routing: dict[str, str]) -> str:
    if agent_name == "fintech_analyst":
        return routing.get("analyst", "gemini-pro")
    if agent_name == "gcp_cloud_consultant":
        return routing.get("consultant", routing.get("analyst", "gemini-pro"))
    if agent_name in ("data_collector", "quick_data_agent", "gcp_data_prep"):
        return routing.get("collector", "gemini-flash")
    if agent_name in ("quality_critic", "report_publisher", "gcp_advisory_critic", "gcp_advisory_publisher"):
        return routing.get("critic", "gemini-flash")
    return routing.get("router", "gemini-flash")


def _extract_turns_from_session(session: Any, routing: dict[str, str]) -> list[dict[str, Any]]:
    """Reconstructs clean UI turns (user prompt + final answer + trace) from ADK session events."""
    events = list(getattr(session, "events", None) or [])
    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def _flush_current() -> None:
        nonlocal current
        if current is None:
            return
        final_text = current.pop("_publisher_text", "") or current.pop("_last_visible_text", "") or current.pop("_fallback_text", "")
        current["assistant_text"] = final_text
        if current["assistant_text"] or current["confirmation"] or current["user_message"]:
            turns.append(current)
        current = None

    for ev in events:
        author = getattr(ev, "author", "") or ""
        content = getattr(ev, "content", None)
        parts = list(getattr(content, "parts", None) or [])
        ts = getattr(ev, "timestamp", None)

        if author == "user":
            user_texts = [p.text for p in parts if getattr(p, "text", None)]
            has_conf_resp = any(
                getattr(p, "function_response", None)
                and getattr(p.function_response, "name", "") == CONFIRMATION_TOOL_NAME
                for p in parts
            )
            if has_conf_resp and current is not None:
                # Continuation of HITL confirmation within the same logical turn.
                current["confirmation"] = None
                continue
            _flush_current()
            user_msg = "\n".join(user_texts).strip()
            current = {
                "id": getattr(ev, "id", None) or uuid.uuid4().hex[:10],
                "timestamp": ts,
                "user_message": user_msg,
                "assistant_text": "",
                "final_agent": None,
                "agents": [],
                "models": [],
                "tool_calls": [],
                "critic_verdict": None,
                "confirmation": None,
                "_publisher_text": "",
                "_last_visible_text": "",
                "_fallback_text": "",
            }
            continue

        if current is None:
            current = {
                "id": getattr(ev, "id", None) or uuid.uuid4().hex[:10],
                "timestamp": ts,
                "user_message": "",
                "assistant_text": "",
                "final_agent": None,
                "agents": [],
                "models": [],
                "tool_calls": [],
                "critic_verdict": None,
                "confirmation": None,
                "_publisher_text": "",
                "_last_visible_text": "",
                "_fallback_text": "",
            }

        if author and author not in current["agents"]:
            current["agents"].append(author)
            model_name = _agent_model_label(author, routing)
            if model_name not in current["models"]:
                current["models"].append(model_name)

        for p in parts:
            fc = getattr(p, "function_call", None)
            if fc:
                name = getattr(fc, "name", "")
                args = getattr(fc, "args", None) or {}
                call_id = getattr(fc, "id", "") or ""
                if name == CONFIRMATION_TOOL_NAME:
                    orig = args.get("originalFunctionCall") or {}
                    tc = args.get("toolConfirmation") or {}
                    current["confirmation"] = {
                        "call_id": call_id,
                        "tool_name": orig.get("name", "export_report_to_gcs"),
                        "args": orig.get("args") or {},
                        "hint": tc.get("hint") or "Confirme para executar esta ação de alto impacto.",
                    }
                elif name != "transfer_to_agent":
                    current["tool_calls"].append(
                        {
                            "call_id": call_id,
                            "agent": author,
                            "name": name,
                            "args": args,
                            "status": "pending",
                            "summary": "",
                        }
                    )
            fr = getattr(p, "function_response", None)
            if fr:
                call_id = getattr(fr, "id", "") or ""
                name = getattr(fr, "name", "")
                resp = getattr(fr, "response", None)
                summary = _summarize_tool_response(resp)
                for tc_item in reversed(current["tool_calls"]):
                    if (call_id and tc_item["call_id"] == call_id) or tc_item["name"] == name:
                        tc_item["status"] = summary["status"]
                        tc_item["summary"] = summary["summary"]
                        break

            text = getattr(p, "text", None)
            is_thought = bool(getattr(p, "thought", False))
            if text and not is_thought:
                if author in _CRITIC_AGENTS:
                    parsed = _try_parse_critic_verdict(text)
                    if parsed:
                        current["critic_verdict"] = parsed
                elif author in _PUBLISHER_AGENTS:
                    current["_publisher_text"] = text
                    current["final_agent"] = author
                elif author not in _INTERMEDIATE_PIPELINE_AGENTS:
                    current["_last_visible_text"] = text
                    current["final_agent"] = author
                else:
                    current["_fallback_text"] = text

    _flush_current()
    return turns


def _sse_frame(event_name: str, payload: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


# --------------------------------------------------------------------------------------
# Runtime Holder (lazy Runner creation for fast startup & clean unit testing)
# --------------------------------------------------------------------------------------


class _AgentRuntime:
    def __init__(
        self,
        *,
        session_service: Any | None = None,
        runner: Any | None = None,
        app_name: str | None = None,
    ) -> None:
        self._session_service = session_service
        self._runner = runner
        self._app_name = app_name
        self._lock = asyncio.Lock()

    def get_app_name(self) -> str:
        if self._app_name:
            return self._app_name
        from bacen_advisor.config import get_settings

        return get_settings().app_name

    def get_routing_dict(self) -> dict[str, str]:
        from bacen_advisor.config import get_settings

        m = get_settings().models
        return {
            "router": m.router,
            "collector": m.collector,
            "analyst": m.analyst,
            "consultant": m.consultant,
            "critic": m.critic,
            "summarizer": m.summarizer,
        }

    def get_session_service(self) -> Any:
        if self._session_service is None:
            from google.adk.sessions import DatabaseSessionService

            from bacen_advisor.config import is_managed_runtime

            db_url = os.getenv("WEB_UI_SESSION_DB_URL")
            if not db_url:
                if is_managed_runtime():
                    db_url = "sqlite+aiosqlite:////tmp/web_ui_sessions.db"
                else:
                    adk_dir = REPO_ROOT / ".adk"
                    adk_dir.mkdir(parents=True, exist_ok=True)
                    db_url = f"sqlite+aiosqlite:///{adk_dir / 'web_ui_sessions.db'}"
            self._session_service = DatabaseSessionService(db_url=db_url)
        return self._session_service

    async def get_runner(self) -> Any:
        if self._runner is not None:
            return self._runner
        async with self._lock:
            if self._runner is None:
                from google.adk.memory import InMemoryMemoryService
                from google.adk.runners import Runner

                from bacen_advisor.agent import app as adk_app
                from bacen_advisor.memory import RedactingMemoryService

                self._app_name = adk_app.name
                self._runner = Runner(
                    app=adk_app,
                    session_service=self.get_session_service(),
                    memory_service=RedactingMemoryService(InMemoryMemoryService()),
                    auto_create_session=True,
                )
        return self._runner


# --------------------------------------------------------------------------------------
# FastAPI App Factory
# --------------------------------------------------------------------------------------


def create_app(
    *,
    session_service: Any | None = None,
    runner: Any | None = None,
    app_name: str | None = None,
    access_token: str | None = None,
) -> FastAPI:
    """Builds the FastAPI application serving the Google-standard Web UI & PDF export API."""
    runtime = _AgentRuntime(session_service=session_service, runner=runner, app_name=app_name)
    gate = AccessGate(access_token=access_token)

    api = FastAPI(
        title="Bacen Fintech Advisor — Google-Standard Web UI",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    # Enforce access-token cookie on all /api/* routes when UI auth is enabled.
    _PUBLIC_API_PATHS = {"/api/auth/status", "/api/auth/login", "/api/auth/logout"}

    @api.middleware("http")
    async def _require_ui_auth(request: Request, call_next):
        path = request.url.path
        if (
            gate.enabled
            and path.startswith("/api/")
            and path not in _PUBLIC_API_PATHS
            and request.method != "OPTIONS"
            and not gate.is_authenticated(request)
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Autenticação obrigatória. Informe o token de acesso."},
            )
        return await call_next(request)

    # Support local dev & corporate proxy origins seamlessly.
    api.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|.*\.(googlers\.com|google\.com|googleplex\.com|googleusercontent\.com))(:[0-9]+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if STATIC_DIR.is_dir():
        api.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def _resolve_user_id(x_user_id: str | None) -> str:
        clean = re.sub(r"[^A-Za-z0-9_.-]", "_", (x_user_id or DEFAULT_USER_ID).strip())
        return clean[:64] or DEFAULT_USER_ID

    @api.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        index_file = STATIC_DIR / "index.html"
        if not index_file.is_file():
            raise HTTPException(status_code=404, detail="Frontend assets not found.")
        return FileResponse(index_file, media_type="text/html; charset=utf-8")

    @api.get("/healthz", include_in_schema=False)
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/api/auth/status")
    async def auth_status(request: Request) -> dict[str, bool]:
        enabled = gate.enabled
        return {
            "auth_enabled": enabled,
            "authenticated": gate.is_authenticated(request) if enabled else True,
        }

    @api.post("/api/auth/login")
    async def auth_login(payload: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
        if not gate.enabled:
            return {"status": "ok", "auth_enabled": False}
        client_ip = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
        if gate.is_rate_limited(client_ip):
            raise HTTPException(
                status_code=429,
                detail="Muitas tentativas inválidas. Aguarde alguns minutos e tente novamente.",
            )
        if not gate.verify_password(payload.token):
            gate.record_failure(client_ip)
            raise HTTPException(status_code=401, detail="Senha ou token de acesso inválido.")
        gate.clear_failures(client_ip)
        gate.set_cookie(response, request)
        return {"status": "ok", "authenticated": True}

    @api.post("/api/auth/logout")
    async def auth_logout(response: Response) -> dict[str, Any]:
        gate.clear_cookie(response)
        return {"status": "ok", "authenticated": False}

    @api.get("/api/health")
    async def health() -> dict[str, Any]:
        from urllib.parse import urlparse

        from bacen_advisor.config import get_settings, is_managed_runtime
        from bacen_advisor.tools.mcp_bacen import (
            _OFFLINE_PLACEHOLDER_URL,
            _IdTokenProvider,
            _resolve_mcp_url,
        )

        settings = get_settings()
        try:
            mcp_url = _resolve_mcp_url()
        except Exception:  # noqa: BLE001
            mcp_url = os.getenv("BACEN_MCP_URL", "")
        if mcp_url == _OFFLINE_PLACEHOLDER_URL:
            mcp_url = ""

        mcp_healthy: bool | None = None
        if mcp_url:
            # Probe `/` rather than `/healthz` because Google Frontend reserves `/healthz` on Cloud Run.
            health_url = re.sub(r"/mcp/?$", "/", mcp_url)
            headers: dict[str, str] = {}
            if is_managed_runtime() or health_url.startswith("https://"):
                try:
                    parsed = urlparse(mcp_url)
                    audience = f"{parsed.scheme}://{parsed.netloc}"
                    token = await asyncio.to_thread(_IdTokenProvider(audience).get)
                    headers["Authorization"] = f"Bearer {token}"
                except Exception:  # noqa: BLE001
                    pass
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(health_url, headers=headers)
                    mcp_healthy = resp.status_code == 200
            except Exception:  # noqa: BLE001
                mcp_healthy = False

        return {
            "status": "ok",
            "app_name": runtime.get_app_name(),
            "project_id": settings.project_id,
            "location": settings.location,
            "models": runtime.get_routing_dict(),
            "mcp_url": mcp_url,
            "mcp_healthy": mcp_healthy,
            "reports_bucket_configured": bool(settings.reports_bucket),
            "managed_runtime": is_managed_runtime(),
        }

    @api.get("/api/sessions")
    async def list_sessions(x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
        user_id = _resolve_user_id(x_user_id)
        svc = runtime.get_session_service()
        app_name_val = runtime.get_app_name()
        resp = await svc.list_sessions(app_name=app_name_val, user_id=user_id)
        summaries: list[dict[str, Any]] = []
        for s in getattr(resp, "sessions", None) or []:
            full = await svc.get_session(app_name=app_name_val, user_id=user_id, session_id=s.id)
            turns = _extract_turns_from_session(full or s, runtime.get_routing_dict())
            first_prompt = next((t["user_message"] for t in turns if t.get("user_message")), "")
            title = (first_prompt[:58] + "...") if len(first_prompt) > 60 else (first_prompt or "Nova análise BCB")
            summaries.append(
                {
                    "session_id": s.id,
                    "title": title,
                    "turn_count": len(turns),
                    "last_update_time": getattr(s, "last_update_time", None),
                }
            )
        summaries.sort(key=lambda item: item.get("last_update_time") or 0, reverse=True)
        return {"sessions": summaries}

    @api.post("/api/sessions")
    async def create_session(x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
        user_id = _resolve_user_id(x_user_id)
        svc = runtime.get_session_service()
        session = await svc.create_session(app_name=runtime.get_app_name(), user_id=user_id)
        return {
            "session_id": session.id,
            "title": "Nova análise BCB",
            "turn_count": 0,
            "last_update_time": getattr(session, "last_update_time", None),
        }

    @api.get("/api/sessions/{session_id}")
    async def get_session(
        session_id: str,
        x_user_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        user_id = _resolve_user_id(x_user_id)
        svc = runtime.get_session_service()
        session = await svc.get_session(
            app_name=runtime.get_app_name(), user_id=user_id, session_id=session_id
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Sessão não encontrada.")
        turns = _extract_turns_from_session(session, runtime.get_routing_dict())
        first_prompt = next((t["user_message"] for t in turns if t.get("user_message")), "")
        title = (first_prompt[:58] + "...") if len(first_prompt) > 60 else (first_prompt or "Nova análise BCB")
        return {
            "session_id": session.id,
            "title": title,
            "turns": turns,
        }

    @api.delete("/api/sessions/{session_id}")
    async def delete_session(
        session_id: str,
        x_user_id: str | None = Header(default=None),
    ) -> dict[str, str]:
        user_id = _resolve_user_id(x_user_id)
        svc = runtime.get_session_service()
        await svc.delete_session(
            app_name=runtime.get_app_name(), user_id=user_id, session_id=session_id
        )
        return {"status": "deleted", "session_id": session_id}

    @api.post("/api/chat/stream")
    async def chat_stream(
        req: ChatStreamRequest,
        x_user_id: str | None = Header(default=None),
    ) -> StreamingResponse:
        user_id = _resolve_user_id(x_user_id)
        if not req.confirmation and not (req.message and req.message.strip()):
            raise HTTPException(status_code=422, detail="Envie uma mensagem ou confirmação HITL.")

        svc = runtime.get_session_service()
        app_name_val = runtime.get_app_name()
        session_id = req.session_id
        if not session_id:
            created = await svc.create_session(app_name=app_name_val, user_id=user_id)
            session_id = created.id
        else:
            existing = await svc.get_session(
                app_name=app_name_val, user_id=user_id, session_id=session_id
            )
            if existing is None:
                created = await svc.create_session(
                    app_name=app_name_val, user_id=user_id, session_id=session_id
                )
                session_id = created.id

        if req.confirmation:
            new_message = types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=req.confirmation.call_id,
                            name=CONFIRMATION_TOOL_NAME,
                            response={"confirmed": req.confirmation.confirmed},
                        )
                    )
                ],
            )
            prompt_for_meta = (
                "Aprovação HITL: exportar relatório para Cloud Storage"
                if req.confirmation.confirmed
                else "Cancelamento HITL da exportação"
            )
        else:
            prompt_for_meta = (req.message or "").strip()
            new_message = types.Content(
                role="user",
                parts=[types.Part(text=prompt_for_meta)],
            )

        async def _event_generator() -> AsyncIterator[str]:
            t0 = time.monotonic()
            routing = runtime.get_routing_dict()
            agents_seen: list[str] = []
            models_seen: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            critic_verdict: dict[str, Any] | None = None
            confirmation_req: dict[str, Any] | None = None
            publisher_text = ""
            last_visible_text = ""
            fallback_text = ""
            final_agent: str | None = None

            yield _sse_frame(
                "status",
                {
                    "session_id": session_id,
                    "agent": "bacen_coordinator",
                    "model": routing.get("router", "Flash"),
                    "tier": "Flash",
                    "label": "Analisando solicitação no coordenador...",
                },
            )

            try:
                runner_inst = await runtime.get_runner()
                async for ev in runner_inst.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=new_message,
                ):
                    author = getattr(ev, "author", "") or ""
                    if author and author != "user" and author not in agents_seen:
                        agents_seen.append(author)
                        model_name = _agent_model_label(author, routing)
                        if model_name not in models_seen:
                            models_seen.append(model_name)
                        stage_label, tier = _AGENT_STAGE_LABELS.get(
                            author, (f"Executando {author}...", "Flash")
                        )
                        yield _sse_frame(
                            "status",
                            {
                                "session_id": session_id,
                                "agent": author,
                                "model": model_name,
                                "tier": tier,
                                "label": stage_label,
                            },
                        )

                    content = getattr(ev, "content", None)
                    parts = list(getattr(content, "parts", None) or [])
                    for p in parts:
                        fc = getattr(p, "function_call", None)
                        if fc:
                            fc_name = getattr(fc, "name", "")
                            fc_args = getattr(fc, "args", None) or {}
                            fc_id = getattr(fc, "id", "") or uuid.uuid4().hex[:8]
                            if fc_name == CONFIRMATION_TOOL_NAME:
                                orig = fc_args.get("originalFunctionCall") or {}
                                tc_meta = fc_args.get("toolConfirmation") or {}
                                confirmation_req = {
                                    "call_id": fc_id,
                                    "tool_name": orig.get("name", "export_report_to_gcs"),
                                    "args": orig.get("args") or {},
                                    "hint": tc_meta.get("hint")
                                    or "Confirme explicitamente para gravar este relatório no Cloud Storage.",
                                }
                                yield _sse_frame("confirmation_request", confirmation_req)
                            elif fc_name == "transfer_to_agent":
                                target = fc_args.get("agent_name") or ""
                                stage_label, tier = _AGENT_STAGE_LABELS.get(
                                    target, (f"Delegando para {target}...", "Flash")
                                )
                                yield _sse_frame(
                                    "status",
                                    {
                                        "session_id": session_id,
                                        "agent": target or author,
                                        "model": _agent_model_label(target or author, routing),
                                        "tier": tier,
                                        "label": stage_label,
                                    },
                                )
                            else:
                                entry = {
                                    "call_id": fc_id,
                                    "agent": author,
                                    "name": fc_name,
                                    "args": fc_args,
                                    "status": "running",
                                    "summary": "",
                                }
                                tool_calls.append(entry)
                                yield _sse_frame("tool_call", entry)

                        fr = getattr(p, "function_response", None)
                        if fr:
                            fr_id = getattr(fr, "id", "") or ""
                            fr_name = getattr(fr, "name", "")
                            if fr_name not in ("transfer_to_agent", CONFIRMATION_TOOL_NAME):
                                info = _summarize_tool_response(getattr(fr, "response", None))
                                for tc_item in reversed(tool_calls):
                                    if (fr_id and tc_item["call_id"] == fr_id) or tc_item["name"] == fr_name:
                                        tc_item["status"] = info["status"]
                                        tc_item["summary"] = info["summary"]
                                        break
                                yield _sse_frame(
                                    "tool_result",
                                    {
                                        "call_id": fr_id,
                                        "agent": author,
                                        "name": fr_name,
                                        "status": info["status"],
                                        "summary": info["summary"],
                                    },
                                )

                        text = getattr(p, "text", None)
                        is_thought = bool(getattr(p, "thought", False))
                        if text and not is_thought:
                            if author in _CRITIC_AGENTS:
                                parsed = _try_parse_critic_verdict(text)
                                if parsed:
                                    critic_verdict = parsed
                                    yield _sse_frame("critic_verdict", parsed)
                            elif author in _PUBLISHER_AGENTS:
                                publisher_text = text
                                final_agent = author
                            elif author not in _INTERMEDIATE_PIPELINE_AGENTS:
                                last_visible_text = text
                                final_agent = author
                            else:
                                fallback_text = text

                final_text = publisher_text or last_visible_text or fallback_text
                latency_s = round(time.monotonic() - t0, 1)

                if final_text or not confirmation_req:
                    yield _sse_frame(
                        "assistant_message",
                        {
                            "message_id": uuid.uuid4().hex[:12],
                            "session_id": session_id,
                            "agent": final_agent or (agents_seen[-1] if agents_seen else "bacen_coordinator"),
                            "text": final_text,
                            "prompt": prompt_for_meta,
                            "latency_s": latency_s,
                            "agents": agents_seen,
                            "models": models_seen,
                            "tool_calls": tool_calls,
                            "critic_verdict": critic_verdict,
                            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
                        },
                    )
            except Exception as exc:  # noqa: BLE001
                yield _sse_frame(
                    "error",
                    {
                        "message": f"Erro ao executar o pipeline multi-agente: {exc}",
                        "session_id": session_id,
                    },
                )
            finally:
                yield _sse_frame("done", {"session_id": session_id})

        return StreamingResponse(
            _event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @api.post("/api/export/pdf")
    async def export_pdf(req: PdfExportRequest) -> Response:
        meta = PdfReportMetadata(
            prompt=req.prompt or "",
            agents=req.agents,
            models=req.models,
            tool_calls_count=req.tool_calls_count,
            latency_s=req.latency_s,
            critic_verdict=req.critic_verdict,
            session_id=req.session_id or "",
        )
        pdf_bytes = await asyncio.to_thread(
            generate_executive_pdf,
            req.markdown,
            title=req.title,
            metadata=meta,
        )
        filename = _slugify_filename(req.title or req.prompt)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    return api


app = create_app()
