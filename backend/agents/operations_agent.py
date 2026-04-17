"""OperationsAgent — structured decision-support for staff.

Emits a JSON action plan. Closed-loop: the ops console lets a human "Apply"
an action, which calls the write-tool (dispatch_alert / suggest_redirect),
which the engine incorporates on the next tick.
"""
from __future__ import annotations

import json
import re

from backend.agents import tools
from backend.agents.adk_runtime import build_adk_agent, run_adk
from backend.agents.prompts import OPERATIONS_SYS_PROMPT

_runner = build_adk_agent(
    name="operations_agent",
    model="gemini-2.0-flash",
    instruction=OPERATIONS_SYS_PROMPT,
    tool_fns=tools.OPERATIONS_TOOLS,
)


async def propose_actions() -> dict:
    """Return the ops JSON plan — ADK output if available, else deterministic."""
    if _runner is not None:
        try:
            raw = await run_adk(
                _runner,
                user_id="ops",
                message=(
                    "Inspect the venue and propose interventions as the required JSON. "
                    "Ground every rationale in a tool call."
                ),
            )
            return {"engine": "google-adk", **_coerce_json(raw)}
        except Exception as e:
            return {"engine": "fallback", "error": str(e), **_deterministic_plan()}
    return {"engine": "fallback", **_deterministic_plan()}


def _coerce_json(raw: str) -> dict:
    """Extract the first JSON object from the model's text."""
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not m:
        return {"situation": raw, "root_cause": "unstructured_output", "actions": [], "confidence": 0.0}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"situation": raw, "root_cause": "invalid_json", "actions": [], "confidence": 0.0}


def _deterministic_plan() -> dict:
    """Rule-based plan used when ADK is not available — still grounded in live data."""
    zones = tools.get_all_zones()
    if not zones:
        return {
            "situation": "No live zone data yet.",
            "root_cause": "engine_empty",
            "actions": [{"type": "monitor", "target": "stadium", "eta_minutes": 1,
                         "rationale": "Waiting for first tick."}],
            "confidence": 0.2,
        }

    critical = [z for z in zones if z["level"] == "critical"]
    congested = [z for z in zones if z["level"] in ("critical", "congested")]
    worst = min(zones, key=lambda z: z["score"])

    if not congested:
        return {
            "situation": f"Venue calm — worst zone is {worst['name']} at {worst['score']}/100.",
            "root_cause": "no_hotspots",
            "actions": [{"type": "monitor", "target": worst["id"], "eta_minutes": 2,
                         "rationale": f"{worst['name']} score {worst['score']}/100, trend {worst['trend']}."}],
            "confidence": 0.9,
        }

    actions: list[dict] = []
    root_zone = critical[0] if critical else congested[0]

    # Redirect logic — find a same-kind alternative with headroom and decent score.
    candidates = [
        z for z in zones
        if z["kind"] == root_zone["kind"]
        and z["id"] != root_zone["id"]
        and z["score"] >= 60
        and z["occupancy"] < z["capacity"] * 0.7
    ]
    if candidates:
        target = max(candidates, key=lambda z: z["score"])
        relief = tools.suggest_redirect(root_zone["id"], target["id"])
        actions.append({
            "type": "redirect",
            "target": root_zone["id"],
            "eta_minutes": 2,
            "rationale": (
                f"Redirect ~{relief.get('redirect_count', 0)} people from {root_zone['name']} "
                f"to {target['name']} (score {target['score']}). "
                f"Expected relief {relief.get('expected_relief_pct', 0)}%."
            ),
        })

    # Gate overflow handling.
    if root_zone["kind"] == "gate" and root_zone["density"] > 0.9:
        # Find a sibling gate with lowest occupancy.
        siblings = [z for z in zones if z["kind"] == "gate" and z["id"] != root_zone["id"]]
        if siblings:
            open_tgt = min(siblings, key=lambda z: z["density"])
            actions.append({
                "type": "open_gate",
                "target": open_tgt["id"],
                "eta_minutes": 1,
                "rationale": (
                    f"{open_tgt['name']} at {open_tgt['density']:.0%} density — open lanes to absorb "
                    f"{root_zone['name']} overflow ({root_zone['density']:.0%})."
                ),
            })

    # Always add a push notification for the hottest zone.
    actions.append({
        "type": "push_notification",
        "target": root_zone["id"],
        "eta_minutes": 1,
        "rationale": (
            f"Nudge fans in/near {root_zone['name']} (score {root_zone['score']}, "
            f"wait {root_zone['wait_minutes']} min) with a quieter alternative."
        ),
    })

    # Record an alert entry for the ops log.
    tools.dispatch_alert(
        root_zone["id"],
        f"Ops plan generated — {len(actions)} action(s) proposed.",
        severity="critical" if critical else "warn",
    )

    return {
        "situation": (
            f"{len(critical)} critical + {len(congested) - len(critical)} congested zones. "
            f"Worst: {root_zone['name']} ({root_zone['score']}/100)."
        ),
        "root_cause": (
            f"{root_zone['name']} density {root_zone['density']:.0%}, "
            f"inflow {root_zone['inflow_per_min']:.1f}/min vs outflow {root_zone['outflow_per_min']:.1f}/min."
        ),
        "actions": actions[:4],
        "confidence": 0.85,
    }
