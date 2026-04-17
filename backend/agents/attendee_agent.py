"""AttendeeAgent — fan-facing concierge.

Uses Google ADK + Gemini 2.0 Flash when credentials exist. The Concierge is a
top-level LlmAgent that **composes two specialist sub-agents** (RoutingAgent
and ForecastAgent) as AgentTool-style callables, plus the direct read-only
engine tools. This mirrors the winning multi-agent pattern: one agent per
concern, orchestrated by a lightweight top-level reasoner.

When ADK isn't available (no GOOGLE_API_KEY), a deterministic fallback still
calls the same sub-agent fallbacks so the UX (tool-call chips) stays intact.
"""
from __future__ import annotations

import re

from backend.agents import tools
from backend.agents.adk_runtime import build_adk_agent, reset_session, run_adk
from backend.agents.forecast_agent import fallback_forecast
from backend.agents.prompts import ATTENDEE_SYS_PROMPT
from backend.agents.routing_agent import fallback_route

# ---- sub-agent-as-tool shims -----------------------------------------------
# Expose the specialist agents to Gemini as regular tools. Gemini picks them
# as naturally as any other callable. The bodies go through the specialist
# fallbacks — they're already grounded in live engine state.

def routing_sub_agent(kind: str, start_zone_id: str = "") -> dict:
    """Ask the Routing specialist for the best same-kind destination and walking route.

    Args:
        kind: Category to route to — "food", "restroom", "merch", "gate", "exit".
        start_zone_id: Optional zone id of where the fan currently is.
    """
    return fallback_route(kind=kind, start=start_zone_id or None)


def forecast_sub_agent(zone_id: str, horizon_minutes: int = 5) -> dict:
    """Ask the Forecast specialist to predict a zone's Flow Score N minutes ahead.

    Args:
        zone_id: The zone to forecast.
        horizon_minutes: How far ahead to predict (1-10).
    """
    return fallback_forecast(zone_id, horizon_minutes=horizon_minutes)


_attendee_tools = [
    # sub-agents (top-level composition)
    routing_sub_agent,
    forecast_sub_agent,
    # direct engine reads (cheap lookups the model shouldn't need to delegate)
    tools.get_zone_state,
    tools.get_all_zones,
    tools.get_wait_time,
    tools.get_best_route,
    tools.forecast_zone,
]

_runner = build_adk_agent(
    name="attendee_agent",
    model="gemini-2.0-flash",
    instruction=ATTENDEE_SYS_PROMPT,
    tool_fns=_attendee_tools,
)


def reset_attendee_session(session_id: str) -> None:
    """Clear the cached ADK session so the next /attendee call starts fresh."""
    reset_session(_runner, session_id)


def build_contextual_message(message: str, location: str | None) -> str:
    """Prefix the user's question with a short machine-readable location hint."""
    if not location:
        return (
            "[Context: the fan has NOT shared their location. Answer generally, "
            "and invite them to tap a zone on the map if they want routing.]\n\n"
            f"Question: {message}"
        )
    zone_name = location
    try:
        state = tools.get_zone_state(location)
        zone_name = state["name"]
    except KeyError:
        pass
    return (
        f"[Context: the fan is currently at zone id '{location}' ({zone_name}). "
        f"Use this as the 'start_zone_id' when calling routing_sub_agent.]\n\n"
        f"Question: {message}"
    )


