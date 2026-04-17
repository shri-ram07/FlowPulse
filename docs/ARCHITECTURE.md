# FlowPulse — Architecture

## Thesis

A stadium is not a container; it is a **flow system**. Capacity matters less than the rate at which people move between zones. FlowPulse models every zone as a node in a directed graph, measures inflow/outflow, computes a single Flow Score, and lets agents reason over that state with tool-calling.

## Components

```
 ┌──────────────────┐    ┌───────────────────┐    ┌─────────────────────┐
 │  Next.js 14 PWA  │◄──►│  FastAPI gateway  │◄──►│  Crowd Flow Engine  │
 │  /  /chat /ops   │ WS │  REST + /ws + JWT │    │  Zones · Scoring    │
 └──────────────────┘    └─────────┬─────────┘    │  EWMA · Forecast    │
                                   │              └──────────┬──────────┘
                                   │                         │
                              ┌────▼─────────┐      ┌────────▼────────┐
                              │ ADK Agents   │      │   Simulator     │
                              │ Attendee/Ops │      │  5-phase cycle  │
                              │ + tools.py   │◄─────┤  + chaos slider │
                              └──────────────┘      └─────────────────┘
```

### Crowd Flow Engine — `backend/core/`
- `zone.py` — Zone dataclass + service-rate heuristics per zone kind.
- `engine.py` — `CrowdFlowEngine` holds all zones, mutates via `enter/exit/move`, computes EWMA inflow/outflow on each `tick`, publishes snapshots to the event bus.
- `scoring.py` — Crowd Flow Score (density × wait × pressure × risk), trend-based forecast.
- `graph.py` — Dijkstra with two modes: `time` (walk seconds) and `comfort` (walk seconds × density penalty, routes around red zones).
- `events.py` — In-process async pub/sub. Interface mirrors `redis.asyncio` so a Redis backend is a one-file swap.

### Agent Layer — `backend/agents/`
- `tools.py` — read/write tool functions with Pydantic-typed returns.
- `adk_runtime.py` — Google ADK wiring (`Agent`, `FunctionTool`, `Runner`) with graceful fallback.
- `attendee_agent.py`, `operations_agent.py` — system prompts + ADK runners + deterministic fallback reasoners that call the same tools.

**Grounded-AI principle:** every claim in an agent reply corresponds to a tool call. The attendee UI renders tool calls as citation chips; the ops UI shows rationales that quote specific numbers.

### Simulator — `backend/sim/simulator.py`
Five phases in a ~10-minute wall-clock cycle: pre-match, Q1, halftime, Q2, exit. The chaos slider (0..1) injects random surges for live-demo resilience.

### Frontend — `frontend/`
- Next.js 14 App Router, single WebSocket hook (`lib/ws.ts`) drives all live views.
- `StadiumMap.tsx` renders a ring-and-concourse SVG with pulsing circles (size = occupancy, colour = score).
- PWA manifest for install/offline fallback.

## Data flow (1 tick)

1. Simulator emits entry/exit/move events on the engine.
2. Engine `tick()`:
   - Updates EWMA inflow/outflow per zone.
   - Evaluates risk rules → appends `Alert`s.
   - Publishes `{type:"tick", zones, alerts}` to event bus.
3. WebSocket route fans out the payload to every connected client.
4. Clients patch local state and re-render. SVG, gauges, and alert banners update.

## Security

- **JWT** for staff endpoints (`/api/sim/*`, `/api/agent/operations`). Attendee endpoints are read-only and unauthenticated.
- **CORS** locked to the frontend origin.
- **Rate limiting** per IP (sliding window) on attendee endpoints.
- **Pydantic** validation on every request body.
- **No PII** is logged; tool outputs only contain aggregate occupancy.
- **Secrets via env vars** (`FLOWPULSE_JWT_SECRET`, `GOOGLE_API_KEY`).

## Scaling notes (beyond demo)

| Bottleneck | Mitigation |
| --- | --- |
| Single engine process | Shard by zone-kind across workers; zones publish to Redis streams. |
| In-process event bus | Swap `EventBus.publish/subscribe` for `redis.asyncio` pub/sub (same interface). |
| WebSocket fan-out | Put behind a socket-aware load balancer; add Redis adapter. |
| Agent latency | Prompt-cache system prompts via ADK; batch forecast requests. |

## Testing

- 19 pytest cases covering engine, scoring, graph routing, tools, and the ops plan.
- Fresh engine per test via `conftest.py` fixture.
- CI (`.github/workflows/ci.yml`) runs backend pytest + frontend `tsc --noEmit` + `next build`.
