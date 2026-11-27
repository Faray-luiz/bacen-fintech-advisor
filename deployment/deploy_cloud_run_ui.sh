#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Deploys the full production Web App stack to Google Cloud Run (authenticated):
#   1. Enables required GCP APIs (Run, Cloud Build, Artifact Registry, Secret
#      Manager, Vertex AI, Cloud Logging, Cloud Trace, Cloud Monitoring).
#   2. Deploys private `mcp-bacen` Cloud Run service (OIDC authenticated).
#   3. Stores the `mcp-bacen` URL in Google Secret Manager (`bacen-mcp-url`).
#   4. Creates least-privilege `bacen-advisor-ui-sa` service account and grants:
#      - roles/aiplatform.user (Vertex AI Gemini)
#      - roles/secretmanager.secretAccessor (Secret Manager)
#      - roles/run.invoker on `mcp-bacen` (service-to-service OIDC)
#      - telemetry writer roles (Logging, Trace, Monitoring)
#   5. Deploys `bacen-advisor-ui` (Google M3 Web UI + ADK Multi-Agent + Senior
#      Google Cloud Consultant + Executive PDF Exporter) to Cloud Run with
#      `--no-allow-unauthenticated` and `--session-affinity`.
#   6. Grants `roles/run.invoker` on `bacen-advisor-ui` to the active gcloud user.
# ==============================================================================

