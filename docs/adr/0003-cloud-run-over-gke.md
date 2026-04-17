# ADR 0003 — Cloud Run over GKE for compute platform

Status: **Accepted**
Date: 2026-04-16
Deciders: Shri Ram Dwivedi

## Context

FlowPulse needs a compute platform that:
- Scales from zero (demo cost) to several instances under burst load.
- Terminates TLS + auto-manages certs (demo URLs must Just Work).
- Supports WebSockets with session affinity (our real-time channel).
- Integrates with Secret Manager, Cloud Trace, Cloud Logging, Cloud Monitoring, Artifact Registry out of the box.
- Requires minimum operator effort — we are one person shipping in a week.

GKE Autopilot (Google-managed Kubernetes) and Cloud Run are both credible. The GKE hackathon winners in 2024-25 showcased multi-node deployments with Terraform, which carries points for "production-ready" signalling.

## Decision

Deploy both services on **Cloud Run** (managed, request-based autoscaling) with:

- `--timeout=3600` + `--session-affinity` for WebSocket stability.
- `--min-instances=1` on the backend to eliminate cold-start in the demo window.
- `--max-instances=10` ceiling against runaway scale (and quota burn on Gemini).
- Runtime service-account identity (no key file); Secret Manager for JWT.
- Cloud Build → Artifact Registry → Cloud Run rollout via `deploy.bat` / `deploy.ps1`.

A **Terraform skeleton** (`infra/terraform/main.tf`) is included to signal IaC-readiness to judges and to give future maintainers a starting point — without committing to maintain GKE manifests now.

## Consequences

**Positive**
- Full deploy fits in an 8-minute `deploy.bat` run; rebuilds ~3 minutes.
- TLS, DDoS mitigation, and HTTP/2 come free.
- Cost: ≈ ₹200/month idle (one warm instance) → ₹0/month with `--min-instances=0` if we accept cold starts.
- Observability hooks (trace / logging / metrics) work with zero extra infra.

**Negative**
- Cloud Run tops out around 1,000 concurrent connections per instance. For a 40k-seat venue we would need either multiple instances behind a Cloud Load Balancer (still Cloud Run) or migrate to GKE when per-pod resource limits matter.
- Background tasks are not first-class; our simulator runs inside the request-serving container. Fine for demo; for production we'd split the simulator into a Cloud Run Job or Pub/Sub worker.

## Alternatives considered

- **GKE Autopilot**: high judge-points per the research (research item #9), but adds 3+ hours of Terraform + kubectl setup for no demo-visible benefit. Keeping it as an "if we had more time" migration target.
- **Compute Engine VM**: rejected — manual TLS, no autoscaling, no managed metadata server for credentials.
- **App Engine Standard**: no WebSocket support in the flexible-response-time tier we'd need.
