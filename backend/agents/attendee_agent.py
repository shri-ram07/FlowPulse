"""AttendeeAgent — fan-facing concierge.

Uses Google ADK + Gemini 2.0 Flash when credentials exist; otherwise falls
back to a deterministic intent router that still calls the real tools so the
UX (grounded answers with tool-call chips) stays intact.
"""
from __future__ import annotations

import re

from backend.agents import tools
from backend.agents.adk_runtime import build_adk_agent, reset_session, run_adk
from backend.agents.prompts import ATTENDEE_SYS_PROMPT

_runner = build_adk_agent(
    name="attendee_agent",
    model="gemini-2.0-flash",
    instruction=ATTENDEE_SYS_PROMPT,
    tool_fns=tools.ATTENDEE_TOOLS,
)


def reset_attendee_session(session_id: str) -> None:
    """Clear the cached ADK session so the next /attendee call starts fresh."""
    reset_session(_runner, session_id)


def build_contextual_message(message: str, location: str | None) -> str:
    """Prefix the user's question with a short machine-readable location hint
    so the model (and a reviewer tailing the logs) can see what the fan typed
    *and* where they're standing.
    """
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
        f"Use this as the 'start' when calling get_best_route.]\n\n"
        f"Question: {message}"
    )


async def ask_attendee(
    message: str,
    location: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Return {reply, tool_calls[], engine, [error]}.

    tool_calls is a list of {name, args, result} so the UI can render citation
    chips — this is the "grounded AI" differentiator. Works in both ADK mode
    (extracted from function_call/function_response events) and fallback mode.

    A stable `session_id` enables multi-turn memory in ADK mode.
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


# ---- deterministic fallback reasoner -----------------------------------

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
    calls: list[dict] = []
    def record(name: str, args: dict, result) -> None:
        calls.append({"name": name, "args": args, "result": result})

    kind = _infer_kind(message)
    m = message.lower()

    if kind in ("food", "restroom", "merch"):
        result = tools.get_all_zones(kind=kind)
        record("get_all_zones", {"kind": kind}, result)
        if not result:
            return {"reply": f"No {kind} zones are currently tracked.",
                    "tool_calls": calls, "engine": "fallback"}
        ranked = sorted(result, key=lambda z: (-z["score"], z["wait_minutes"]))
        best = ranked[0]
        extra = ""
        if location and location in {z["id"] for z in tools.get_all_zones()}:
            route = tools.get_best_route(location, best["id"], optimize="comfort")
            record("get_best_route",
                   {"start": location, "dest": best["id"], "optimize": "comfort"},
                   route)
            if "eta_seconds" in route:
                extra = f" About {route['eta_seconds'] // 60} min walk from your spot."
        elif not location:
            extra = " (Tap a zone on the map to tell me where you are for a walking time.)"
        reply = (
            f"Head to {best['name']} — Flow Score {best['score']}/100, "
            f"~{best['wait_minutes']} min wait ({best['level']}).{extra}"
        )
        return {"reply": reply, "tool_calls": calls, "engine": "fallback"}

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

    if "forecast" in m or "in 5" in m or "later" in m:
        all_ = tools.get_all_zones()
        record("get_all_zones", {}, all_)
        worst = max(all_, key=lambda z: z["density"])
        fc = tools.forecast_zone(worst["id"], horizon_minutes=5)
        record("forecast_zone", {"zone_id": worst["id"], "horizon_minutes": 5}, fc)
        return {
            "reply": (
                f"In 5 min {worst['name']} is forecast at density "
                f"{fc['predicted_density']:.0%} and Flow Score {fc['predicted_score']}."
            ),
            "tool_calls": calls, "engine": "fallback",
        }

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
