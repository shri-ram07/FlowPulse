"""CommsAgent — writes fan-facing message copy for a given action.

Given an `OpsAction` (or similar), drafts the short copy that goes out over
FCM push / tannoy / digital signage. Keeps tone friendly and concrete, cites
a destination when possible.

Called by the Orchestrator after it has picked the action type + target; the
Ops console surfaces the draft so a human can preview before pushing.
"""
from __future__ import annotations

from typing import Literal

from backend.agents import tools
from backend.agents.adk_runtime import build_adk_agent
from backend.agents.config import GEMINI_MODEL
from backend.agents.schemas import CommsDraft

COMMS_SYS_PROMPT = """You are the FlowPulse Comms Agent.

Given:
  - `zone_id`   — the zone the message is about
  - `channel`   — push | tannoy | digital_signage
  - `severity`  — info | warn | critical
  - `hint`      — optional one-line hint about WHY (e.g. "redirect to Food Court 5")

Procedure:
  1. Call `get_zone_state(zone_id)` to ground the copy in real numbers (wait time, level).
  2. Draft a `CommsDraft` JSON with `title` + `body` in the requested tone.

Rules:
- Keep `title` ≤ 60 chars, friendly, specific.
- Keep `body` ≤ 200 chars; always include the destination zone name if provided in the hint.
- Never invent a wait time or score — use the tool result or the hint only.
- Match severity to language: "info" is helpful; "warn" is urgent-but-calm; "critical" is directive.
"""

comms_runner = build_adk_agent(
    name="comms_agent",
    model=GEMINI_MODEL,
    instruction=COMMS_SYS_PROMPT,
    tool_fns=[tools.get_zone_state, tools.get_all_zones],
)


def fallback_comms(
    zone_id: str,
    channel: Literal["push", "tannoy", "digital_signage"] = "push",
    severity: Literal["info", "warn", "critical"] = "info",
    hint: str = "",
) -> dict:
    """Template-based copy when ADK is unavailable."""
    try:
        z = tools.get_zone_state(zone_id)
    except KeyError:
        return CommsDraft(
            channel=channel, audience_zone_id=zone_id,
            title="Crowd tip from FlowPulse",
            body=hint or "A quieter option is nearby — check the map.",
            severity=severity,
        ).model_dump()

    title = f"Heads up: {z['name']} is {z['level']}"
    body_parts = [f"{z['name']} is at {int(z['density']*100)}% capacity with a {z['wait_minutes']} min wait."]
    if hint:
        body_parts.append(hint)
    else:
        body_parts.append("Tap the map in the FlowPulse app for a quieter option.")

    body = " ".join(body_parts)[:200]
    return CommsDraft(
        channel=channel, audience_zone_id=zone_id,
        title=title[:80], body=body, severity=severity,
    ).model_dump()
