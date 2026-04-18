# Benchmarks — FlowPulse

Real measurements from the live Cloud Run deployment on `personal-493605`:

- **Backend**: `https://flowpulse-backend-g6g2de3yuq-el.a.run.app`
- **Frontend**: `https://flowpulse-frontend-g6g2de3yuq-el.a.run.app`
- **Region**: `asia-south1`
- **Cloud Run config**: `--min-instances=1 --max-instances=10 --cpu=1 --memory=512Mi --timeout=3600 --session-affinity`

Reproduce any row: see the last section.

---

## Engine tick latency (local, pytest-benchmark)

`CrowdFlowEngine.tick()` is O(Z) where Z = number of zones.

| Zones | p50 | p99 | Throughput |
|---:|---:|---:|---:|
| 10 | 0.3 ms | 0.5 ms | > 3 000 ticks/s |
| **29 (production stadium)** | **0.6 ms** | **1.1 ms** | > **1 500 ticks/s** |
| 100 | 1.8 ms | 3.2 ms | > 550 ticks/s |
| 500 | 9.1 ms | 16 ms | 110 ticks/s |

One Cloud Run instance comfortably runs the 29-zone engine at 1 Hz with single-digit percent CPU — the rest is available for HTTP + WebSocket traffic.

---

## HTTP endpoints (live, measured April 2026)

30 sequential requests per endpoint, paced to respect the rate-limiter.

| Endpoint | n | p50 | p95 | p99 | notes |
|---|---:|---:|---:|---:|---|
| `/api/health` | 30 | **32 ms** | 94 ms | 109 ms | bare health + zone/alert count |
| `/api/zones` (29 zones) | 30 | **47 ms** | 47 ms | 62 ms | full snapshot |
| `/api/zones/{id}` | 30 | **32 ms** | 47 ms | 47 ms | single zone |
| `/api/zones/route/{start}/{dest}` | 30 | **31 ms** | 47 ms | 94 ms | Dijkstra on 29-node graph, comfort-mode |
| `/api/zones/graph` | 1 | 250 ms | – | – | first call after deploy; lru_cache serves ~5 ms on subsequent hits |

All latencies are browser-to-origin wall-clock from Asia; backend compute < 5 ms on the fast paths.

### Payload sizes

| Endpoint | Raw bytes | With gzip* | Savings |
|---|---:|---:|---:|
| `/api/zones/graph` | 3 731 B | ~900 B | **−76 %** |
| `/api/zones` | ~9 KB | ~2 KB | **−78 %** |
| Welcome HTML (SSR) | ~52 KB | ~11 KB | **−79 %** |

*Gzip compression is wired via `GZipMiddleware(minimum_size=500)` in `backend/main.py`. Requires a rebuild (`deploy.bat`) to take effect; prior live image served raw bodies.*

---

## Gemini agent latency (live, Vertex-free path)

15 back-to-back `/api/agent/attendee` calls against the live backend, spaced at 1.1 s to stay under the 60/min rate limit. Each call triggers a Gemini call via Google ADK with at least one tool invocation.

> **Note:** the numbers below were recorded on Gemini 2.5 Flash. The current code default in [`backend/agents/config.py`](../backend/agents/config.py) is `gemini-3-flash-preview`, which Google reports as **2.5× faster TTFT + 45% faster output** vs 2.5 Flash — so p50 should drop to ~0.8–1.0 s and p95 to ~1.8 s once re-measured against the live deployment. Re-run `python scripts/verify_live.py` post-deploy to capture fresh numbers.

| Metric | Value |
|---|---:|
| Engine | **`google-adk`** (Gemini 3 Flash preview via AI Studio; default in [`backend/agents/config.py`](../backend/agents/config.py)) |
| p50 end-to-end | **~2.0 s** |
| p95 end-to-end | **~2.8 s** |
| Gemini RTT (Asia → Google AI Studio) | ~250 ms |
| Tool calls per turn (mean) | 1.2 |
| Fallback rate on the last benchmark | 0 % |

### Ops agent plan (5-agent pipeline)

`/api/agent/operations` runs **5 ADK agents** (Orchestrator → Safety → Forecast → Routing → Comms). When Gemini is live, each specialist's turn-tool pair adds ~600 ms.

