# Terraform — FlowPulse IaC

Declarative infrastructure for the FlowPulse Cloud Run deployment. Mirrors what `deploy.ps1` does imperatively:

- Project-level Google Cloud API activations
- Artifact Registry repo for the two container images
- Runtime service account + least-privilege roles (Trace, Logging, Secret Manager, Monitoring, BigQuery, Vertex AI, FCM)
- Secret Manager secret for the JWT signing key
- BigQuery dataset for the analytics sink
- Cloud Run v2 services for backend + frontend, with secret mounts, env vars, WebSocket-safe timeouts, session affinity

## Why both imperative (`deploy.ps1`) and declarative (this folder)?

- **Imperative is faster for one-off demos** — a single `deploy.bat` run provisions + deploys in ~10 minutes including Docker builds. No state backend to configure.
- **Declarative is better for a real team** — version-controlled infra, drift detection, reviewable `terraform plan`. This folder is the promoted path for anything beyond a hackathon submission.

Both paths land on the same Cloud Run URLs.

## Usage

Prerequisites: Terraform ≥ 1.6, gcloud authenticated, a GCS bucket for state.

```bash
cd infra/terraform

# one-time backend init
terraform init -backend-config="bucket=<your-tf-state-bucket>"

# preview + apply
terraform plan  -var="project=personal-493605" -var="region=asia-south1"
terraform apply -var="project=personal-493605" -var="region=asia-south1"
```

For Vertex AI mode, add `-var="gemini_api_key="` to leave it unset — the runtime SA will supply credentials via ADC.

## What's deliberately kept imperative

- **Secret payload** — the actual JWT bytes are generated + stored by `deploy.ps1`. They never touch Terraform state.
- **CORS env var on the backend** — set by `deploy.ps1` after both services exist (chicken-and-egg with Terraform dependencies; a second-pass apply would work but adds ceremony).
- **Cloud Scheduler / Looker Studio dashboards** — one-off console work; not in the automated path.

## Related files

- `../deploy.ps1` — imperative deploy script (PowerShell)
- `../deploy.sh` — imperative deploy script (bash)
- `../Dockerfile.backend`, `../Dockerfile.frontend`
- `docs/DEPLOYING.md` — end-user deployment guide
