"""SafetyAgent — triages the whole venue for risk.

Reads every zone via `get_all_zones()` and returns a `SafetyReport`: counts of
critical / congested zones plus detailed flags. Used by the Orchestrator as the
first step of every planning cycle so downstream decisions have a common
snapshot.
"""
from __future__ import annotations

from backend.agents import tools
from backend.agents.adk_runtime import build_adk_agent
from backend.agents.schemas import SafetyFlag, SafetyReport

SAFETY_SYS_PROMPT = """You are the FlowPulse Safety Agent.

Every call, you:
  1. Call `get_all_zones()` to read the current venue state.
  2. Identify zones at `level` = "critical" or "congested".
  3. Emit a `SafetyReport` JSON object with counts + up to 10 flags (top by worst score).

Rules:
- `reason` on each flag MUST include the live numeric density + trend from the tool result.
- NEVER invent a flag for a zone the tool didn't return as critical/congested.
- Sort flags by ascending Flow Score (worst first).
"""

safety_runner = build_adk_agent(
    name="safety_agent",
    model="gemini-2.0-flash",
    instruction=SAFETY_SYS_PROMPT,
    tool_fns=[tools.get_all_zones, tools.get_zone_state],
)


def fallback_safety() -> dict:
    """Deterministic safety scan — used when ADK isn't available."""
    zones = tools.get_all_zones()
    critical = [z for z in zones if z["level"] == "critical"]
    congested = [z for z in zones if z["level"] == "congested"]
    flagged = sorted(critical + congested, key=lambda z: z["score"])[:10]
    flags = [
        SafetyFlag(
            zone_id=z["id"],
            level=z["level"],  # type: ignore[arg-type]
            score=z["score"],
            reason=(
                f"{z['name']} density {z['density']:.0%}, "
                f"inflow {z['inflow_per_min']:.1f}/min vs outflow {z['outflow_per_min']:.1f}/min, "
                f"trend {z['trend']}"
            ),
        )
        for z in flagged
    ]
    return SafetyReport(
        critical_count=len(critical),
        congested_count=len(congested),
        flags=flags,
    ).model_dump()
