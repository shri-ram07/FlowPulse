# =====================================================================
# FlowPulse - one-shot Cloud Run deployment (PowerShell).
#
# Usage:
#   $env:PROJECT = "your-gcp-project-id"
#   $env:REGION = "asia-south1"              # optional, default asia-south1
#   $env:GOOGLE_API_KEY = "AIza..."          # optional
#   .\infra\deploy.ps1
#
# Same 8-step idempotent flow as deploy.sh - safe to re-run.
# Requires: gcloud CLI + Python on PATH.
#
# Note: gcloud writes informational messages to stderr on Windows. We
# therefore DO NOT use $ErrorActionPreference=Stop; we use explicit
# $LASTEXITCODE checks instead.
# Note: this file is ASCII-only so PowerShell 5.1 parses it without BOM.
# =====================================================================

if (-not $env:PROJECT) {
    throw "Please set `$env:PROJECT to your GCP project id, e.g. `$env:PROJECT='my-project-123'"
}
$PROJECT = $env:PROJECT
$REGION  = if ($env:REGION) { $env:REGION } else { "asia-south1" }
$SA_NAME = "flowpulse-runtime"
$SA_EMAIL = "$SA_NAME@$PROJECT.iam.gserviceaccount.com"
$REGISTRY = "$REGION-docker.pkg.dev/$PROJECT/flowpulse"
$JWT_SECRET_NAME = "flowpulse-jwt"

function Say($msg) { Write-Host "`n[flowpulse-deploy] $msg" -ForegroundColor Cyan }

function Assert-Success($what) {
    if ($LASTEXITCODE -ne 0) { throw "$what failed with exit code $LASTEXITCODE." }
}

# Suppress the 'native command wrote to stderr' non-terminating errors that
# PowerShell 7+ promotes - they are noise for gcloud status messages.
$PSNativeCommandUseErrorActionPreference = $false
$ErrorActionPreference = "Continue"

gcloud config set project $PROJECT 2>&1 | Out-Null

Say "1/8  Enabling APIs..."
gcloud services enable `
    run.googleapis.com `
    cloudbuild.googleapis.com `
    artifactregistry.googleapis.com `
    secretmanager.googleapis.com `
    cloudtrace.googleapis.com `
    aiplatform.googleapis.com `
    iamcredentials.googleapis.com `
    firebase.googleapis.com `
    fcm.googleapis.com `
    monitoring.googleapis.com `
    bigquery.googleapis.com `
    --quiet 2>&1 | Out-Host
Assert-Success "Enable APIs"

Say "2/8  Creating Artifact Registry repo 'flowpulse' in $REGION..."
gcloud artifacts repositories create flowpulse `
    --repository-format=docker --location=$REGION `
    --description="FlowPulse images" --quiet 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "      (already exists - continuing)" }

