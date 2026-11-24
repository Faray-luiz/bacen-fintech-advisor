# Security Policy

## Reporting a vulnerability
Please do **not** open public issues for security vulnerabilities. Report them privately via
GitHub Security Advisories on this repository's Security tab.

## Security control matrix

| Area | Control |
|---|---|
| **Public-data boundary** | Uses exclusively public Banco Central do Brasil (Olinda OData / CKAN) & Open Finance Phase 1 data plus deterministic public-domain benchmark snapshots. Zero confidential customer data, proprietary schemas or credentials exist in this repository. |
| **Workload identity** | Dedicated runtime SA (`bacen-advisor-sa`), separate CI/CD deployer SA (`bacen-advisor-deployer`) and telemetry-only MCP SA (`mcp-bacen-sa`). Zero static service-account keys. GitHub Actions authenticates via keyless Workload Identity Federation restricted to this repo. |
| **Least privilege & separation of duties** | Resource-scoped IAM bindings (`run.invoker` on `mcp-bacen`, `secretAccessor` on `bacen-mcp-url`, `objectCreator` only on the reports bucket). CI/CD cannot modify IAM or provision infrastructure. |
| **Secret management** | MCP endpoint resolved at runtime via Google Secret Manager. Local developer overrides (`BACEN_MCP_URL`, `MCP_ID_TOKEN`) are ignored when `is_managed_runtime()` is true. |
| **Service-to-service auth** | Private Cloud Run MCP service requiring Google-signed OIDC ID tokens scoped to the Cloud Run audience. |
| **Prompt & output guardrails** | Layered Google Cloud Model Armor (`SanitizeUserPrompt` / `SanitizeModelResponse`) + zero-latency deterministic rules (prompt injection, system-prompt exfiltration, KYC/AML bypass blocking) + independent LLM-as-judge `quality_critic`. |
| **Tool safety & HITL** | Strict Pydantic input/output validation (`extra="forbid"`) via `ToolGuardPlugin`; mandatory human confirmation (`require_confirmation=True`) before the sole write action (`export_report_to_gcs`). |
| **PII protection** | Google Cloud DLP (`BRAZIL_CPF_NUMBER`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD_NUMBER`, `PERSON_NAME`) preceded by atomic regex scrubbing (CNPJ + Pix random EVP UUID keys) on logs, exported reports and Memory Bank writes. |
| **Telemetry privacy** | Prompts, answers and tool arguments are never copied into OpenTelemetry spans (`ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false`, `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=NO_CONTENT`). |
| **Supply chain** | Bounded dependency ranges, Dependabot, `pip-audit` and `gitleaks` in GitHub Actions CI. |
