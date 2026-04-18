"""ForecastAgent — predicts near-future zone congestion.

Wraps the `forecast_zone` tool in an ADK `LlmAgent` that returns a typed
`ForecastReport`. The model's only job is to decide WHICH zone to forecast and
what to recommend based on the numbers the tool returns — it cannot invent
occupancy values.

Exposed to:
  - the Attendee Concierge (via `AgentTool(forecast_agent)`) so fans can ask
    "how busy will it be in 5 minutes?"
  - the Orchestrator (via the same pattern) for pre-emptive interventions.
"""

from __future__ import annotations

from typing import Any

from backend.agents import tools
from backend.agents.adk_runtime import build_adk_agent
from backend.agents.config import (
    GEMINI_MODEL,
    SCORE_INTERVENE_THRESHOLD,
    SCORE_MONITOR_THRESHOLD,
)
from backend.agents.schemas import ForecastReport

FORECAST_SYS_PROMPT = f"""You are the FlowPulse Forecast Agent.

Given a zone id (or the question context), you call `forecast_zone(zone_id, horizon_minutes)` on the live Crowd Flow Engine and return a `ForecastReport` JSON object.

Rules:
- ALWAYS call the tool; never invent predicted_occupancy / predicted_score.
- If `predicted_score` falls below {SCORE_INTERVENE_THRESHOLD} → set `recommendation` = "intervene".
- If `predicted_score` is {SCORE_INTERVENE_THRESHOLD}-{SCORE_MONITOR_THRESHOLD} → "monitor".
- If `predicted_score` ≥ {SCORE_MONITOR_THRESHOLD} → "hold".
- Default horizon is 5 minutes unless the caller specifies otherwise.
- Return JSON only; no prose around it.
"""

forecast_runner = build_adk_agent(
    name="forecast_agent",
    model=GEMINI_MODEL,
    instruction=FORECAST_SYS_PROMPT,
    tool_fns=[tools.forecast_zone, tools.get_zone_state, tools.get_all_zones],
)


def fallback_forecast(zone_id: str, horizon_minutes: int = 5) -> dict[str, Any]:
    """Deterministic fallback when ADK is unavailable — still grounded."""
    try:
        raw = tools.forecast_zone(zone_id, horizon_minutes=horizon_minutes)
    except KeyError:
        return ForecastReport(
            zone_id=zone_id,
            horizon_minutes=horizon_minutes,
            predicted_occupancy=0,
            predicted_density=0.0,
            predicted_score=0,
            recommendation="monitor",
        ).model_dump()
    score = raw["predicted_score"]
    rec: str
    if score < SCORE_INTERVENE_THRESHOLD:
        rec = "intervene"
    elif score < SCORE_MONITOR_THRESHOLD:
        rec = "monitor"
    else:
        rec = "hold"
    return ForecastReport(
        zone_id=raw["zone_id"],
        horizon_minutes=raw["horizon_minutes"],
        predicted_occupancy=raw["predicted_occupancy"],
        predicted_density=raw["predicted_density"],
        predicted_score=score,
        recommendation=rec,  # type: ignore[arg-type]  # literal narrowed by guards above
    ).model_dump()
