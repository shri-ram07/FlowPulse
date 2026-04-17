# Deploying FlowPulse to Google Cloud Run

This guide deploys both services to Cloud Run with WebSockets, Secret Manager, Cloud Logging, and Cloud Trace all wired up.

## Architecture (what gets deployed)

```
Internet ── Cloud Run ── flowpulse-frontend  (Next.js 14, SSR)
                   ──── flowpulse-backend   (FastAPI + WebSocket)
                               │
                               ├─ Gemini 2.0 Flash  (via Google ADK, HTTPS)
                               ├─ Firebase Cloud Messaging  (HTTP v1)
                               ├─ Cloud Trace        (OpenTelemetry → gRPC)
                               ├─ Cloud Logging      (stdout JSON, auto-ingested)
                               └─ Secret Manager     (JWT secret mounted as env)
```

## Prerequisites

- A GCP project with **billing enabled**
- `gcloud` CLI installed and authenticated — `gcloud auth login`
- Your `GOOGLE_API_KEY` (from https://aistudio.google.com/app/apikey) — optional

## Option A — one-shot script (recommended)

```bash
cd /path/to/flowpulse

export PROJECT=your-gcp-project-id
export REGION=asia-south1               # optional, default asia-south1
export GOOGLE_API_KEY=AIza...           # optional

bash infra/deploy.sh
```

The script is idempotent — safe to re-run. It will print the final URLs when done.

## Option B — step-by-step

### 1. Set shell variables

```bash
export PROJECT=your-gcp-project-id
export REGION=asia-south1
export SA=flowpulse-runtime
export SA_EMAIL=${SA}@${PROJECT}.iam.gserviceaccount.com
export REGISTRY=${REGION}-docker.pkg.dev/${PROJECT}/flowpulse
```

### 2. Enable APIs

```bash
gcloud config set project $PROJECT
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    cloudtrace.googleapis.com \
    aiplatform.googleapis.com \
    iamcredentials.googleapis.com \
    firebase.googleapis.com \
    fcm.googleapis.com
```

### 3. Create Artifact Registry repo

```bash
gcloud artifacts repositories create flowpulse \
    --repository-format=docker --location=$REGION
```

### 4. Runtime service account

```bash
gcloud iam service-accounts create $SA --display-name="FlowPulse runtime"

for role in cloudtrace.agent logging.logWriter secretmanager.secretAccessor firebasemessaging.admin; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member=serviceAccount:$SA_EMAIL --role=roles/$role --condition=None
done
```

### 5. JWT secret in Secret Manager

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))" \
    | gcloud secrets create flowpulse-jwt --data-file=-

gcloud secrets add-iam-policy-binding flowpulse-jwt \
    --member=serviceAccount:$SA_EMAIL \
    --role=roles/secretmanager.secretAccessor
```

### 6. Build + deploy backend

```bash
gcloud builds submit . \
    --tag $REGISTRY/backend \
    --machine-type=e2-highcpu-8 \
    -- \
    --dockerfile=infra/Dockerfile.backend   # or use a cloudbuild.yaml

gcloud run deploy flowpulse-backend \
    --image=$REGISTRY/backend \
    --region=$REGION \
    --allow-unauthenticated \
    --service-account=$SA_EMAIL \
    --set-secrets=FLOWPULSE_JWT_SECRET=flowpulse-jwt:latest \
    --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_API_KEY=$GOOGLE_API_KEY \
    --timeout=3600 --session-affinity \
    --cpu=1 --memory=512Mi \
    --min-instances=1 --max-instances=10

BACKEND_URL=$(gcloud run services describe flowpulse-backend \
    --region=$REGION --format='value(status.url)')
WS_URL="${BACKEND_URL/https/wss}/ws"
echo "Backend: $BACKEND_URL"
```

> **Why `--timeout=3600` and `--session-affinity`?** WebSockets need a long idle timeout and sticky sessions so reconnects hit the same instance.

### 7. Build + deploy frontend (with backend URL baked in)

```bash
# Next.js inlines NEXT_PUBLIC_* at BUILD time, so they must be --build-args.
cat > /tmp/frontend-cloudbuild.yaml <<EOF
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
images:
    - ${REGISTRY}/frontend
EOF

gcloud builds submit . --config=/tmp/frontend-cloudbuild.yaml

gcloud run deploy flowpulse-frontend \
    --image=$REGISTRY/frontend \
    --region=$REGION \
    --allow-unauthenticated \
    --set-env-vars=NEXT_PUBLIC_API_URL=$BACKEND_URL,NEXT_PUBLIC_WS_URL=$WS_URL \
    --cpu=1 --memory=512Mi

FRONTEND_URL=$(gcloud run services describe flowpulse-frontend \
    --region=$REGION --format='value(status.url)')
echo "Frontend: $FRONTEND_URL"
```

### 8. Update backend CORS

```bash
gcloud run services update flowpulse-backend \
    --region=$REGION \
    --update-env-vars=FLOWPULSE_CORS_ORIGINS=$FRONTEND_URL
```

## After deploy — smoke checks

```bash
curl $BACKEND_URL/api/health
# {"status":"ok","zones":27,"alerts":0}

curl -s $BACKEND_URL/api/zones | head -c 200
```

Open `$FRONTEND_URL` in a browser:
- `/` → Welcome
- `/map` → live map with WebSocket diffs
- `/chat` → Gemini concierge
- `/ops` → login with `ops` / `ops-demo`

## Observability

- **Logs** — https://console.cloud.google.com/logs/query?project=${PROJECT}
  Filter: `resource.type="cloud_run_revision" AND resource.labels.service_name="flowpulse-backend"`
- **Traces** — https://console.cloud.google.com/traces/list?project=${PROJECT}
  Every agent tool call becomes a span automatically.
- **Cloud Run metrics** — per-revision p50/p95 latency, request count, container CPU.

## Costs (rough estimates, asia-south1)

| Component | Cost at demo load |
|---|---|
| 2 × Cloud Run (min-instance=1 backend, 0 frontend) | ~₹200/month idle |
| Artifact Registry storage (2 images, ~300 MB) | ~₹20/month |
| Secret Manager (1 secret, few reads) | free tier |
| Gemini 2.0 Flash (via ADK) | ~₹0.08 per 1M input tokens — pennies for demos |
| Cloud Trace | 2.5M spans/month free tier |

Scale min-instances=0 on backend for zero idle cost, accepting ~2s cold starts.

## Teardown

```bash
gcloud run services delete flowpulse-frontend flowpulse-backend --region=$REGION --quiet
gcloud artifacts repositories delete flowpulse --location=$REGION --quiet
gcloud secrets delete flowpulse-jwt --quiet
gcloud iam service-accounts delete $SA_EMAIL --quiet
```

## Common pitfalls

- **WebSocket disconnects every 60s** — you forgot `--timeout=3600` on `gcloud run deploy`.
- **403 from Gemini** — API key not set, or it was set without re-building/re-deploying the backend.
- **CORS failures in browser console** — `FLOWPULSE_CORS_ORIGINS` on the backend doesn't include the exact frontend URL (protocol + host, no trailing slash).
- **Frontend calls localhost** — you forgot `--build-arg NEXT_PUBLIC_API_URL=$BACKEND_URL` when building the frontend image.
- **Cold starts 5–10 s** — add `--min-instances=1` on the backend (and optionally frontend).
- **Cloud Trace 403** — runtime service account missing `roles/cloudtrace.agent`.
