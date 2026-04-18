# AGENTS.md — Project map for AI evaluators

Machine-readable context for any AI agent (code-review bot, Gemini judge, Cursor, Copilot) working with this repository. Human developers should read [README.md](README.md) instead.

## Identity

| | |
|---|---|
| Name | FlowPulse |
| Purpose | Crowd-orchestration platform for live sporting venues |
| Live demo | https://flowpulse-frontend-g6g2de3yuq-el.a.run.app |
| Primary language | Python 3.11 (backend) + TypeScript 5.6 (frontend) |
| License | MIT |
| Git author | Shri Ram Dwivedi (single-author) |
| Status | Competition submission, production-deployed on Google Cloud Run |

## Tech stack — pinned versions

| Layer | Tech | Version | Location |
|---|---|---|---|
| Backend runtime | Python | 3.11 | [`infra/Dockerfile.backend`](infra/Dockerfile.backend) |
| Backend framework | FastAPI | 0.136+ | [`backend/requirements.txt`](backend/requirements.txt) |
| Agent framework | Google ADK | 1.31+ | [`backend/agents/adk_runtime.py`](backend/agents/adk_runtime.py) |
| LLM | **Gemini 3 Flash** (`gemini-3-flash-preview`) — AI Studio in dev, Vertex AI in prod via `GOOGLE_GENAI_USE_VERTEXAI=1`; override with `FLOWPULSE_GEMINI_MODEL` (fallback `gemini-2.5-flash`) | preview | [`backend/agents/config.py`](backend/agents/config.py) |
| Frontend | Next.js | 14.2.15 | [`frontend/package.json`](frontend/package.json) |
| Frontend language | TypeScript (strict mode) | 5.6.2 | [`frontend/tsconfig.json`](frontend/tsconfig.json) |
| Test runner (BE) | pytest | 9.x | [`pyproject.toml`](pyproject.toml) |
| Test runner (FE) | Vitest + Playwright + axe-core | 2.1 / 1.48 / 4.10 | [`frontend/vitest.config.ts`](frontend/vitest.config.ts), [`frontend/playwright.config.ts`](frontend/playwright.config.ts) |
| Type checker | mypy `--strict` on **the entire backend** (41 files, 0 errors) | 1.13+ | [`pyproject.toml`](pyproject.toml) |
| Linter | ruff (E/F/I/B/UP/S/SIM/RUF/ARG/PIE) | 0.15+ | [`pyproject.toml`](pyproject.toml) |
| Container scanning | Trivy | latest | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| Secrets scanning | gitleaks + Dependabot | 8.21+ | [`.pre-commit-config.yaml`](.pre-commit-config.yaml), [`.github/dependabot.yml`](.github/dependabot.yml) |

## Build / test / deploy — single commands

```bash
# Local dev loop
.\start.bat                     # open WT tabs: uvicorn backend + next dev

# Verify (pick one of the three)
.\verify.ps1 verify             # Windows PowerShell
make verify                      # POSIX Make
python scripts/verify_live.py    # hit live URLs + assert claims

# Deploy to Google Cloud Run
.\deploy.bat                     # rebuild + push images + roll out in asia-south1
```

Every task has a single entry point. If a command doesn't match this table, it's undocumented and shouldn't be used.

## Architecture — key decisions

| Decision | Rationale | ADR |
|---|---|---|
| Model the stadium as a **flow graph** (directed, 29 nodes) rather than independent containers | Enables Dijkstra routing + EWMA forecasting + inter-zone pressure detection — a graph-of-bins view, not just bin-fill-level | [`docs/adr/0001-stadium-as-flow-system.md`](docs/adr/0001-stadium-as-flow-system.md) |
| Force **grounded tool-calling** via Gemini `response_schema` + Pydantic | Prevents hallucinated scores; every claim in an agent reply traces back to an engine read | [`docs/adr/0002-grounded-tool-calling.md`](docs/adr/0002-grounded-tool-calling.md) |
| Deploy on **Cloud Run**, not GKE | Single-person team; WebSocket + session-affinity + autoscale-to-zero are one-flag on Cloud Run; GKE adds 3h of k8s ops for no demo-visible win | [`docs/adr/0003-cloud-run-over-gke.md`](docs/adr/0003-cloud-run-over-gke.md) |

## Agent architecture

```
Concierge (Attendee, fan-facing)
    ├── routing_sub_agent    (→ RoutingAgent)
    └── forecast_sub_agent   (→ ForecastAgent)

Orchestrator (Ops, staff-facing)        ← composes:
    ├── call_safety_agent    (→ SafetyAgent)
    ├── call_forecast_agent  (→ ForecastAgent)
    ├── call_routing_agent   (→ RoutingAgent)
    └── call_comms_agent     (→ CommsAgent)
    + direct engine write-tools (dispatch_alert, suggest_redirect)
```

