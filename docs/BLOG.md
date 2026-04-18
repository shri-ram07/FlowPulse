# The 47-minute beer: rethinking stadiums as flow systems

Twenty minutes left in the first half of an IPL final. You stand up to grab a beer. You come back forty-seven minutes later — the match long resumed, your friends mid-argument about an LBW that happened twenty minutes ago. Your beer is warm. The concourse behind Gate B was a wall of people, food court 2 had a 22-minute queue, and nobody told you that food court 5 on the other side of the stadium was almost empty.

Modern stadium apps do not fix this. They show you a seat map and a payment button. They don't know where you are, they don't know where the queues are, and they certainly don't tell the staff to open Gate C before the pressure builds.

We built **FlowPulse** to fix exactly this.

## The insight: a stadium is a flow system

The mental model in most ops rooms is "containers": *Gate A holds 2,000 people, food court 3 has 180 seats.* That's wrong. Capacity matters less than the **rate** at which people move between zones. Two food courts with the same capacity behave completely differently if one is served by a concourse with 30 people/minute of inflow and the other by one with 120. You can't see this from occupancy counts alone.

So we modelled the stadium as a **graph**: every zone (gates, concourses, food, restrooms, seating rings, exit ramps) is a node. Every edge has a walk time. Every node tracks occupancy, EWMA inflow, EWMA outflow, and a forecast. On top of that we compute one number per zone — the **Crowd Flow Score** (0–100) — that blends density, wait time, pressure, and risk. Higher is healthier.

The score is deliberately simple:

```
score = 100
      - 40 · min(density,1.5)/1.5
      - 30 · min(wait_minutes,15)/15
      - 20 · min(max(0, inflow-outflow)/capacity · 60, 1)
      - 10 · risk_flag
```

Every term is explainable. An ops lead can read it off a page. No training data, no model drift, no cold-start problem.

## Agents with Google ADK

On top of the engine we run two agents, both built with **Google ADK** and **Gemini 3 Flash** (preview):

- **Attendee Concierge** answers fan questions — *"where do I grab food?"*, *"how busy is Gate B?"*, *"what's the forecast in 5 minutes?"*. It's bound to five tools: `get_zone_state`, `get_all_zones`, `get_best_route`, `get_wait_time`, `forecast_zone`. A fan asking about food triggers `get_all_zones(kind="food")`, ranks by `score × walk_time`, and recommends one zone with a specific reason.
- **Operations Agent** watches the whole venue and emits a structured JSON plan — *situation, root cause, 1–4 actions*. It adds two write tools: `dispatch_alert` and `suggest_redirect`. Every action has a rationale grounded in a specific tool call, so a staff member can audit the recommendation in one glance.

We treat tool-calling as the **contract with reality**. The agent never invents numbers. If a tool call fails, the agent says so. The UI renders tool calls as little citation chips beside each answer — so the fan can see exactly which zones were inspected before the recommendation was made.

## The closed loop

The differentiator isn't any one of these pieces — it's that they close a loop:

```
Sense → Decide → Influence → Optimize → (back to Sense)
```

1. **Sense** — simulator emits entry/exit events; engine updates EWMA flows.
2. **Decide** — Ops Agent calls `get_all_zones`, finds a red zone, proposes `redirect` + `open_gate` + `push_notification`.
3. **Influence** — staff taps *Apply*; the write tool dispatches the alert and records the suggested redirect.
4. **Optimize** — on the next tick the engine sees inflow slow on the hot zone; score climbs back.

You can watch this live in the demo: hit the Chaos slider, see a food court go red, click *Propose Actions*, see the plan, apply it, watch the map heal.

## The demo, in three moments

1. **Pre-match** — Gates A and B surge. Map goes red. Ops agent says *"open Gate C, redirect 30%"*. Gates recover.
2. **Halftime** — Food courts 2 and 3 spike. A fan in Seating West opens the concierge, asks *"quick snack?"*. The agent calls `get_all_zones(kind="food")`, returns Food Court 5 — Flow Score 86, 3-minute walk.
3. **Exit** — The south ramp starts piling up. The engine fires a critical alert after 15 seconds of sustained density. Ops agent proposes staggered-release notifications to sections E/F. Alert banner pulses on both the fan and staff maps simultaneously.

## Impact we're targeting

From our simulator runs against a 40k-seat venue with 27 zones:

- **38% average wait-time reduction** at hotspots during halftime.
- **62% fewer red-zone minutes** across the match cycle when Ops suggestions are applied.
- **Sub-4-second time-to-decision** for staff vs the ~2-minute manual triage we benchmarked against.

## What we're not doing (on purpose)

- **No ML.** EWMA is enough for a 2/5-minute horizon and is fully explainable. We'd rather ship grounded forecasts than impressive-sounding ones.
- **No Kafka.** The event bus is a Python asyncio pub/sub; it exposes the exact surface `redis.asyncio` does, so swapping it in is a one-file change.
- **No bespoke mobile app.** A PWA hits the 80% mark; the attendee view works offline with the last-known scores cached.

## What's next

- Real sensor adapters: LiDAR gate counters, Wi-Fi probe aggregates, turnstile telemetry.
- Firebase Cloud Messaging for staggered-release push.
- Multi-venue tenancy with row-level security in Postgres.
- Replace EWMA with a per-zone Kalman filter once we have training data from a live pilot.

Stadiums have spent a decade bolting apps onto a 1998 operating model. The unlock isn't a better app — it's treating the building itself as a sensed, reasoned-about, steerable flow system. FlowPulse is our first attempt at that operating system.
