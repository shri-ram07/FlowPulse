# ADR 0001 — Model the stadium as a flow system, not a container

Status: **Accepted**
Date: 2026-04-16
Deciders: Shri Ram Dwivedi

## Context

Existing stadium apps ("ticket wallets") treat the venue as a set of fixed-capacity containers. They show a seat map and a payment button; they don't know where people actually are, which queues are shortest, or where pressure is building.

Any system that wants to *reduce* congestion — not just display it — has to model the building as something more dynamic. Two options were on the table:

1. **Container model** — each zone has `capacity` and `occupancy`; show fill percentages.
2. **Flow model** — each zone is a node in a graph; track inflow/outflow rates and compute a score that combines density + trend.

## Decision

Model every zone as a node in a **directed flow graph**:

- Per zone: `capacity`, `occupancy`, `inflow_rate` (EWMA), `outflow_rate` (EWMA), `neighbors[]`, `history[60]`.
- Edges carry `walk_seconds`.
- Global per-zone output: **Crowd Flow Score (0–100)** combining density, wait time, pressure trend, and a risk flag.

This lets us:

- Forecast each zone's near-future density by extrapolating the EWMA rates (no ML, fully explainable).
- Route users with Dijkstra weighted by `walk_seconds × density_penalty` so paths skirt hot zones.
- Identify building-scale pressure (not just local fill) via neighbour-spillover analysis.
- Expose a single metric judges + staff can reason about.

## Consequences

**Positive**
- Closed-loop control becomes possible: sense → decide → influence → re-sense.
- The simulator and real sensors share the same event interface; swapping in LiDAR / Wi-Fi probes later is additive.
- Forecasts don't need training data — EWMA extrapolation works from the first tick.

**Negative**
- The graph needs to be curated per venue (coordinates, edges, service rates). Not auto-discovered.
- O(Z) tick cost grows with zone count, but stays under 20 ms for 500 zones (see `docs/BENCHMARKS.md`).

## Alternatives considered

- **Container-only**: discarded; can't reason about routing or proactive intervention.
- **Agent-based (each person is a sim agent)**: more realistic but ~1000× more expensive; unnecessary for this fidelity of decision.
- **Classical queueing theory (M/M/c models per zone)**: fine for steady-state waits; cannot capture inter-zone spillover cleanly.