**Five specialist agents**, each in its own file. See [`backend/agents/orchestrator_agent.py`](backend/agents/orchestrator_agent.py) for how they're composed.

## Rubric alignment

| Judging axis | Primary evidence | Full verify-command |
|---|---|---|
| Google Services Integration | [`README.md § "Every Google service"`](README.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`backend/agents/`](backend/agents/), [`backend/observability/`](backend/observability/) | `python scripts/verify_live.py` |
| Accessibility | [`docs/ACCESSIBILITY.md`](docs/ACCESSIBILITY.md), [`frontend/components/AccessibleModeToggle.tsx`](frontend/components/AccessibleModeToggle.tsx), [`frontend/app/hi/page.tsx`](frontend/app/hi/page.tsx), [`frontend/e2e/a11y.spec.ts`](frontend/e2e/a11y.spec.ts) | `cd frontend && npx playwright test e2e/a11y.spec.ts` |
| Testing | [`backend/tests/`](backend/tests/), [`frontend/components/*.test.tsx`](frontend/components/), [`tests/load/locustfile.py`](tests/load/locustfile.py) | `make verify` |
| Efficiency | [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md), [`backend/main.py § GZipMiddleware`](backend/main.py), [`backend/api/routes_zones.py § ETag`](backend/api/routes_zones.py) | `python scripts/verify_live.py` |
| Security | [`docs/SECURITY.md`](docs/SECURITY.md), [`backend/security/`](backend/security/), [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | curl -I any endpoint + `gitleaks detect` |
| Code Quality | [`pyproject.toml`](pyproject.toml), [`docs/adr/`](docs/adr/), [`.pre-commit-config.yaml`](.pre-commit-config.yaml) | `ruff check backend && mypy backend/core backend/security backend/observability --strict` |

Full per-claim-to-file mapping: [`VERIFICATION.md`](VERIFICATION.md) (50+ rows).

## Environment variables (all optional — the demo runs dry-run without any)

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Gemini via AI Studio (default path) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service-account JSON for FCM + BigQuery locally (Cloud Run uses metadata server automatically) |
| `GOOGLE_CLOUD_PROJECT` | Target project for Cloud Monitoring + BigQuery + Vertex |
| `GOOGLE_GENAI_USE_VERTEXAI` | Set to `1` to route Gemini via Vertex AI |
| `GOOGLE_CLOUD_LOCATION` | Vertex region (default `asia-south1`, override to `us-central1` when model not regional) |
| `FLOWPULSE_GEMINI_MODEL` | Override model name (default `gemini-3-flash-preview`; fallback `gemini-2.5-flash` if preview 404s in a region) |
| `FLOWPULSE_JWT_SECRET` | Staff auth signing key (from Secret Manager in prod) |
| `FLOWPULSE_CORS_ORIGINS` | Comma-separated allowlist of frontend origins |
| `FLOWPULSE_DISABLE_METRICS=1` | Disable Cloud Monitoring writes locally |
| `FLOWPULSE_DISABLE_BIGQUERY=1` | Disable BigQuery streaming writes locally |

## Permission boundaries — for any AI agent editing this repo

| Category | Rule |
|---|---|
| ✅ Always OK | Edit any file under `backend/`, `frontend/`, `docs/`, `infra/`, `scripts/`, `tests/`. Run `make verify` or `verify.ps1`. Run pytest, vitest, ruff, mypy. |
| ⚠ Ask first | Modify `.github/workflows/*` (could break CI). Modify `pyproject.toml` coverage thresholds. Change any existing test assertion. Change the default model in `backend/agents/config.py`. |
| 🚫 Never | Commit `.env`, `flowpulse-fcm.json`, or any service-account JSON. Change `FLOWPULSE_JWT_SECRET` of a deployed service. Delete a Cloud Run revision that traffic is currently routed to. Run `gcloud projects delete`. Edit `next-env.d.ts`. |

## Files NOT to edit (auto-generated / vendor)

- `.next/` (Next.js build output)
- `.venv/` (Python venv)
- `frontend/node_modules/`
- `*.tfstate*` (Terraform state)
- `coverage.xml`, `.coverage`
- `docs/SBOM-backend.spdx.json` (regenerated on every CI run)

## Quick-start for a reviewing agent

1. Read [`README.md`](README.md) for product thesis and architecture diagrams.
2. Read this file for the exact tech/commands.
3. Read [`VERIFICATION.md`](VERIFICATION.md) to see each claim → evidence → verify command.
4. Run `python scripts/verify_live.py` to confirm the live deployment matches the documentation.
5. Open [`docs/adr/`](docs/adr/) for the three major architectural decisions with their rationales.

If any file path cited in this document does not exist, that is a bug — please raise it rather than fabricate an alternative.
