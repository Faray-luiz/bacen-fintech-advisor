PROJECT_ID ?= demo
REGION     ?= us-central1
PY         ?= .venv/bin/python
GCLOUD     ?= gcloud

.PHONY: install lint test mcp-test mcp-run mcp-deploy eval adk-eval e2e playground playground-otel run tf-bootstrap tf-init infra-plan infra verify-infra infra-destroy deploy adk-deploy deploy-test destroy

install:            ## Create venv and install deps (uses uv if available, else python3 -m venv)
	@if command -v uv >/dev/null 2>&1; then \
		uv venv .venv --python 3.12 && uv pip install --python $(PY) -e ".[dev]"; \
	else \
		python3 -m venv .venv && $(PY) -m pip install -U pip && $(PY) -m pip install -e ".[dev]"; \
	fi

lint:               ## Static checks (ADK agents + MCP server)
	$(PY) -m ruff check bacen_advisor mcp_bacen tests deployment

test:               ## Offline unit & contract tests (ADK agents + MCP server)
	$(PY) -m pytest tests/unit -q
	PYTHONPATH=mcp_bacen $(PY) -m pytest mcp_bacen/tests -q

mcp-test:           ## Run MCP server unit, StreamableHTTP & tracing tests
	PYTHONPATH=mcp_bacen $(PY) -m pytest mcp_bacen/tests -v

mcp-run:            ## Start local Bacen MCP server on http://localhost:8080/mcp
	PYTHONPATH=mcp_bacen $(PY) -m uvicorn src.main:app --host 0.0.0.0 --port 8080

mcp-deploy:         ## Deploy/update the Bacen MCP server on Cloud Run
	PROJECT_ID=$(PROJECT_ID) REGION=$(REGION) GCLOUD=$(GCLOUD) bash mcp_bacen/scripts/deploy_cloud_run.sh

eval:               ## Golden-dataset evaluation (Gemini + live MCP)
	$(PY) -m pytest tests/eval -m eval -q

adk-eval:           ## Golden-dataset evaluation via ADK CLI
	.venv/bin/adk eval bacen_advisor tests/eval/data/bacen_golden.evalset.json --config_file_path tests/eval/data/test_config.json

e2e:                ## Run all user stories against deployed Agent Runtime
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) $(PY) tests/e2e/run_remote_stories.py

playground:         ## ADK dev UI with persistent local SQLite sessions
	.venv/bin/adk web --session_service_uri sqlite:///.adk/sessions.db .

playground-otel:    ## Same, exporting OpenTelemetry traces + logs to Google Cloud Observability
	.venv/bin/adk web --otel_to_cloud --session_service_uri sqlite:///.adk/sessions.db .

run:                ## ADK CLI interactive chat
	.venv/bin/adk run bacen_advisor

TF       ?= terraform
TF_DIR   := terraform
TF_VARS  := -var-file=environments/$(PROJECT_ID).tfvars $(if $(wildcard $(TF_DIR)/environments/$(PROJECT_ID).private.tfvars),-var-file=environments/$(PROJECT_ID).private.tfvars)

tf-bootstrap:       ## Create versioned GCS remote-state bucket (once per project)
	PROJECT_ID=$(PROJECT_ID) REGION=$(REGION) GCLOUD=$(GCLOUD) bash $(TF_DIR)/bootstrap/create_state_bucket.sh

tf-init:            ## terraform init with per-environment backend
	cd $(TF_DIR) && $(TF) init -input=false -backend-config=environments/$(PROJECT_ID).backend.hcl

infra-plan:         ## Review Terraform plan
	cd $(TF_DIR) && $(TF) plan -input=false $(TF_VARS)

infra:              ## Apply infrastructure with Terraform
	cd $(TF_DIR) && $(TF) apply -input=false $(TF_VARS)

verify-infra:       ## Drift detection (exits 2 if cloud infra drifted from code)
	cd $(TF_DIR) && $(TF) plan -input=false -detailed-exitcode -lock=false $(TF_VARS)

infra-destroy:      ## Destroy Terraform-managed infrastructure
	cd $(TF_DIR) && $(TF) destroy -input=false $(TF_VARS)

deploy:             ## Idempotent deploy/update to Agent Runtime
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) $(PY) deployment/deploy.py

adk-deploy:         ## Equivalent ADK CLI deploy (`adk deploy agent_engine`)
	.venv/bin/adk deploy agent_engine --project=$(PROJECT_ID) --region=$(REGION) --staging_bucket=gs://$(PROJECT_ID)-bacen-advisor-staging --display_name=bacen-fintech-advisor bacen_advisor

deploy-test:        ## Smoke-test deployed Agent Runtime
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) $(PY) deployment/deploy.py --test "Compare o Nubank com Itaú, Bradesco e Inter nos 4 pilares do Banco Central"

destroy:            ## Delete Agent Runtime instance, then Terraform infrastructure
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) $(PY) deployment/deploy.py --delete
	$(MAKE) infra-destroy PROJECT_ID=$(PROJECT_ID)
