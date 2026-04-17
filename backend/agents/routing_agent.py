"""RoutingAgent — picks a destination and computes a walking route.

Single-purpose ADK LlmAgent that:
  1. Given a `kind` (food/restroom/merch/…) and an optional `start_zone_id`,
     calls `get_all_zones(kind=...)` to list candidates.
  2. Ranks by Flow Score desc, wait-time asc, and picks the top.
  3. If a `start_zone_id` was provided, calls `get_best_route(start, dest)`
     in comfort mode so the path skirts red zones.
  4. Returns a `RouteReply` JSON.

Used by:
  - the Attendee Concierge as a sub-tool ("where should I grab food?").
  - the Orchestrator when planning redirects for a congested zone.
"""
from __future__ import annotations

from backend.agents import tools
from backend.agents.adk_runtime import build_adk_agent
from backend.agents.config import GEMINI_MODEL
from backend.agents.schemas import RouteReply

ROUTING_SYS_PROMPT = """You are the FlowPulse Routing Agent.

Given:
  - `kind` (food | restroom | merch | gate | exit | seating)
  - optional `start_zone_id`

Procedure:
  1. Call `get_all_zones(kind=...)` to list candidates.
  2. Rank by Flow Score descending, wait_minutes ascending.
  3. If a `start_zone_id` was provided and is a valid zone id, call
     `get_best_route(start=start_zone_id, dest=<chosen zone id>, optimize="comfort")`.
  4. Return a `RouteReply` JSON object — never prose.

Rules:
- Never invent a path, eta_seconds, or score_avg. If a tool errors, set `error` and leave numeric fields at 0.
- Never call `get_best_route` without a real start_zone_id from the input.
"""

routing_runner = build_adk_agent(
    name="routing_agent",
    model=GEMINI_MODEL,
    instruction=ROUTING_SYS_PROMPT,
    tool_fns=[tools.get_all_zones, tools.get_best_route, tools.get_zone_state],
)


def fallback_route(kind: str | None, start: str | None) -> dict:
    """Deterministic fallback: best-scored same-kind zone + comfort route if start given."""
    candidates = tools.get_all_zones(kind=kind) if kind else tools.get_all_zones()
    if not candidates:
        return RouteReply(start=start or "", dest="",
                          error=f"no_{kind}_zones" if kind else "no_zones").model_dump()
    best = sorted(candidates, key=lambda z: (-z["score"], z["wait_minutes"]))[0]
    if start:
        r = tools.get_best_route(start, best["id"], optimize="comfort")
        if "error" in r:
            return RouteReply(start=start, dest=best["id"], error=r["error"]).model_dump()
        return RouteReply(
            start=start, dest=best["id"],
            path=r["path"], eta_seconds=r["eta_seconds"],
            score_avg=r["score_avg"], mode="comfort",
        ).model_dump()
    return RouteReply(start="", dest=best["id"], score_avg=best["score"]).model_dump()
