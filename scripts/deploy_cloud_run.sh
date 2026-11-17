#!/usr/bin/env bash
#
# A4I 2026 - Early Intervention Triage ("First Milestones")
# End-to-End Google Cloud Provisioning & Cloud Run Deployment Script
#
# Usage (from repository root in Google Cloud Shell):
#   bash scripts/deploy_cloud_run.sh          # loads MS + ReferralGraph + deploys Cloud Run
#   bash scripts/deploy_cloud_run.sh CA       # loads CA (leading-zero FIPS 06) + deploys
#   bash scripts/deploy_cloud_run.sh --skip-data

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ARG="${1:-MS}"
STATE="${A4I_STATE:-MS}"
if [[ "${ARG}" != "--skip-data" ]]; then
  STATE="$(printf '%s' "${ARG}" | tr '[:lower:]' '[:upper:]')"
fi

SERVICE_NAME="${A4I_SERVICE_NAME:-first-milestones-triage}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
DATASET="${A4I_DATASET:-a4i_early_intervention}"
BQ_LOCATION="${A4I_LOCATION:-US}"
GEMINI_MODEL="${A4I_GEMINI_MODEL:-gemini-2.5-pro}"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }

command -v gcloud >/dev/null 2>&1 || { echo "ERROR: 'gcloud' CLI not found. Run in Cloud Shell."; exit 1; }
PROJECT_ID="$(gcloud config get-value project 2>/dev/null || true)"
[[ -n "${PROJECT_ID}" && "${PROJECT_ID}" != "(unset)" ]] || {
  echo "ERROR: Set your GCP project first: gcloud config set project YOUR_PROJECT_ID"
  exit 1
}

bold "=== Deploying First Milestones (${STATE}) on Project: ${PROJECT_ID} ==="

bold "1/4  Enabling required Google Cloud APIs (Run, Cloud Build, Artifact Registry, Vertex AI, BigQuery + MCP)"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  bigqueryreservation.googleapis.com \
  --project="${PROJECT_ID}" --quiet

# Enable BigQuery's remote managed MCP endpoint (non-fatal if beta component isn't installed)
gcloud beta services mcp enable bigquery.googleapis.com --project="${PROJECT_ID}" --quiet >/dev/null 2>&1 || true

if [[ "${ARG}" != "--skip-data" ]]; then
  bold "2/4  Provisioning BigQuery Enterprise Graph Reservation, Starter Tables & ReferralGraph (${STATE})"
  bash "${SCRIPT_DIR}/setup_graph.sh" "${STATE}"
else
  bold "2/4  Skipping data reload (--skip-data)"
fi

bold "3/4  Granting BigQuery & Vertex AI IAM permissions to Cloud Run default service account"
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for ROLE in roles/bigquery.dataViewer roles/bigquery.jobUser roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet >/dev/null
done
info "Service account ${COMPUTE_SA} configured."

bold "4/4  Building & deploying unified ADK + MCP Toolbox + Split-Pane UI to Cloud Run (--min-instances=1)"
cd "${REPO_ROOT}"
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --allow-unauthenticated \
  --quiet \
  --min-instances=1 \
  --max-instances=4 \
  --memory=2Gi \
  --cpu=2 \
  --timeout=180 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=TRUE,A4I_DATASET=${DATASET},A4I_LOCATION=${BQ_LOCATION},A4I_STATE=${STATE},A4I_GEMINI_MODEL=${GEMINI_MODEL},A4I_MCP_MODE=auto"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"

echo
bold "Deployment Complete!"
info "Live Coordinator Workbench URL : ${SERVICE_URL}"
info "Health & MCP Status Endpoint   : ${SERVICE_URL}/api/health"
echo
info "(Optional) To also deploy directly to Vertex AI Agent Engine:"
info "  adk deploy agent_engine --project=${PROJECT_ID} --region=${REGION} ./agent/first_milestones"
