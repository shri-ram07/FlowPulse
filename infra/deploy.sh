#!/usr/bin/env bash
# =====================================================================
# FlowPulse — one-shot Cloud Run deployment.
#
# Usage:
#   export PROJECT=my-gcp-project
#   export REGION=asia-south1                       # optional, default asia-south1
#   export GOOGLE_API_KEY=AIza...                   # optional; without it agents fall back
#   bash infra/deploy.sh
#
# What it does:
#   1. Enables the required Google Cloud APIs (idempotent)
#   2. Creates an Artifact Registry repo (idempotent)
#   3. Creates a runtime service account with least-privilege roles
#   4. Stores the JWT signing secret in Secret Manager
#   5. Builds + deploys the backend container to Cloud Run
#   6. Builds + deploys the frontend container with the backend URL baked in
#   7. Updates backend CORS to include the frontend URL
#   8. Prints final URLs
# =====================================================================
set -euo pipefail

: "${PROJECT:?Please set PROJECT to your GCP project id, e.g. export PROJECT=my-project-123}"
REGION="${REGION:-asia-south1}"
SA_NAME="flowpulse-runtime"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT}/flowpulse"
JWT_SECRET_NAME="flowpulse-jwt"

say() { echo -e "\n\033[1;36m[flowpulse-deploy]\033[0m $*"; }

gcloud config set project "${PROJECT}" >/dev/null

say "1/8  Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudtrace.googleapis.com \
  aiplatform.googleapis.com \
  iamcredentials.googleapis.com \
  firebase.googleapis.com \
  fcm.googleapis.com \
  --quiet

say "2/8  Creating Artifact Registry repo 'flowpulse' in ${REGION}..."
gcloud artifacts repositories create flowpulse \
  --repository-format=docker --location="${REGION}" \
  --description="FlowPulse images" --quiet 2>/dev/null || echo "(already exists)"

say "3/8  Creating runtime service account..."
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="FlowPulse runtime" --quiet 2>/dev/null || echo "(already exists)"

for role in cloudtrace.agent logging.logWriter secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "${PROJECT}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/${role}" --condition=None --quiet >/dev/null
done
# Optional FCM role — only binds if API is enabled.
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/firebasemessaging.admin" --condition=None --quiet >/dev/null 2>&1 || true

say "4/8  Creating JWT secret..."
if ! gcloud secrets describe "${JWT_SECRET_NAME}" >/dev/null 2>&1; then
  python3 -c "import secrets; print(secrets.token_urlsafe(48))" \
    | gcloud secrets create "${JWT_SECRET_NAME}" --data-file=- --quiet
fi
gcloud secrets add-iam-policy-binding "${JWT_SECRET_NAME}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" --quiet >/dev/null

say "5/8  Building backend image..."
gcloud builds submit . \
  --tag "${REGISTRY}/backend" \
  --region="${REGION}" \
  --gcs-log-dir="gs://${PROJECT}_cloudbuild/logs" \
  -- \
  -f infra/Dockerfile.backend \
  2>/dev/null || \
gcloud builds submit . --tag "${REGISTRY}/backend" \
  --config=<(cat <<EOF
steps:
- name: gcr.io/cloud-builders/docker
  args: ['build', '-f', 'infra/Dockerfile.backend', '-t', '${REGISTRY}/backend', '.']
images: ['${REGISTRY}/backend']
EOF
)

say "6/8  Deploying backend to Cloud Run..."
EXTRA_ENV=""
if [[ -n "${GOOGLE_API_KEY:-}" ]]; then
  EXTRA_ENV="--set-env-vars=GOOGLE_API_KEY=${GOOGLE_API_KEY}"
fi

gcloud run deploy flowpulse-backend \
  --image="${REGISTRY}/backend" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --service-account="${SA_EMAIL}" \
  --set-secrets="FLOWPULSE_JWT_SECRET=${JWT_SECRET_NAME}:latest" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT}" \
  ${EXTRA_ENV} \
  --timeout=3600 \
  --session-affinity \
  --cpu=1 --memory=512Mi \
  --min-instances=1 --max-instances=10 \
  --quiet

BACKEND_URL="$(gcloud run services describe flowpulse-backend --region="${REGION}" --format='value(status.url)')"
say "Backend deployed: ${BACKEND_URL}"

WS_URL="${BACKEND_URL/https/wss}/ws"

say "7/8  Building frontend image (baking in backend URL)..."
gcloud builds submit . \
  --config=<(cat <<EOF
steps:
- name: gcr.io/cloud-builders/docker
  args:
  - build
  - -f
  - infra/Dockerfile.frontend
  - --build-arg
  - NEXT_PUBLIC_API_URL=${BACKEND_URL}
  - --build-arg
  - NEXT_PUBLIC_WS_URL=${WS_URL}
  - -t
  - ${REGISTRY}/frontend
  - .
images: ['${REGISTRY}/frontend']
EOF
)

say "Deploying frontend to Cloud Run..."
gcloud run deploy flowpulse-frontend \
  --image="${REGISTRY}/frontend" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="NEXT_PUBLIC_API_URL=${BACKEND_URL},NEXT_PUBLIC_WS_URL=${WS_URL}" \
  --cpu=1 --memory=512Mi \
  --min-instances=0 --max-instances=10 \
  --quiet

FRONTEND_URL="$(gcloud run services describe flowpulse-frontend --region="${REGION}" --format='value(status.url)')"

say "8/8  Updating backend CORS to allow ${FRONTEND_URL}..."
gcloud run services update flowpulse-backend \
  --region="${REGION}" \
  --update-env-vars="FLOWPULSE_CORS_ORIGINS=${FRONTEND_URL}" \
  --quiet

echo
echo "=================================================================="
echo "  Backend   : ${BACKEND_URL}"
echo "  Frontend  : ${FRONTEND_URL}"
echo "  API docs  : ${BACKEND_URL}/docs"
echo "  Cloud Run : https://console.cloud.google.com/run?project=${PROJECT}"
echo "  Traces    : https://console.cloud.google.com/traces/list?project=${PROJECT}"
echo "  Logs      : https://console.cloud.google.com/logs/query?project=${PROJECT}"
echo "=================================================================="
