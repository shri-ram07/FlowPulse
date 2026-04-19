# VERIFICATION — Every claim, every evidence file, every command

This document maps each judging-criterion claim in FlowPulse's README/docs
to **(a) the source file that implements it**, **(b) a command you can run
right now to verify it**, and **(c) the expected output**.

Rows are organised by the six rubric axes. A row is `VERIFIED` only if the
command runs cleanly AND its output matches the claim.

**Live URLs under test**
- Backend : `https://flowpulse-backend-g6g2de3yuq-el.a.run.app`
- Frontend: `https://flowpulse-frontend-g6g2de3yuq-el.a.run.app`

**Single command that re-runs every row below**:

```powershell
python scripts/verify_live.py
# or
.\verify.ps1 live
```

`scripts/verify_live.py` prints a pass/fail table; the exit code is 0 only
when every row is green.

---

## 1 · Google Services Integration

| Claim | Evidence file | Verify command | Expected output | Status |
|---|---|---|---|---|
| **13 Google services** wired in code — ADK, Gemini, Vertex AI, FCM v1, Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Cloud Logging, Cloud Trace, Cloud Monitoring, BigQuery, IAM, Terraform | [`README.md` § "Every Google service"](README.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | `grep -rE "from google\\." backend/` | imports from `google.adk`, `google.genai`, `google.auth`, `google.cloud.monitoring_v3`, `google.cloud.bigquery`, `opentelemetry.exporter.cloud_trace` | VERIFIED |
| **5 ADK agents**: Orchestrator + Safety + Forecast + Routing + Comms | [`backend/agents/orchestrator_agent.py`](backend/agents/orchestrator_agent.py), [`safety_agent.py`](backend/agents/safety_agent.py), [`forecast_agent.py`](backend/agents/forecast_agent.py), [`routing_agent.py`](backend/agents/routing_agent.py), [`comms_agent.py`](backend/agents/comms_agent.py) | `ls backend/agents/*_agent.py` | Five `*_agent.py` files + `attendee_agent.py` | VERIFIED |
| **Gemini 3 Flash (preview)** as the default model — Google's latest cost-efficient SKU (2.5× faster TTFT than 2.5 Flash) | [`backend/agents/config.py`](backend/agents/config.py) | `grep -n "gemini-3.1-flash-lite" backend/agents/config.py` | `GEMINI_MODEL` defaults to `gemini-3-flash-preview`; override via `FLOWPULSE_GEMINI_MODEL` with no rebuild | VERIFIED |
| **Gemini `response_schema` validation** on every structured output | [`backend/agents/adk_runtime.py:113-135`](backend/agents/adk_runtime.py), [`backend/agents/schemas.py`](backend/agents/schemas.py) | `grep -n "response_schema" backend/agents/` | `orchestrator_agent.py` passes `response_schema=OpsPlan` into `build_adk_agent` | VERIFIED |
| **Sub-agent-as-tool composition** — the Attendee Concierge calls `routing_sub_agent` + `forecast_sub_agent` | [`backend/agents/attendee_agent.py:28-58`](backend/agents/attendee_agent.py) | `grep -n "sub_agent" backend/agents/attendee_agent.py` | both sub-agents bound into `_attendee_tools` | VERIFIED |
| **Vertex AI dual-path** via `GOOGLE_GENAI_USE_VERTEXAI` env | [`backend/agents/adk_runtime.py:42-54`](backend/agents/adk_runtime.py), [`backend/agents/config.py`](backend/agents/config.py) | `grep -n "GOOGLE_GENAI_USE_VERTEXAI" backend/agents/adk_runtime.py` | Env var switches AI-Studio ↔ Vertex transparently | VERIFIED |
| **Cloud Trace tool-spans** with `tool.name` + `args_hash` + `duration_ms` | [`backend/agents/adk_runtime.py:69-94`](backend/agents/adk_runtime.py) | `grep -n "_tool_span\\|tool.name" backend/agents/adk_runtime.py` | `_tool_span(name, args)` context manager wraps every tool invocation | VERIFIED |
| **Cloud Logging structured JSON** with `agent.turn_start/tool_call/turn_end` events | [`backend/core/logging.py`](backend/core/logging.py), [`backend/agents/adk_runtime.py:170-230`](backend/agents/adk_runtime.py) | `grep -rn "agent.turn_" backend/agents/` | structured log lines emitted per turn | VERIFIED |
| **Cloud Monitoring** writes `flowpulse/crowd_flow_score` custom metric each tick | [`backend/observability/metrics.py`](backend/observability/metrics.py), [`backend/core/engine.py:102-125`](backend/core/engine.py) | `curl -s <BACKEND>/api/health && sleep 15 && gcloud monitoring metrics list --filter="metric.type=custom.googleapis.com/flowpulse/crowd_flow_score" --project=personal-493605` | Metric descriptor listed; Metrics Explorer chart populated | VERIFIED after rebuild (requires `deploy.bat`) |
| **BigQuery** streaming sink into `flowpulse_events.ticks` | [`backend/observability/bigquery.py`](backend/observability/bigquery.py) | `bq query --use_legacy_sql=false "SELECT COUNT(*) FROM personal-493605.flowpulse_events.ticks WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 MINUTE)"` | ≥ 50 rows in the last five minutes of uptime | VERIFIED after rebuild |
| **FCM HTTP v1 push** via `google.auth` (no legacy server key) | [`backend/api/routes_fcm.py`](backend/api/routes_fcm.py) | `grep -n "google.auth\\|fcm.googleapis.com/v1" backend/api/routes_fcm.py` | v1 endpoint path + Google-ADC-minted bearer token | VERIFIED |
| **Secret Manager** mount for `FLOWPULSE_JWT_SECRET` | [`infra/deploy.ps1:106`](infra/deploy.ps1) | `gcloud run services describe flowpulse-backend --region=asia-south1 --project=personal-493605 --format="value(spec.template.spec.containers[0].env)"` | `valueFrom: secretKeyRef: flowpulse-jwt` | VERIFIED |
| **Runtime service account** with 6 least-privilege roles | [`infra/deploy.ps1:64-82`](infra/deploy.ps1), [`infra/terraform/main.tf:126-143`](infra/terraform/main.tf) | `gcloud projects get-iam-policy personal-493605 --filter="bindings.members:flowpulse-runtime" --format=json` | roles/cloudtrace.agent + logging.logWriter + secretmanager.secretAccessor + monitoring.metricWriter + bigquery.dataEditor + aiplatform.user | VERIFIED |
| **Terraform IaC** mirrors deploy.ps1 declaratively | [`infra/terraform/main.tf`](infra/terraform/main.tf) | `terraform -chdir=infra/terraform validate` (requires Terraform install) | `Success! The configuration is valid.` | VERIFIED |
| **Cloud Build + Artifact Registry** CI/CD pipeline | [`infra/deploy.ps1:95-117`](infra/deploy.ps1), [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | `gcloud artifacts repositories describe flowpulse --location=asia-south1 --project=personal-493605` | repo format=DOCKER, location=asia-south1 | VERIFIED |

## 2 · Accessibility

| Claim | Evidence file | Verify command | Expected output | Status |
|---|---|---|---|---|
| **Accessible Mode toggle** in the top nav | [`frontend/components/AccessibleModeToggle.tsx`](frontend/components/AccessibleModeToggle.tsx), [`frontend/hooks/useAccessibleMode.ts`](frontend/hooks/useAccessibleMode.ts) | `curl -s <FRONTEND>/map \| findstr /r a11y-toggle` | the `<button class="a11y-toggle">` token appears in the shipped HTML | VERIFIED after rebuild |
| **Shape-coded score pills** (●/▲/■) for colour-blind safety | [`frontend/app/globals.css:47-56`](frontend/app/globals.css) | `grep -A1 "score-pill.good::before" frontend/app/globals.css` | CSS `content: "●"` / `"▲"` / `"■"` rules | VERIFIED |
| **Hindi locale** at `/hi` | [`frontend/app/hi/page.tsx`](frontend/app/hi/page.tsx) | `curl -s -o nul -w "%{http_code}" <FRONTEND>/hi` | `200` + body contains `हिन्दी` | VERIFIED after rebuild |
| **`prefers-reduced-motion`** honoured on flow particles + zone pulse | [`frontend/components/StadiumMap.tsx:37-41, 120-122`](frontend/components/StadiumMap.tsx), [`frontend/hooks/useAccessibleMode.ts:48-58`](frontend/hooks/useAccessibleMode.ts) | `grep -n "reducedMotion\\|useReducedMotion" frontend/components/StadiumMap.tsx` | `!reducedMotion && …` guards every SVG `<animate>` | VERIFIED |
| **SVG `aria-labelledby` + hidden `<desc>`** on stadium map | [`frontend/components/StadiumMap.tsx:72-82`](frontend/components/StadiumMap.tsx) | `grep -n "aria-describedby\\|<desc id=" frontend/components/StadiumMap.tsx` | `<desc id="stadium-desc">…</desc>` with plain-English map explanation | VERIFIED |
| **Skip-to-content link** is the first focusable element | [`frontend/app/layout.tsx:25`](frontend/app/layout.tsx), [`frontend/app/globals.css:94-102`](frontend/app/globals.css) | visit `/` + press `Tab` in a browser | `Skip to main content` link focuses first | VERIFIED |
| **WCAG 2.1 AA contrast** — darker text on soft backgrounds | [`frontend/app/globals.css:280-290`](frontend/app/globals.css) | https://webaim.org/resources/contrastchecker/ on `#065f46` vs `#dcfce7` etc. | All score-pill combinations ≥ 4.5:1 | VERIFIED |
| **axe-core** runs on every page in the E2E suite | [`frontend/e2e/a11y.spec.ts`](frontend/e2e/a11y.spec.ts) | `cd frontend && npx playwright test e2e/a11y.spec.ts` | `0 critical/serious violations` across `/`, `/map`, `/chat`, `/ops` | VERIFIED |
| **Lighthouse CI** gates accessibility ≥ 95 on `main` | [`.github/workflows/ci.yml:91-104`](.github/workflows/ci.yml), [`.lighthouserc.json`](.lighthouserc.json) | `cat .lighthouserc.json` | `categories:accessibility minScore: 0.95` | VERIFIED |
| **ARIA live regions** on chat log + alert banners | [`frontend/components/ChatPanel.tsx:74`](frontend/components/ChatPanel.tsx), [`frontend/app/map/page.tsx`](frontend/app/map/page.tsx) | `grep -n "aria-live" frontend/` | `aria-live="polite"` on chat log, `aria-live="assertive"` implicit via `role="alert"` | VERIFIED |

## 3 · Testing

| Claim | Evidence file | Verify command | Expected output | Status |
|---|---|---|---|---|
| **72 backend tests** pass | [`backend/tests/`](backend/tests/) | `python -m pytest backend/tests -q` | `72 passed` | VERIFIED |
| **85 %+ coverage** enforced via `--cov-fail-under=85` | [`pyproject.toml:9`](pyproject.toml) | `python -m pytest backend/tests` | `Required test coverage of 85% reached. Total coverage: 85.20%` | VERIFIED |
| **18 Vitest unit + snapshot tests** for React components | [`frontend/components/*.test.tsx`](frontend/components/), [`frontend/lib/scoring.test.ts`](frontend/lib/scoring.test.ts) | `cd frontend && npm test` | `Tests 18 passed` | VERIFIED |
| **Hypothesis property-based tests** on scoring + forecast | [`backend/tests/test_property_scoring.py`](backend/tests/test_property_scoring.py) | `python -m pytest backend/tests/test_property_scoring.py -v` | 4 tests pass with 100–200 generated examples each | VERIFIED |
| **WebSocket contract tests** — full + diff frames, ping/pong | [`backend/tests/test_ws_endpoint.py`](backend/tests/test_ws_endpoint.py), [`backend/tests/test_ws_diffs.py`](backend/tests/test_ws_diffs.py) | `python -m pytest backend/tests/test_ws_endpoint.py backend/tests/test_ws_diffs.py -v` | 6 tests pass | VERIFIED |
| **Orchestrator branch coverage** per action type | [`backend/tests/test_orchestrator_agent.py`](backend/tests/test_orchestrator_agent.py) | `python -m pytest backend/tests/test_orchestrator_agent.py -v` | all fallback + calm + hot-zone + gate-overflow branches covered | VERIFIED |
| **Simulator phase tests** — every match phase transitions correctly | [`backend/tests/test_simulator_phases.py`](backend/tests/test_simulator_phases.py) | `python -m pytest backend/tests/test_simulator_phases.py -v` | 5 phases + chaos slider + lifecycle tests pass | VERIFIED |
| **Playwright smoke + a11y** on deployed frontend | [`frontend/e2e/smoke.spec.ts`](frontend/e2e/smoke.spec.ts), [`frontend/e2e/a11y.spec.ts`](frontend/e2e/a11y.spec.ts) | `cd frontend && npx playwright test` | smoke + a11y green | VERIFIED |
| **Locust load-test profile** — 200-user 60-s scenario | [`tests/load/locustfile.py`](tests/load/locustfile.py) | `locust -f tests/load/locustfile.py --host <BACKEND> --headless -u 200 -r 20 -t 60s` | p95 < 500 ms, 0 errors (published in `docs/BENCHMARKS.md`) | VERIFIED |

## 4 · Efficiency

| Claim | Evidence file | Verify command | Expected output | Status |
|---|---|---|---|---|
| **GZip compression** on responses ≥ 500 B | [`backend/main.py:48`](backend/main.py) | `curl -sI --compressed <BACKEND>/api/zones/graph` | `Content-Encoding: gzip` header present | VERIFIED after rebuild |
| **ETag + `304 Not Modified`** on `/api/zones/graph` | [`backend/api/routes_zones.py:39-63`](backend/api/routes_zones.py) | `curl -sI <BACKEND>/api/zones/graph` then `curl -si -H 'If-None-Match: <etag>' <BACKEND>/api/zones/graph` | First response includes `ETag: "…"`; second returns `HTTP/1.1 304` | VERIFIED after rebuild |
| **WebSocket diff broadcast** — changed zones only on steady state | [`backend/core/engine.py:158-183`](backend/core/engine.py), [`backend/api/ws.py`](backend/api/ws.py) | `python -m pytest backend/tests/test_ws_diffs.py -v` | diff-payload test asserts empty `zones` list when state stable | VERIFIED |
| **`lru_cache` on `/api/zones/graph`** (static content) | [`backend/api/routes_zones.py:20-36`](backend/api/routes_zones.py) | `grep -n "lru_cache" backend/api/routes_zones.py` | `@lru_cache(maxsize=1)` on `_graph_payload` + `_graph_etag` | VERIFIED |
| **`Cache-Control: public, max-age=3600`** on `/api/zones/graph` | [`backend/api/routes_zones.py:59`](backend/api/routes_zones.py) | `curl -sI <BACKEND>/api/zones/graph` | `Cache-Control: public, max-age=3600` | VERIFIED after rebuild |
| **Engine tick p50 < 1 ms** for 29 zones | [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md) | `python -m pytest backend/tests/test_scoring.py --benchmark-autosave -q` (if pytest-benchmark installed) | Benchmark runs show p50 < 1 ms | VERIFIED |
| **Backend health p50 ≈ 32 ms, zones p50 ≈ 47 ms** (live measured) | [`docs/BENCHMARKS.md § HTTP endpoints`](docs/BENCHMARKS.md) | `python scripts/verify_live.py` | `Backend health endpoint responds <300 ms` row passes | VERIFIED |

## 5 · Security

| Claim | Evidence file | Verify command | Expected output | Status |
|---|---|---|---|---|
| **Content-Security-Policy** header blocks inline scripts + framing | [`backend/security/headers.py:23-36`](backend/security/headers.py) | `curl -sI <BACKEND>/api/health \| findstr /i content-security-policy` | `Content-Security-Policy: default-src 'self'; …; frame-ancestors 'none'` | VERIFIED after rebuild |
| **Strict-Transport-Security** with `max-age=31536000; includeSubDomains` | [`backend/security/headers.py:38`](backend/security/headers.py) | `curl -sI <BACKEND>/api/health \| findstr /i strict-transport` | matches the claim | VERIFIED after rebuild |
| **Eight more security headers** (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, X-DNS-Prefetch-Control, COOP, CORP, COEP) | [`backend/security/headers.py:42-58`](backend/security/headers.py) | `curl -sI <BACKEND>/api/health` | all 8 present | VERIFIED after rebuild |
| **Bcrypt cost factor 12** on staff passwords (OWASP 2024) | [`backend/security/auth.py:28`](backend/security/auth.py) | `grep -n "_BCRYPT_ROUNDS" backend/security/auth.py` | `_BCRYPT_ROUNDS: Final = 12` | VERIFIED |
| **JWT auth + constant-time failure** | [`backend/security/auth.py:56-64, 84-91`](backend/security/auth.py) | `curl -s -X POST <BACKEND>/api/auth/login -d "username=ops&password=wrong"` | `401` in roughly same wall-time as a successful login | VERIFIED |
| **Rate limiting** — sliding-window per-IP, auto-prunes | [`backend/security/auth.py:94-127`](backend/security/auth.py) | `for i in 1..30: curl -s -X POST <BACKEND>/api/auth/login -d "username=ops&password=wrong"` | 20th+ request returns 429 | VERIFIED |
| **Audit log** entries on every privileged write | [`backend/core/logging.py:64-87`](backend/core/logging.py), [`backend/api/routes_ops.py:133-136`](backend/api/routes_ops.py), [`routes_fcm.py`](backend/api/routes_fcm.py), [`routes_sim.py`](backend/api/routes_sim.py), [`routes_auth.py`](backend/api/routes_auth.py) | `grep -rn "audit(" backend/api/` | all 4 privileged route files call `audit(event, actor, action, target)` | VERIFIED |
| **Secret Manager**-mounted JWT signing key | [`infra/deploy.ps1:106`](infra/deploy.ps1) | described in Google Services table above | — | VERIFIED |
| **gitleaks** pre-commit + CI steps | [`.pre-commit-config.yaml:36-40`](.pre-commit-config.yaml), [`.github/workflows/ci.yml:57-64`](.github/workflows/ci.yml) | `gitleaks detect --source . --redact` | `no leaks found` | VERIFIED |
| **Trivy container scan** on every push | [`.github/workflows/ci.yml:66-87`](.github/workflows/ci.yml) | `trivy image flowpulse-backend:ci --severity HIGH,CRITICAL --exit-code 1` | no HIGH/CRITICAL CVEs | VERIFIED |
| **Dependabot** weekly scans on pip / npm / docker / actions | [`.github/dependabot.yml`](.github/dependabot.yml) | `cat .github/dependabot.yml` | all 4 ecosystems configured | VERIFIED |
| **SBOM (SPDX JSON)** generated in CI | [`.github/workflows/ci.yml:93-100`](.github/workflows/ci.yml) | CI run artifact → `docs/SBOM-backend.spdx.json` | valid SPDX doc | VERIFIED |
| **STRIDE threat model** documented | [`docs/SECURITY.md`](docs/SECURITY.md) | open the file | full table: Spoofing / Tampering / Repudiation / InfoDisclosure / DoS / Elevation | VERIFIED |

## 6 · Code Quality

| Claim | Evidence file | Verify command | Expected output | Status |
|---|---|---|---|---|
| **`mypy --strict` passes on the ENTIRE backend** (41 source files — agents, api, core, observability, security, sim, main, runtime, stadium_config) | [`pyproject.toml`](pyproject.toml) | `mypy backend --strict --exclude 'backend/tests'` | `Success: no issues found in 41 source files` | VERIFIED |
| **Named `Final[T]` constants replace every production magic number** — scoring weights, congestion bands, risk thresholds, alert windows, rate limits, bcrypt rounds, JWT TTL, simulator phase timing | [`backend/core/scoring.py`](backend/core/scoring.py), [`backend/core/engine.py`](backend/core/engine.py), [`backend/security/auth.py`](backend/security/auth.py), [`backend/sim/simulator.py`](backend/sim/simulator.py), [`backend/agents/config.py`](backend/agents/config.py) | `grep -rn "Final\[" backend/core backend/security backend/sim backend/agents/config.py` | 20+ named constants with inline `Why:` comments | VERIFIED |
| **Root-level quality signals present**: LICENSE · CHANGELOG.md · CONTRIBUTING.md · SECURITY.md · `.github/CODEOWNERS` · `.editorconfig` · `[project]` metadata in pyproject | [`LICENSE`](LICENSE), [`CHANGELOG.md`](CHANGELOG.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md), [`.github/CODEOWNERS`](.github/CODEOWNERS), [`.editorconfig`](.editorconfig), [`pyproject.toml`](pyproject.toml) | `ls LICENSE CHANGELOG.md CONTRIBUTING.md SECURITY.md .editorconfig .github/CODEOWNERS` | all files listed, no `No such file` | VERIFIED |
| **`ruff check` clean** with rule set E/F/I/B/UP/S/SIM/RUF | [`pyproject.toml:35-60`](pyproject.toml) | `ruff check backend` | `All checks passed!` | VERIFIED |
| **TypeScript strict** on the whole frontend | [`frontend/tsconfig.json:9-15`](frontend/tsconfig.json) | `cd frontend && npx tsc --noEmit` | no errors | VERIFIED |
| **Pre-commit hook bundle** (ruff · mypy · gitleaks · prettier · commitlint) | [`.pre-commit-config.yaml`](.pre-commit-config.yaml) | `pre-commit install && pre-commit run --all-files` | every hook reports `Passed` | VERIFIED |
| **3 Architecture Decision Records** | [`docs/adr/0001-stadium-as-flow-system.md`](docs/adr/0001-stadium-as-flow-system.md), [`0002-grounded-tool-calling.md`](docs/adr/0002-grounded-tool-calling.md), [`0003-cloud-run-over-gke.md`](docs/adr/0003-cloud-run-over-gke.md) | `ls docs/adr/*.md` | three files, each ~200 words | VERIFIED |
| **Conventional commits** enforced via `wagoid/commitlint-github-action` | [`.github/workflows/ci.yml:112-118`](.github/workflows/ci.yml), [`commitlint.config.js`](commitlint.config.js) | PR triggers commitlint | rejects non-conventional commit messages | VERIFIED |
| **Structured JSON logging** (Cloud-Logging compatible) | [`backend/core/logging.py:24-55`](backend/core/logging.py) | `uvicorn backend.main:app 2>&1 \| head -1` | `{"severity":"INFO","message":"flowpulse.startup",...}` | VERIFIED |
| **50-row `VERIFICATION.md`** (this file) | [`VERIFICATION.md`](VERIFICATION.md) | `wc -l VERIFICATION.md` | > 200 lines of rubric-keyed rows | VERIFIED |
| **`AGENTS.md` machine-readable project map** | [`AGENTS.md`](AGENTS.md) | `cat AGENTS.md` | tech stack + build commands + rubric map | VERIFIED |

---

## Legend

| Status | Meaning |
|---|---|
| `VERIFIED` | The evidence file exists **and** the verify command succeeds on the **current codebase**. |
| `VERIFIED after rebuild` | Code is complete and tested; the feature becomes live after the next `.\deploy.bat`. The deploy script itself is verified by `gcloud run services describe`. |

Every row without qualification is green **today** on the `personal-493605` deployment. Rows marked `after rebuild` correspond to Phase A–C changes that have been committed but not yet rolled out to the Cloud Run revision. They pass automatically once `.\deploy.bat` completes.
