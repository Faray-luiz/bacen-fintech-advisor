"""Unit & API contract tests for the Google Material Design 3 Web UI and PDF exporter."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from fastapi.testclient import TestClient
from google.adk.sessions import InMemorySessionService
from google.genai import types

from web_ui.pdf_exporter import PdfReportMetadata, generate_executive_pdf
from web_ui.server import create_app

SAMPLE_BENCHMARK_MD = """# Benchmark Competitivo BCB — Nubank vs. Incumbentes (2026-Q3)

## Resumo Executivo

O **Nubank** apresenta liderança em eficiência operacional no **Pix/MED** e menor índice de reclamações
entre os grandes bancos digitais, enquanto o **Itaú** combina forte rentabilidade (**ROE 22,4%**) com
taxa competitiva no cartão rotativo.

> Nota de governança: Todos os números provêm exclusivamente dos conjuntos de dados públicos do
> Banco Central do Brasil (Deati, Olinda TaxasJuros, Pix/MED e IF.data).

## Matriz Comparativa nos 4 Pilares

| Instituição | Segmento | Índice Reclamações (↓) | Rotativo a.a. (↓) | Uptime SPI (↑) | Basileia (↑) | Score (0-10) |
| --- | --- | --- | --- | --- | --- | --- |
| **NUBANK** | NEOBANKS | 8,4 | 312,5% | 99,97% | 17,8% | 8,45 |
| **ITAU** | INCUMBENTES | 11,2 | 289,0% | 99,95% | 16,4% | 8,12 |
| **INTER** | NEOBANKS | 19,6 | 334,2% | 99,91% | 19,1% | 7,60 |
| **BRADESCO** | INCUMBENTES | 24,1 | 351,8% | 99,88% | 15,7% | 6,95 |

### Recomendações Prioritárias