async def ask_attendee(
    message: str,
    location: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Return {reply, tool_calls[], engine, [error]}.

    `tool_calls` is extracted from ADK events (function_call / function_response).
    In fallback mode, it's constructed explicitly so the UI's citation chips
    render in both paths.
    """
    contextual = build_contextual_message(message, location)

    if _runner is not None:
        try:
            result = await run_adk(
                _runner, user_id="attendee",
                message=contextual, session_id=session_id,
            )
            return {
                "reply": result["reply"],
                "tool_calls": result["tool_calls"],
                "engine": "google-adk",
            }
        except Exception as e:
            fb = _fallback(message, location)
            return {
                "reply": f"(falling back) {fb['reply']}",
                "tool_calls": fb["tool_calls"],
                "engine": "fallback",
                "error": str(e),
            }
    return _fallback(message, location)


# ---- deterministic fallback reasoner ---------------------------------------

KIND_KEYWORDS = {
    "food": ["food", "eat", "snack", "hungry", "beer", "drink", "meal", "concession"],
    "restroom": ["restroom", "toilet", "bathroom", "washroom", "loo"],
    "merch": ["merch", "jersey", "shop", "store", "souvenir"],
    "gate": ["gate", "entry", "entrance"],
    "exit": ["exit", "leave", "out", "home"],
}


def _infer_kind(msg: str) -> str | None:
    m = msg.lower()
    for kind, kws in KIND_KEYWORDS.items():
        if any(kw in m for kw in kws):
            return kind
    return None


def _fallback(message: str, location: str | None) -> dict:
    """Deterministic path — exercises the SAME sub-agent fallbacks so the UI
    sees tool chips like `routing_sub_agent()` / `forecast_sub_agent()`
    regardless of which engine served the turn."""
    calls: list[dict] = []

    def record(name: str, args: dict, result: object) -> None:
        calls.append({"name": name, "args": args, "result": result})

    kind = _infer_kind(message)
    m = message.lower()

    # 1) Forecast-intent ("forecast", "in 5", "later")?
    if "forecast" in m or "in 5" in m or "later" in m:
        all_ = tools.get_all_zones()
        record("get_all_zones", {}, all_)
        worst = max(all_, key=lambda z: z["density"])
        fc = forecast_sub_agent(worst["id"], horizon_minutes=5)
        record("forecast_sub_agent",
               {"zone_id": worst["id"], "horizon_minutes": 5}, fc)
        return {
            "reply": (
                f"In 5 min {worst['name']} is forecast at density "
                f"{fc['predicted_density']:.0%} and Flow Score {fc['predicted_score']}."
                f" Recommendation: {fc['recommendation']}."
            ),
            "tool_calls": calls, "engine": "fallback",
        }

    # 2) "how busy is X" exact-match queries.
    mzone = re.search(r"(gate [a-g]|food court \d|restroom [a-z]-?\d?|exit ramp)", m)
    if mzone:
        all_ = tools.get_all_zones()
        record("get_all_zones", {}, all_)
        match = next((z for z in all_ if z["name"].lower() == mzone.group(0)), None)
        if match:
            s = tools.get_zone_state(match["id"])
            record("get_zone_state", {"zone_id": match["id"]}, s)
            return {
                "reply": (
                    f"{s['name']} is {s['level']} — Flow Score {s['score']}/100, "
                    f"~{s['wait_minutes']} min wait, trend {s['trend']}."
                ),
                "tool_calls": calls, "engine": "fallback",
            }

    # 3) Category routing via the RoutingAgent sub-tool.
    if kind in ("food", "restroom", "merch"):
        route = routing_sub_agent(kind=kind, start_zone_id=location or "")
        record("routing_sub_agent",
               {"kind": kind, "start_zone_id": location or ""}, route)
        if route.get("error"):
            return {"reply": f"Routing error: {route['error']}",
                    "tool_calls": calls, "engine": "fallback"}
        if not route.get("dest"):
            return {"reply": "No matching zones found.",
                    "tool_calls": calls, "engine": "fallback"}
        dest_state = tools.get_zone_state(route["dest"])
        record("get_zone_state", {"zone_id": route["dest"]}, dest_state)
        extra = ""
        if location and route.get("eta_seconds"):
            extra = f" About {route['eta_seconds'] // 60} min walk from your spot."
        elif not location:
            extra = (" (Tap a zone on the map to tell me where you are for a "
                     "walking time.)")
        return {
            "reply": (
                f"Head to {dest_state['name']} — Flow Score {dest_state['score']}/100, "
                f"~{dest_state['wait_minutes']} min wait ({dest_state['level']}).{extra}"
            ),
            "tool_calls": calls, "engine": "fallback",
        }

    # 4) Default — show overall health, invite a click.
    all_ = tools.get_all_zones()
    record("get_all_zones", {}, all_)
    avg = round(sum(z["score"] for z in all_) / len(all_)) if all_ else 0
    hottest = min(all_, key=lambda z: z["score"]) if all_ else None
    hot_s = f" Hottest spot: {hottest['name']} ({hottest['score']}/100)." if hottest else ""
    hint = "" if location else " Tap a zone on the map to tell me where you are."
    return {
        "reply": (f"Stadium-wide Flow Score is {avg}/100.{hot_s}"
                  f" Ask me for food, restrooms, or routes.{hint}"),
        "tool_calls": calls, "engine": "fallback",
    }
