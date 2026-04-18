# Security Model — FlowPulse

A lightweight STRIDE threat model and the controls FlowPulse ships to address each class. The model covers the live Cloud Run deployment and assumes an untrusted internet attacker.

## Scope

Two Cloud Run services (frontend + backend), fronted by Cloud Run's managed TLS. Staff endpoints gated by a JWT; attendee endpoints are public read-only. Service-to-service calls to Gemini, FCM, BigQuery, Cloud Trace, Cloud Monitoring all go via the runtime service account's metadata-server credentials (no key files on disk).

## STRIDE analysis

| Category | Vector | Control(s) | File reference |
|---|---|---|---|
| **Spoofing** | Fake staff token | HS256 JWT signed with `FLOWPULSE_JWT_SECRET` mounted from **Secret Manager**; verified on every privileged call | [backend/security/auth.py](../backend/security/auth.py) |
|  | Brute-force login | Bcrypt cost-12 hashes + per-IP sliding-window rate-limit (20 login/min) + constant-time failure path | [auth.py](../backend/security/auth.py) |
|  | Session fixation in ADK chat | Stable, client-generated `session_id`; server-side cache keyed by `(runner_id, session_id)` and expires with process lifetime | [adk_runtime.py](../backend/agents/adk_runtime.py) |
| **Tampering** | MITM on HTTP | HSTS `max-age=31536000; includeSubDomains`; Cloud Run terminates TLS with a managed cert | [security/headers.py](../backend/security/headers.py) |
|  | CSRF on staff calls | Bearer-token auth (no cookies) → CSRF not applicable; any future cookie MUST be `SameSite=Strict` + `Secure` | [auth.py](../backend/security/auth.py) |
|  | Payload injection | Pydantic v2 models validate every request body / query / path param; enum + length limits | every `backend/api/routes_*.py` |
| **Repudiation** | Unlogged staff action | Structured JSON audit-log line on every privileged write (`actor`, `action`, `target`, `result`, `request_id`) ingested into Cloud Logging | [backend/core/logging.py](../backend/core/logging.py) + `routes_ops.py`, `routes_fcm.py`, `routes_sim.py`, `routes_auth.py` |
| **Information disclosure** | XSS on chat UI | CSP `script-src 'self' 'unsafe-inline'`, `object-src 'none'`, `frame-ancestors 'none'`; tool-call results are JSON, rendered via React (no `dangerouslySetInnerHTML`) | [headers.py](../backend/security/headers.py) |
|  | Secrets in stack traces | `FastAPI` default error handler hides internals; `configure_logging()` never logs env values; service-account JSON lives outside the repo (`~/.gcp/`) | [logging.py](../backend/core/logging.py) |
|  | Secrets in VCS | `.gitignore` excludes `.env`, `*-fcm.json`, `credentials.json`, `*.pem`; gitleaks runs pre-commit + CI | [.gitignore](../.gitignore), [.pre-commit-config.yaml](../.pre-commit-config.yaml) |
| **Denial of Service** | Flood `/api/agent/attendee` burning Gemini quota | Rate-limit 60/min per IP + `--min-instances=1 --max-instances=10` autoscaling ceiling + budget alerts (documented) | [auth.py:rate_limit](../backend/security/auth.py) |
|  | WebSocket connection flood | Cloud Run connection concurrency cap (80 default) + per-subscriber bounded queue on the event bus (64 frames, drop-oldest policy) | [backend/core/events.py](../backend/core/events.py), [ws.py](../backend/api/ws.py) |
|  | Slow-loris on chat | `httpx.AsyncClient(timeout=5.0)` on every outbound call | [routes_fcm.py](../backend/api/routes_fcm.py) |
| **Elevation of privilege** | Agent tool calls from unauthenticated user | Only **read-only** tools are bound to the Attendee agent; write tools (`dispatch_alert`, `suggest_redirect`) are only bound to the staff-only Orchestrator agent | [backend/agents/tools.py](../backend/agents/tools.py) |
|  | Service-account key theft | Workload-identity style — Cloud Run uses the runtime SA via the metadata server; no JSON key file on the container. Local dev uses `GOOGLE_APPLICATION_CREDENTIALS` pointing outside the repo | [tracing.py](../backend/observability/tracing.py) |

## HTTP response-header baseline (verifiable)

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; …
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: geolocation=(), camera=(), microphone=(), interest-cohort=(), …
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-site
```

Run `curl -I https://flowpulse-backend-g6g2de3yuq-el.a.run.app/api/health` to confirm.

## Automated scans in CI

- **gitleaks** — blocks any commit containing a secret (`.pre-commit-config.yaml` + `.github/workflows/ci.yml`)
- **Trivy** — scans both container images on every push; fails on HIGH/CRITICAL CVEs
- **Dependabot** — weekly pip + npm + docker + actions updates (`.github/dependabot.yml`)
- **SBOM (SPDX JSON)** — `anchore/sbom-action` artefact attached to every CI run (`docs/SBOM-backend.spdx.json`)
- **ruff S-rules** — bandit-equivalent Python security linter, part of the standard ruff check

## Operational hygiene

- Rotate `FLOWPULSE_JWT_SECRET` via Secret Manager new-version; a forced redeploy invalidates all in-flight tokens.
- Rotate `GOOGLE_API_KEY` via AI Studio at least quarterly.
- Quarterly Cloud IAM review on `flowpulse-runtime@...iam.gserviceaccount.com`.
- Budget alert on Cloud Billing — capping runaway spend (documented in `docs/DEPLOYING.md`).

## Known accepted risks (demo)

- Demo staff credentials (`ops`/`ops-demo`, `admin`/`admin-demo`) are in source, clearly labelled `DEMO_STAFF` — not for production. Replace with a real user table + Identity Platform before any live deployment.
- The in-memory rate-limit bucket + session cache reset on Cloud Run cold start and are not shared across instances. For scale beyond the demo, migrate to Redis / Memorystore — documented seam in `auth.py`.