GCLOUD="${GCLOUD:-gcloud}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ID="${PROJECT_ID:-$(${GCLOUD} config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
VERTEX_LOCATION="${VERTEX_LOCATION:-global}"
MCP_SERVICE_NAME="${MCP_SERVICE_NAME:-mcp-bacen}"
UI_SERVICE_NAME="${UI_SERVICE_NAME:-bacen-advisor-ui}"
UI_SA_NAME="${UI_SA_NAME:-bacen-advisor-ui-sa}"
INGRESS="${INGRESS:-all}"
SECRET_ID="${SECRET_ID:-bacen-mcp-url}"
MODEL_FLASH="${MODEL_FLASH:-gemini-3-flash-preview}"
MODEL_PRO="${MODEL_PRO:-gemini-3.1-pro-preview}"
PII_MODE="${PII_MODE:-regex}"
INVOKER_USER="${INVOKER_USER:-$(${GCLOUD} config get-value account 2>/dev/null || true)}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: set PROJECT_ID (e.g. PROJECT_ID=my-gcp-project bash deployment/deploy_cloud_run_ui.sh)" >&2
  exit 1
fi

UI_SA="${UI_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> [1/6] Enabling required Google Cloud APIs on ${PROJECT_ID}..."
${GCLOUD} services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  logging.googleapis.com \
  cloudtrace.googleapis.com \
  monitoring.googleapis.com \
  --project "${PROJECT_ID}" \
  --quiet

echo "==> [2/6] Deploying private Bacen MCP server (${MCP_SERVICE_NAME}) to Cloud Run (${REGION})..."
PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" SERVICE_NAME="${MCP_SERVICE_NAME}" GCLOUD="${GCLOUD}" \
  bash "${REPO_ROOT}/mcp_bacen/scripts/deploy_cloud_run.sh"

MCP_BASE_URL="$(${GCLOUD} run services describe "${MCP_SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format="value(status.url)")"
MCP_ENDPOINT="${MCP_BASE_URL%/}/mcp"
echo "    MCP endpoint: ${MCP_ENDPOINT}"

echo "==> [3/6] Storing ${SECRET_ID} in Google Secret Manager..."
if ! ${GCLOUD} secrets describe "${SECRET_ID}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  ${GCLOUD} secrets create "${SECRET_ID}" \
    --project "${PROJECT_ID}" \
    --replication-policy="automatic" \
    --quiet
fi
CURRENT_SECRET="$(${GCLOUD} secrets versions access latest --secret="${SECRET_ID}" --project "${PROJECT_ID}" 2>/dev/null || true)"
if [[ "${CURRENT_SECRET}" != "${MCP_ENDPOINT}" ]]; then
  printf '%s' "${MCP_ENDPOINT}" | ${GCLOUD} secrets versions add "${SECRET_ID}" \
    --project "${PROJECT_ID}" \
    --data-file=- \
    --quiet
  echo "    Added new secret version for ${SECRET_ID}."
else
  echo "    Secret ${SECRET_ID} already points to ${MCP_ENDPOINT}."
fi

echo "==> [4/6] Configuring least-privilege runtime SA ${UI_SA}..."
if ! ${GCLOUD} iam service-accounts describe "${UI_SA}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  ${GCLOUD} iam service-accounts create "${UI_SA_NAME}" \
    --project "${PROJECT_ID}" \
    --display-name "Bacen Fintech Advisor Web UI (Cloud Run)" \
    --description "Runtime identity for the Google M3 Web UI + ADK multi-agent system."
fi

bind_project_role() {
  local role="$1" attempt
  for attempt in 1 2 3 4 5; do
    if ${GCLOUD} projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${UI_SA}" \
        --role="${role}" \
        --condition=None \
        --quiet >/dev/null 2>&1; then
      return 0
    fi
    sleep $((attempt * 3))
  done
  echo "Error: could not grant ${role} to ${UI_SA}" >&2
  return 1
}

for role in \
  roles/aiplatform.user \
  roles/logging.logWriter \
  roles/cloudtrace.agent \
  roles/monitoring.metricWriter; do
  bind_project_role "${role}"
done

${GCLOUD} secrets add-iam-policy-binding "${SECRET_ID}" \
  --project "${PROJECT_ID}" \
  --member="serviceAccount:${UI_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet >/dev/null

${GCLOUD} run services add-iam-policy-binding "${MCP_SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --member="serviceAccount:${UI_SA}" \
  --role="roles/run.invoker" \
  --quiet >/dev/null

echo "==> [5/6] Deploying ${UI_SERVICE_NAME} to Cloud Run (${REGION})..."
${GCLOUD} run deploy "${UI_SERVICE_NAME}" \
  --source "${REPO_ROOT}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed \
  --service-account "${UI_SA}" \
  --ingress "${INGRESS}" \
  --no-allow-unauthenticated \
  --session-affinity \
  --memory 2Gi \
  --cpu 2 \
  --concurrency 20 \
  --timeout 300s \
  --min-instances 0 \
  --max-instances 5 \
  --quiet \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${VERTEX_LOCATION},GOOGLE_GENAI_USE_VERTEXAI=TRUE,MCP_URL_SECRET_ID=${SECRET_ID},MODEL_ROUTER=${MODEL_FLASH},MODEL_COLLECTOR=${MODEL_FLASH},MODEL_CRITIC=${MODEL_FLASH},MODEL_SUMMARIZER=${MODEL_FLASH},MODEL_ANALYST=${MODEL_PRO},MODEL_CONSULTANT=${MODEL_PRO},PII_REDACTION_MODE=${PII_MODE},ENABLE_CLOUD_TRACE=true,LOG_LEVEL=INFO"

UI_URL="$(${GCLOUD} run services describe "${UI_SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format="value(status.url)")"

echo "==> [6/6] Granting Cloud Run Invoker access to authorized user..."
if [[ -n "${INVOKER_USER}" && "${INVOKER_USER}" != *"gserviceaccount.com" ]]; then
  ${GCLOUD} run services add-iam-policy-binding "${UI_SERVICE_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --member="user:${INVOKER_USER}" \
    --role="roles/run.invoker" \
    --quiet >/dev/null
  echo "    Granted roles/run.invoker to user:${INVOKER_USER}"
fi

echo ""
echo "=============================================================================="
echo "PRODUCTION DEPLOY COMPLETE"
echo "  Web UI URL (IAM-protected): ${UI_URL}"
echo "  Private MCP Server URL:     ${MCP_ENDPOINT}"
echo "  Secret Manager Secret:      projects/${PROJECT_ID}/secrets/${SECRET_ID}"
echo ""
echo "To open the authenticated Web UI in your browser:"
echo "  ${GCLOUD} run services proxy ${UI_SERVICE_NAME} --project=${PROJECT_ID} --region=${REGION} --port=8085"
echo "=============================================================================="
