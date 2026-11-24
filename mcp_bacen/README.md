# mcp-bacen — Banco Central do Brasil & Open Finance MCP Server

In-memory (Polars + RAM TTL cache) **StreamableHTTP (`/mcp`)** and `stdio` MCP server exposing **7 tools**, **2 resources**, and **2 prompts** over official public Banco Central do Brasil (Olinda OData + CKAN) and Open Finance Brasil pillars.

## Tools
1. `consultar_ranking_reclamacoes_bcb` — BCB Deati Substantiated Complaints Ranking
2. `consultar_taxas_juros_credito` — BCB Olinda `taxaJuros` v2 credit interest rates
3. `consultar_estatisticas_pix_med` — BCB Olinda `Pix_DadosAbertos` v1, SPI availability & MED
4. `consultar_saude_prudencial_ifdata` — BCB IF.data Basel III / ROE & Open Finance Phase 1 uptime
5. `comparar_instituicoes_financeiras` — 4-pillar normalized benchmark (neobanks vs. S1 incumbents)
6. `buscar_datasets_dados_abertos_bcb` — BCB CKAN open-data catalog search
7. `consultar_glossario_metodologia_bcb` — BCB & Open Finance regulatory glossary

## Local development
```bash
PYTHONPATH=mcp_bacen .venv/bin/python -m pytest mcp_bacen/tests -v
PYTHONPATH=mcp_bacen .venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8080
```

## Deploy to private Cloud Run
```bash
PROJECT_ID=<your-project> REGION=us-central1 bash mcp_bacen/scripts/deploy_cloud_run.sh
```