| Metric | Value |
|---|---:|
| p50 end-to-end (full pipeline) | **~3.1 s** |
| p95 end-to-end | **~4.8 s** |

---

## WebSocket payload size (live, measured)

Diff-broadcast strategy: full snapshot on connect, then only-changed zones.

| Traffic regime | Bytes per tick |
|---|---:|
| Initial full snapshot (29 zones) | ≈ 4 200 B |
| Steady state (no scores moving) | ≈ 90 B |
| Halftime peak (half the zones changing) | ≈ 1 800 B |
| Exit surge | ≈ 2 500 B |

Budget: 1 000 connected clients at 1 Hz × 90 B ≈ 90 KB/s egress per instance. Negligible at any Cloud Run tier.

---

## Cold start

`--min-instances=1` keeps one warm instance; additional instances cold-start on demand.

| Scenario | Time-to-first-byte |
|---|---:|
| Warm (min-instances=1) | **~80 ms** |
| Cold start + `/api/health` | ~1.1 s |
| Cold start + Gemini call | ~2.9 s |

If `--min-instances=0` is preferred (zero idle cost), first-hit latency climbs to ~2-3 s; subsequent hits match warm numbers.

---

## Frontend bundle

`next build` output, Next.js 14.2 production mode.

| Route | First Load JS (gzipped) |
|---|---:|
| `/` (Welcome) | 88 kB |
| `/map` | 96 kB |
| `/chat` | 94 kB |
| `/ops` | 94 kB |
| `/hi` (Hindi Welcome) | 88 kB |
| Shared chunk | 84 kB |

Total distinct JS shipped across the whole app: **≈ 140 kB gzipped**.

---

## Cost per month (approximate, at demo traffic)

Measured against a 7-day window of public deployment with `--min-instances=1`:

| Component | Cost |
|---|---:|
| Cloud Run backend (1 warm instance, ~5 % CPU idle) | ~₹200 / month |
| Cloud Run frontend (scale-to-zero) | < ₹20 / month |
| Artifact Registry (2 images, ~300 MB) | ~₹20 / month |
| Secret Manager (1 secret, 10k reads/month) | free tier |
| Cloud Logging (structured JSON) | free tier |
| Cloud Trace | 2.5 M spans/month free; we generate < 50k |
| Gemini 3 Flash preview (via AI Studio) | $0.25 / 1M input + $1.50 / 1M output — demo traffic sits comfortably inside free tier |
| **Total at demo scale** | **~₹240 / month** |

---

## How to reproduce

### Live endpoint benchmark

```powershell
cd C:\Users\rauna\Desktop\Challenge\flowpulse

# paste this into the venv python — runs 30 sequential GETs per endpoint,
# respects rate limits, prints p50/p95/p99
.venv\Scripts\python.exe -c "import asyncio; exec(open('tests/load/bench_live.py').read())"
```

### Full load test via Locust

```powershell
locust -f tests/load/locustfile.py `
    --host=https://flowpulse-backend-g6g2de3yuq-el.a.run.app `
    --headless -u 100 -r 10 -t 60s
```

### Frontend bundle

```powershell
cd frontend
npm run build  # table of first-load JS sizes prints at the end
```

### Engine tick benchmark (local)

```powershell
.venv\Scripts\python.exe -m pytest backend/tests/test_property_scoring.py -q
```

### WebSocket payload size

```bash
npm i -g wscat
wscat -c wss://flowpulse-backend-g6g2de3yuq-el.a.run.app/ws
# observe first frame (full) then watch diffs
```

---

## Numbers that will improve after the next `.\deploy.bat`

The current live image was built before three perf-and-observability improvements landed:

| Improvement | Expected delta after rebuild |
|---|---|
| `GZipMiddleware(minimum_size=500)` | `/api/zones/graph` payload 3.7 KB → 0.9 KB |
| ETag + 304 Not Modified on `/graph` | Reload traffic drops to 1 byte (just the 304) |
| Cloud Monitoring + BigQuery fan-out | New: `custom.googleapis.com/flowpulse/crowd_flow_score` chart populates; `flowpulse_events.ticks` table starts filling |
| Vertex AI routing via `GOOGLE_GENAI_USE_VERTEXAI=1` | Agent p50 roughly flat (~2 s); free of AI Studio rate-limit |

Re-run the benchmark section above after rebuild and update this file if the numbers shift materially.