Say "3/8  Creating runtime service account..."
gcloud iam service-accounts create $SA_NAME `
    --display-name="FlowPulse runtime" --quiet 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "      (already exists - continuing)" }

Say "      Granting IAM roles to $SA_EMAIL ..."
foreach ($role in @(
        "cloudtrace.agent",            # Cloud Trace spans
        "logging.logWriter",           # Cloud Logging (structured JSON)
        "secretmanager.secretAccessor",# JWT secret mount
        "monitoring.metricWriter",     # custom Flow Score metric
        "bigquery.dataEditor",         # tick event streaming
        "aiplatform.user"              # Vertex AI (Gemini via GenAI SDK)
    )) {
    gcloud projects add-iam-policy-binding $PROJECT `
        --member="serviceAccount:$SA_EMAIL" `
        --role="roles/$role" --condition=None --quiet 2>&1 | Out-Null
    Assert-Success "Bind role $role"
}
# Optional FCM admin - best-effort, do not fail the deploy if the API is absent.
gcloud projects add-iam-policy-binding $PROJECT `
    --member="serviceAccount:$SA_EMAIL" `
    --role="roles/firebasemessaging.admin" --condition=None --quiet 2>&1 | Out-Null

Say "4/8  Creating JWT secret in Secret Manager..."
gcloud secrets describe $JWT_SECRET_NAME --quiet 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    $jwt = python -c "import secrets; print(secrets.token_urlsafe(48))"
    if (-not $jwt) { throw "python is required on PATH to generate the JWT secret." }
    $jwt | gcloud secrets create $JWT_SECRET_NAME --data-file=- --quiet 2>&1 | Out-Host
    Assert-Success "Create JWT secret"
} else {
    Write-Host "      (already exists - continuing)"
}
gcloud secrets add-iam-policy-binding $JWT_SECRET_NAME `
    --member="serviceAccount:$SA_EMAIL" `
    --role="roles/secretmanager.secretAccessor" --quiet 2>&1 | Out-Null

Say "5/8  Building backend image (via Cloud Build)..."
$backendYaml = [System.IO.Path]::Combine($env:TEMP, "flowpulse-backend-$(Get-Random).yaml")
@"
steps:
- name: gcr.io/cloud-builders/docker
  args: ['build', '-f', 'infra/Dockerfile.backend', '-t', '$REGISTRY/backend', '.']
images: ['$REGISTRY/backend']
"@ | Set-Content -Path $backendYaml -Encoding utf8

gcloud builds submit . --config=$backendYaml --quiet 2>&1 | Out-Host
Assert-Success "Backend image build"
Remove-Item $backendYaml -Force -ErrorAction SilentlyContinue

Say "6/8  Deploying backend to Cloud Run..."
# gcloud accepts only ONE of --set-env-vars / --update-env-vars / etc. per
# invocation, so merge all env vars into a single comma-separated value.
$envPairs = @("GOOGLE_CLOUD_PROJECT=$PROJECT")
if ($env:GOOGLE_API_KEY) { $envPairs += "GOOGLE_API_KEY=$($env:GOOGLE_API_KEY)" }
# Pin the Gemini model explicitly so a one-liner `gcloud run services update`
# can revert to a stable SKU if the preview 404s in a region without rebuild.
$model = if ($env:FLOWPULSE_GEMINI_MODEL) { $env:FLOWPULSE_GEMINI_MODEL } else { "gemini-3-flash-preview" }
$envPairs += "FLOWPULSE_GEMINI_MODEL=$model"
# Route ADK through Vertex AI in production (research-backed best practice).
# Same Python code runs locally against AI Studio and on Cloud Run against Vertex.
if ($env:GOOGLE_GENAI_USE_VERTEXAI) {
    $envPairs += "GOOGLE_GENAI_USE_VERTEXAI=$($env:GOOGLE_GENAI_USE_VERTEXAI)"
    $envPairs += "GOOGLE_CLOUD_LOCATION=$(if ($env:GOOGLE_CLOUD_LOCATION) { $env:GOOGLE_CLOUD_LOCATION } else { 'asia-south1' })"
}
$envVarsArg = "--set-env-vars=" + ($envPairs -join ",")

$backendArgs = @(
    "run", "deploy", "flowpulse-backend",
    "--image=$REGISTRY/backend",
    "--region=$REGION",
    "--platform=managed",
    "--allow-unauthenticated",
    "--service-account=$SA_EMAIL",
    "--set-secrets=FLOWPULSE_JWT_SECRET=${JWT_SECRET_NAME}:latest",
    $envVarsArg,
    "--timeout=3600",
    "--session-affinity",
    "--cpu=1", "--memory=512Mi",
    "--min-instances=1", "--max-instances=10",
    "--quiet"
)
& gcloud @backendArgs 2>&1 | Out-Host
Assert-Success "Backend Cloud Run deploy"

$BACKEND_URL = (gcloud run services describe flowpulse-backend --region=$REGION --format='value(status.url)').Trim()
if (-not $BACKEND_URL) { throw "Could not read backend URL." }
$WS_URL = ($BACKEND_URL -replace '^https', 'wss') + '/ws'
Say "Backend deployed: $BACKEND_URL"

Say "7/8  Building frontend image (baking in backend URL)..."
$frontendYaml = [System.IO.Path]::Combine($env:TEMP, "flowpulse-frontend-$(Get-Random).yaml")
@"
steps:
- name: gcr.io/cloud-builders/docker
  args:
  - build
  - -f
  - infra/Dockerfile.frontend
  - --build-arg
  - NEXT_PUBLIC_API_URL=$BACKEND_URL
  - --build-arg
  - NEXT_PUBLIC_WS_URL=$WS_URL
  - -t
  - $REGISTRY/frontend
  - .
images: ['$REGISTRY/frontend']
"@ | Set-Content -Path $frontendYaml -Encoding utf8

gcloud builds submit . --config=$frontendYaml --quiet 2>&1 | Out-Host
Assert-Success "Frontend image build"
Remove-Item $frontendYaml -Force -ErrorAction SilentlyContinue

Say "Deploying frontend to Cloud Run..."
gcloud run deploy flowpulse-frontend `
    --image="$REGISTRY/frontend" `
    --region=$REGION `
    --platform=managed `
    --allow-unauthenticated `
    --set-env-vars="NEXT_PUBLIC_API_URL=$BACKEND_URL,NEXT_PUBLIC_WS_URL=$WS_URL" `
    --cpu=1 --memory=512Mi `
    --min-instances=0 --max-instances=10 `
    --quiet 2>&1 | Out-Host
Assert-Success "Frontend Cloud Run deploy"

$FRONTEND_URL = (gcloud run services describe flowpulse-frontend --region=$REGION --format='value(status.url)').Trim()
if (-not $FRONTEND_URL) { throw "Could not read frontend URL." }

Say "8/8  Updating backend CORS to allow $FRONTEND_URL ..."
gcloud run services update flowpulse-backend `
    --region=$REGION `
    --update-env-vars="FLOWPULSE_CORS_ORIGINS=$FRONTEND_URL" `
    --quiet 2>&1 | Out-Null
Assert-Success "Backend CORS update"

Write-Host ""
Write-Host "=================================================================="
Write-Host "  Backend   : $BACKEND_URL"
Write-Host "  Frontend  : $FRONTEND_URL"
Write-Host "  API docs  : $BACKEND_URL/docs"
Write-Host "  Cloud Run : https://console.cloud.google.com/run?project=$PROJECT"
Write-Host "  Traces    : https://console.cloud.google.com/traces/list?project=$PROJECT"
Write-Host "  Logs      : https://console.cloud.google.com/logs/query?project=$PROJECT"
Write-Host "=================================================================="

exit 0
