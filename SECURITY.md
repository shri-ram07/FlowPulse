# Security Policy

## Reporting a vulnerability

If you discover a security issue in FlowPulse, please **do not open a public
issue**. Instead, email the maintainer directly:

- **Contact:** 159000468+shri-ram07@users.noreply.github.com
- **Subject:** "FlowPulse security: <one-line summary>"

Include (to the extent you can):

- A description of the vulnerability and its impact.
- Steps to reproduce — ideally a minimal proof-of-concept.
- Affected versions / commits / Cloud Run revisions.
- Your name/handle if you'd like to be credited in the CHANGELOG.

**Response times** (best-effort; solo maintainer):

| Severity      | Ack within | Patch target |
|---------------|:----------:|:------------:|
| Critical / RCE | 24 h      | 72 h         |
| High           | 48 h      | 1 week       |
| Medium / Low   | 1 week    | 2 weeks      |

## Supported versions

Only the latest release line is actively supported:

| Version | Supported |
|---------|:---------:|
| 1.2.x   | ✅ yes    |
| 1.1.x   | ⚠️ critical fixes only — upgrade to 1.2.x |
| 1.0.x   | ❌ upgrade to 1.2.x |

## Unauthenticated endpoints (by design)

Not every endpoint requires a JWT. The following are **public read-only** —
their payloads carry no PII and no write capability:

| Endpoint | Why it's public |
|---|---|
| `GET /api/zones` · `GET /api/zones/{id}` · `GET /api/zones/graph` · `GET /api/zones/{id}/forecast` · `GET /api/zones/route/{start}/{dest}` | The stadium layout + live Flow Scores drive the fan-facing PWA. Same signal a stadium big-screen would display. |
| `GET /api/sim/state` | Exposes only `{phase, elapsed, chaos}` — internal simulator state, no crowd identity. |
| `POST /api/agent/attendee` · `POST /api/agent/attendee/reset` | Fan-facing concierge. Read-only by design — the Attendee agent has no write-capable tool. |
| `WebSocket /ws` | Broadcasts the same zone snapshots as the REST `/api/zones` endpoint. |
| `POST /api/csp-report` | Receives browser CSP violation reports; never queried, only written to Cloud Logging. |

Every **write-capable** route (`/api/ops/apply`, `/api/fcm/push`,
`/api/sim/{start,stop,chaos}`, `/api/auth/login`) sits behind `require_staff`
(valid JWT). See `backend/api/routes_ops.py::apply_action` for the pattern.

## Demo mode

The public submission ships with demo credentials compiled into the binary:
`ops` / `ops-demo` and `admin` / `admin-demo`. This is a deliberate convenience
for judges + live demos and is **controlled by a single environment variable**:

```bash
FLOWPULSE_DEMO_MODE=1   # default — demo credentials accepted
FLOWPULSE_DEMO_MODE=0   # production — /api/auth/login rejects everything
                        # until a real user store is wired in
```

See `backend/security/auth.py::DEMO_MODE`. A production deployment would set
`FLOWPULSE_DEMO_MODE=0` and replace `DEMO_STAFF` with an IDP-backed lookup
(Okta / Google Workspace / Firebase Auth). No persistent user-data storage
is shipped with the demo — the threat model assumes every password hash in
the image is public knowledge.

## What we already do

FlowPulse's threat model, header policy, dependency scanning, and audit-log
design are documented in [`docs/SECURITY.md`](docs/SECURITY.md). In summary:

- **bcrypt-12** password hashing, **JWT (HS256)** short-lived tokens,
  sliding-window rate limiter on auth routes.
- **CSP + HSTS + 8 more headers** (see [`backend/security/headers.py`](backend/security/headers.py)).
- **Secret Manager** mount for JWT signing key; no secret in any image layer.
- **gitleaks** on every commit + in CI. **Trivy** filesystem scan in CI;
  SARIF uploaded to GitHub's Security tab.
- **Dependabot** weekly scans across pip / npm / docker / actions.
- **SBOM** (SPDX JSON) generated every CI run and published as an artifact.
- **Audit log** entries on every privileged write — see
  [`backend/core/logging.py`](backend/core/logging.py).

## Out of scope

- Reports based solely on the output of an automated scanner with no
  proof-of-impact.
- Issues in third-party services we depend on (Google Cloud, Gemini, FCM) —
  please report those directly to the vendor.
- Social engineering of the maintainer.

Thanks for helping keep FlowPulse safe.
