# Changelog

All notable changes to OptimFlow are documented here. This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) and the format of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.2.0] — 2026-04-18

### Fixed
- **Orchestrator ADK path was silently disabled** — Gemini 3 Flash preview rejects
  `response_schema` + function-calling tools at Runner construction. `build_adk_agent`
  was catching the exception, returning `None`, and every `/api/agent/operations`
  call served the deterministic fallback with empty `tool_calls`. Reconfigured:
  * Dropped `response_schema=OpsPlan` from the orchestrator's Runner.
  * Strengthened `ORCHESTRATOR_SYS_PROMPT` with mandatory STEP 1-6 tool-call
    procedure + the exact JSON shape to emit at STEP 6.
  * Restored flexible `_coerce_plan` — tries strict parse first, then extracts
    the first `{...}` block from prose/code-fenced replies, then falls back to
    a zero-confidence monitor plan. Live verified: `engine=google-adk` with
    `tool_calls=['call_safety_agent','get_all_zones','call_forecast_agent',...]`.

### Changed
- **Model default** is now `gemini-3-flash-preview` (GA trade-off moved to ADR 0005).
  `gemini-2.5-flash` is the documented one-command fallback when the preview
  SKU's quota tightens (no rebuild needed).
- `infra/deploy.ps1` pins `OPTIMFLOW_GEMINI_MODEL=gemini-3-flash-preview`
  on every rollout so the Cloud Run revision is explicit about its model.
- Rewrote ADR 0005 with the live-observed model trade-off table.

## [1.1.0] — 2026-04-17

### Added
- **Gemini 3 Flash (preview)** as the default model (2.5× faster TTFT, 45% faster output
  vs. 2.5 Flash). Overridable via `OPTIMFLOW_GEMINI_MODEL`.
- Whole-backend `mypy --strict` coverage (`agents/`, `api/`, `sim/`, `main.py`, `runtime.py`,
  `stadium_config.py` — previously only `core`, `security`, `observability`).
- Named `Final[T]` constants for every scoring, engine, simulator, auth, and forecast threshold
  (previously inline magic numbers).
- Root-level quality files: `LICENSE` (MIT), `CONTRIBUTING.md`, `.github/CODEOWNERS`, `.editorconfig`.
- `[project]` metadata block in `pyproject.toml` (name, version, authors, license, python version).
- Docstrings on every public route handler + `Simulator` method + Pydantic `Field(description=...)`.
- Extracted `_plan_redirect` helper from `orchestrator_agent._deterministic_plan` (103-line function
  reduced to ~65 lines).
- Ruff rule categories `ARG` + `PIE` (catch dead params + pep-8 micro-issues).
- Frontend `tsconfig` flags `noUnusedLocals` + `noUnusedParameters`.

### Changed
- Three bare `except Exception` handlers replaced with logged catches
  (orchestrator, tracing, adk_runtime).
- JWT secret fallback now emits `auth.jwt_secret_missing_in_prod` when running on Cloud Run without
  a mounted Secret Manager secret.
- `operations_agent.py` carries an explicit `DEPRECATED` banner clarifying the 5-agent count.
- Security headers extended to **10** (X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
  Permissions-Policy, X-DNS-Prefetch-Control, HSTS, CSP, COOP, CORP, COEP).

### Removed
- Unused `useEffect` import from `Toast.tsx`.
- Unused `unit` parameter from `metrics.make_series`.
- Unused `monkeypatch` fixture from `test_attendee_session`.

### Infrastructure
- `infra/deploy.ps1` pins `OPTIMFLOW_GEMINI_MODEL` per deploy — one-liner `gcloud run services
  update` reverts the model without a rebuild.

## [1.0.0] — 2026-04-15

Initial submission — multi-agent ADK pipeline, live Cloud Run deployment, observability stack,
accessibility mode, Hindi locale, end-to-end verification harness.

### Added
- 5-agent Google ADK architecture: Orchestrator + Safety + Forecast + Routing + Comms.
- Attendee Concierge agent composing Routing + Forecast as sub-tools.
- Crowd Flow Engine (`backend/core/engine.py`) with EWMA flow smoothing + tick-level diffs.
- FastAPI gateway with WebSocket diff broadcast + REST routes.
- Next.js 14 PWA (Welcome / Map / Chat / Ops / `/hi` Hindi locale).
- Cloud Run deployment (`asia-south1`), Cloud Build + Artifact Registry + Secret Manager.
- Observability: Cloud Logging (structured JSON), Cloud Trace (per-tool spans),
  Cloud Monitoring (`optimflow/crowd_flow_score` custom metric), BigQuery
  (`optimflow_events.ticks` streaming sink).
- Firebase Cloud Messaging v1 with OAuth-minted bearer tokens.
- Security: bcrypt-12 + JWT, CSP/HSTS/COOP/CORP headers, sliding-window rate limiting,
  structured audit log on every privileged write.
- Testing: 72 backend pytest tests (Hypothesis property tests + WebSocket contract tests),
  18 frontend Vitest tests, Playwright + axe-core e2e, Locust load profile.
- Terraform IaC spec mirroring the imperative `deploy.ps1`.

[1.1.0]: https://github.com/Ananya419/OptimFlow/releases/tag/v1.1.0
[1.0.0]: https://github.com/Ananya419/OptimFlow/releases/tag/v1.0.0
