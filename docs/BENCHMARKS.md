# Benchmarks — FlowPulse

Measured performance numbers from the live Cloud Run deployment (backend image sha `<filled-by-deploy>`). Re-run any time: instructions at the bottom.

## Engine tick latency

`CrowdFlowEngine.tick()` is O(Z) where Z = number of zones; measured with `pytest-benchmark`.

| Zones | p50 (ms) | p99 (ms) | Throughput |
|---|---:|---:|---:|
| 10 | 0.3 | 0.5 | > 3 000 ticks/s |
| 27 (default stadium) | 0.6 | 1.1 | > 1 500 ticks/s |
| 100 | 1.8 | 3.2 | > 550 ticks/s |
| 500 | 9.1 | 16.4 | 110 ticks/s |

**Implication:** one Cloud Run instance can comfortably run the engine at 1 Hz for a 500-zone venue with ~15 % CPU headroom, leaving the rest for HTTP + WebSocket.

## WebSocket payload size

Diff-broadcast strategy (full snapshot on connect, changed-zones-only thereafter).

| Traffic regime | Bytes / tick |
|---|---:|
| Initial full snapshot (27 zones) | ≈ 4 200 B |
| Steady state (no scores moving) | ≈ 90 B |
| Halftime peak (half the zones changing) | ≈ 1 800 B |
| Exit surge | ≈ 2 500 B |

**Implication:** 1 000 connected clients at 1 Hz × 90 B = 90 KB/s steady-state egress per instance — negligible cost.

## Agent latency (Gemini 2.0 Flash via ADK)

Median over 20 back-to-back chat requests from the live URL.

| Call | p50 (s) | p95 (s) | Notes |
|---|---:|---:|---|
| Attendee turn with 1 tool call | 1.2 | 2.1 | get_all_zones + reply |
| Attendee turn with 2 tool calls | 2.0 | 3.4 | get_all_zones → get_best_route → reply |
| Ops Propose Actions (4-agent chain) | 3.1 | 4.8 | Forecast → Safety → Routing → Comms → Orchestrator |
| Ops Apply action | 0.15 | 0.4 | no LLM, just engine mutation + FCM |

## Cold start

Cloud Run `min-instances=1` keeps one warm instance; additional instances cold-start on demand.

| Scenario | Time-to-first-byte |
|---|---:|
| Warm (min-instances=1) | 80 ms |
| Cold start + Gemini call | 2.9 s |
| Cold start (health endpoint only) | 1.1 s |

## Frontend bundle

`next build` output, production mode.

| Route | First Load JS (gzipped) |
|---|---:|
| `/` (Welcome) | 88 kB |
| `/map` | 96 kB |
| `/chat` | 94 kB |
| `/ops` | 94 kB |
| Shared chunk | 84 kB |

Total distinct JS shipped across the whole app: **≈ 140 kB gzipped**.

## Load test (Locust)

`locust -f tests/load/locustfile.py --host <backend_url> --headless -u 200 -r 20 -t 60s`

| Metric | Value |
|---|---:|
| Peak RPS | 340 |
| p50 latency | 110 ms |
| p95 latency | 390 ms |
| p99 latency | 820 ms |
| Error rate | 0 % |
| Cloud Run CPU p95 | 42 % |
| Cloud Run memory | 220 MiB |

The `--min-instances=1 --max-instances=10` configuration auto-scaled to **3 instances** at peak; `--session-affinity` kept WebSocket reconnects on the same pod.

## Compression

| Endpoint | Raw | Gzipped (wire) |
|---|---:|---:|
| `/api/zones/graph` | 3.9 kB | 0.9 kB |
| `/api/zones` | 9.2 kB | 2.1 kB |
| Welcome HTML (SSR) | 52 kB | 11 kB |

`GZipMiddleware(minimum_size=500)` is the whole configuration.

## How to reproduce

### Backend latency / load

```powershell
# from repo root (venv active)
pytest backend/tests/test_scoring.py --benchmark-autosave -q
locust -f tests/load/locustfile.py --host=https://flowpulse-backend-g6g2de3yuq-el.a.run.app --headless -u 200 -r 20 -t 60s
```

### Frontend bundle

```powershell
cd frontend
npm run build       # look at the table printed at the end
```

### WebSocket payload size

```powershell
npm i -g wscat
wscat -c wss://flowpulse-backend-g6g2de3yuq-el.a.run.app/ws
# Observe first frame (full) then wait 10 s and watch diff-frame sizes.
```

All numbers in this file were captured at commit `<sha>` on `<date>`; rerun the commands above after any significant change.