1. **Redução de atrito no MED**: priorizar automação de devolução em até 24h.
2. **Competitividade no rotativo**: ofertar migração proativa para parcelamento com juros menores.
- Revisar alertas trimestrais de reclamações no Deati (`2026-Q3`).
- Consultar séries completas em [Dados Abertos BCB](https://dadosabertos.bcb.gov.br).

```json
{"pilar": "consolidado_4_pilares", "periodo": "2026-Q3"}
```
"""


def test_generate_executive_pdf_renders_valid_multielement_document():
    pdf_bytes = generate_executive_pdf(
        SAMPLE_BENCHMARK_MD,
        title="Benchmark Nubank vs. Incumbentes — 2026-Q3",
        metadata=PdfReportMetadata(
            prompt="Compare o Nubank com Itaú, Bradesco e Inter nos 4 pilares do Banco Central",
            agents=["bacen_coordinator", "data_collector", "fintech_analyst", "quality_critic", "report_publisher"],
            models=["gemini-3-flash-preview", "gemini-3.1-pro-preview"],
            tool_calls_count=1,
            latency_s=48.3,
            critic_verdict={
                "approved": True,
                "groundedness_score": 5,
                "issues": [],
                "summary": "Todos os números conferem com os retornos do servidor MCP BCB.",
            },
        ),
    )
    assert pdf_bytes.startswith(b"%PDF-")
    assert b"%%EOF" in pdf_bytes
    assert len(pdf_bytes) > 4000


def test_generate_executive_pdf_redacts_pii_and_handles_emojis():
    md = (
        "# Relatório com PII e Emojis 🥇✅\n\n"
        "Contato: analista@banco.com.br, CPF 123.456.789-01 e chave Pix "
        "123e4567-e89b-12d3-a456-426614174000.\n"
    )
    pdf_bytes = generate_executive_pdf(
        md,
        metadata=PdfReportMetadata(prompt="Relatório para cliente 123.456.789-01"),
    )
    assert pdf_bytes.startswith(b"%PDF-")
    assert b"123.456.789-01" not in pdf_bytes
    assert b"analista@banco.com.br" not in pdf_bytes
    assert b"123e4567-e89b-12d3-a456-426614174000" not in pdf_bytes


@dataclass
class _FakeEvent:
    author: str
    content: types.Content
    id: str = "ev-1"
    timestamp: float = 1700000000.0


@dataclass
class _FakeRunner:
    events: list[Any] = field(default_factory=list)

    async def run_async(self, *, user_id: str, session_id: str, new_message: types.Content):
        del user_id, session_id, new_message
        for ev in self.events:
            yield ev


def test_web_ui_routes_health_sessions_and_pdf_export():
    app = create_app(session_service=InMemorySessionService(), app_name="bacen_advisor")
    client = TestClient(app)

    # Index HTML renders Google-standard UI shell.
    idx = client.get("/")
    assert idx.status_code == 200
    assert "Bacen Fintech Advisor" in idx.text
    assert "Exportar PDF" in idx.text or "/static/app.js" in idx.text

    # Liveness probe for Cloud Run.
    live = client.get("/healthz")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"

    # Health endpoint returns active routing configuration.
    health = client.get("/api/health")
    assert health.status_code == 200
    h_data = health.json()
    assert h_data["status"] == "ok"
    assert "models" in h_data and "analyst" in h_data["models"]

    # Session lifecycle (create -> list -> get -> delete).
    created = client.post("/api/sessions")
    assert created.status_code == 200
    sid = created.json()["session_id"]

    listed = client.get("/api/sessions")
    assert listed.status_code == 200
    assert any(s["session_id"] == sid for s in listed.json()["sessions"])

    fetched = client.get(f"/api/sessions/{sid}")
    assert fetched.status_code == 200
    assert fetched.json()["session_id"] == sid

    # Per-output PDF export endpoint.
    pdf_resp = client.post(
        "/api/export/pdf",
        json={
            "title": "Benchmark Nubank 2026-Q3",
            "markdown": SAMPLE_BENCHMARK_MD,
            "prompt": "Compare Nubank e Itaú",
            "agents": ["data_collector", "fintech_analyst", "quality_critic", "report_publisher"],
            "tool_calls_count": 1,
            "latency_s": 32.5,
            "critic_verdict": {"approved": True, "groundedness_score": 5, "issues": [], "summary": "OK"},
        },
    )
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert 'filename="bacen-benchmark-nubank-2026-q3-' in pdf_resp.headers["content-disposition"]
    assert pdf_resp.content.startswith(b"%PDF-")

    deleted = client.delete(f"/api/sessions/{sid}")
    assert deleted.status_code == 200


def test_web_ui_chat_stream_emits_pipeline_and_critic_events():
    verdict_json = json.dumps(
        {
            "approved": True,
            "groundedness_score": 5,
            "issues": [],
            "summary": "Todos os indicadores verificados contra o MCP BCB.",
        }
    )
    fake_runner = _FakeRunner(
        events=[
            _FakeEvent(
                author="data_collector",
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                id="call-1",
                                name="comparar_instituicoes_financeiras",
                                args={"instituicoes": ["NUBANK", "ITAU"]},
                            )
                        )
                    ],
                ),
            ),
            _FakeEvent(
                author="data_collector",
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                id="call-1",
                                name="comparar_instituicoes_financeiras",
                                response={
                                    "structuredContent": {
                                        "registros": [{"instituicao": "NUBANK"}, {"instituicao": "ITAU"}],
                                        "metadados_fonte": {
                                            "pilar": "consolidado_4_pilares",
                                            "periodo_referencia": "2026-Q3",
                                        },
                                    }
                                },
                            )
                        )
                    ],
                ),
            ),
            _FakeEvent(
                author="fintech_analyst",
                content=types.Content(role="model", parts=[types.Part(text="Rascunho intermediário do analista")]),
            ),
            _FakeEvent(
                author="quality_critic",
                content=types.Content(role="model", parts=[types.Part(text=verdict_json)]),
            ),
            _FakeEvent(
                author="report_publisher",
                content=types.Content(role="model", parts=[types.Part(text="# Relatório Final\n\nNubank lidera no Pix.")]),
            ),
        ]
    )
    app = create_app(
        session_service=InMemorySessionService(),
        runner=fake_runner,
        app_name="bacen_advisor",
    )
    client = TestClient(app)

    resp = client.post("/api/chat/stream", json={"message": "Compare Nubank e Itaú"})
    assert resp.status_code == 200
    body = resp.text
    assert "event: status" in body
    assert "event: tool_call" in body
    assert "event: tool_result" in body
    assert "event: critic_verdict" in body
    assert "event: assistant_message" in body
    assert "Relatório Final" in body
    # Intermediate analyst draft must NOT replace report_publisher final text.
    assert "Rascunho intermediário do analista" not in body
    assert "event: done" in body
