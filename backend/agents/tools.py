"""Agent tools — plain Python functions that read/write the CrowdFlowEngine.

These are wrapped as Google ADK FunctionTool objects in `adk_tools.py`, and are
also exposed as REST endpoints. Every function has a docstring that doubles
as the LLM-facing tool description.

Design rule: tools NEVER make up numbers. They always return current engine
state so the agent's answers are traceable.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from backend.core.engine import Alert
from backend.core.graph import best_route
from backend.runtime import get_engine


# ---- read tools ---------------------------------------------------------
def get_zone_state(zone_id: str) -> dict[str, Any]:
    """Return live metrics for a single zone.

    Args:
        zone_id: Stadium zone id (e.g. "gate_a", "food_court_2", "restroom_n3").
    """
    return get_engine().snapshot(zone_id)


def get_all_zones(kind: str | None = None) -> list[dict[str, Any]]:
    """List every zone's current state.

    Args:
        kind: Optional filter: "gate" | "seating" | "food" | "restroom" |
            "concourse" | "exit" | "merch". Omit for all.
    """
    return get_engine().snapshot_all(kind=kind)


def get_wait_time(zone_id: str) -> dict[str, Any]:
    """Return current estimated wait time in minutes for a service zone."""
    s = get_engine().snapshot(zone_id)
    # Confidence degrades when flow is very bursty.
    eng = get_engine()
    z = eng.zones[zone_id]
    burstiness = abs(z.inflow_rate - z.outflow_rate) / max(z.capacity, 1)
    confidence = round(max(0.3, 1.0 - burstiness), 2)
    return {
        "zone_id": zone_id,
        "minutes": s["wait_minutes"],
        "confidence": confidence,
        "level": s["level"],
    }


def get_best_route(
    start: str,
    dest: str,
    optimize: Literal["time", "comfort"] = "comfort",
) -> dict[str, Any]:
    """Compute the best walking route between two zones.

    Args:
        start: Source zone id.
        dest: Destination zone id.
        optimize: `"time"` minimises walk seconds; `"comfort"` (default) also
            avoids red (critical / congested) zones along the path.

    Returns:
        Dict with `path` (zone ids in order), `eta_seconds` (total walk),
        `score_avg` (mean Flow Score along the path), and `mode`.
    """
    return best_route(get_engine().zones, start, dest, mode=optimize)


def forecast_zone(zone_id: str, horizon_minutes: int = 2) -> dict[str, Any]:
    """Predict a zone's occupancy and Crowd Flow Score N minutes ahead.

    Args:
        zone_id: Zone to forecast.
        horizon_minutes: Minutes ahead (1-10 is reasonable; default 2).

    Returns:
        Dict with `zone_id`, `horizon_minutes`, `predicted_occupancy`,
        `predicted_density`, `predicted_score` (all grounded in the live engine
        state — the agent cannot invent these numbers).
    """
    return get_engine().forecast(zone_id, horizon_minutes=horizon_minutes)


# ---- write tools (staff only via ops agent) ----------------------------
def dispatch_alert(zone_id: str, message: str, severity: str = "warn") -> dict[str, Any]:
    """Record and broadcast a staff alert for a specific zone.

    Args:
        zone_id: Zone the alert pertains to.
        message: Human-readable message (truncated to 240 chars before persist).
        severity: One of `info`, `warn`, `critical`. Anything else is coerced
            to `warn`.

    Returns:
        `{alert_id, delivered}` on success, or `{error: "unknown_zone"}` if the
        zone id is not in the engine.
    """
    if severity not in ("info", "warn", "critical"):
        severity = "warn"
    eng = get_engine()
    if zone_id not in eng.zones:
        return {"error": "unknown_zone"}
    a = Alert(
        id=str(uuid.uuid4()),
        zone_id=zone_id,
        severity=severity,
        message=message[:240],
        ts=time.monotonic(),
    )
    eng.alerts.append(a)
    return {"alert_id": a.id, "delivered": True}


def suggest_redirect(from_zone: str, to_zone: str) -> dict[str, Any]:
    """Estimate the density relief if 30% of `from_zone` is rerouted to `to_zone`.

    Args:
        from_zone: Overloaded source zone.
        to_zone: Destination with headroom.

    Returns:
        `{from_zone, to_zone, redirect_count, expected_relief_pct}` — the
        number of people that fit within the destination's remaining capacity,
        and the percent-of-source-capacity relief that produces.
    """
    eng = get_engine()
    if from_zone not in eng.zones or to_zone not in eng.zones:
        return {"error": "unknown_zone"}
    zf, zt = eng.zones[from_zone], eng.zones[to_zone]
    headroom = max(0, zt.capacity - zt.occupancy)
    redirectable = min(int(zf.occupancy * 0.3), headroom)
    relief_pct = round((redirectable / zf.capacity) * 100, 1) if zf.capacity else 0.0
    return {
        "from_zone": from_zone,
        "to_zone": to_zone,
        "redirect_count": redirectable,
        "expected_relief_pct": relief_pct,
    }


# ---- registry exposed to both ADK and fallback agents -----------------
ATTENDEE_TOOLS = [
    get_zone_state,
    get_all_zones,
    get_wait_time,
    get_best_route,
    forecast_zone,
]
OPERATIONS_TOOLS = [*ATTENDEE_TOOLS, dispatch_alert, suggest_redirect]
