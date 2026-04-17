"""Typed output schemas for every FlowPulse agent.

These Pydantic models double as:
  - The `response_schema` passed to Gemini via ADK's GenerationConfig —
    Gemini is forced to emit JSON matching the schema.
  - The public contract for `/api/agent/*` endpoints (they're the return types
    in OpenAPI).
  - The validation layer for fallback-path outputs.

Keep them small and stable — schema drift between model + engine breaks the
grounded-tool discipline.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------------
# Ops — action plans emitted by the Orchestrator.
# ----------------------------------------------------------------------------

ActionType = Literal[
    "open_gate", "push_notification", "dispatch_staff", "redirect", "monitor",
]


class OpsAction(BaseModel):
    """A single intervention the Orchestrator proposes."""
    type: ActionType
    target: str = Field(min_length=1, max_length=64,
                        description="Zone id the action applies to.")
    eta_minutes: int = Field(ge=0, le=30,
                             description="Expected time-to-effect in minutes.")
    rationale: str = Field(min_length=1, max_length=240,
                           description="One-sentence justification grounded in a tool result.")


class OpsPlan(BaseModel):
    """Structured response the Orchestrator returns to the Ops console."""
    situation: str = Field(min_length=1, max_length=240,
                           description="One-sentence summary of current state.")
    root_cause: str = Field(min_length=1, max_length=240,
                            description="One-sentence cause statement grounded in live numbers.")
    actions: list[OpsAction] = Field(default_factory=list, max_length=4)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


# ----------------------------------------------------------------------------
# Forecast — ForecastAgent sub-call.
# ----------------------------------------------------------------------------


class ForecastReport(BaseModel):
    zone_id: str
    horizon_minutes: int = Field(ge=1, le=15)
    predicted_occupancy: int = Field(ge=0)
    predicted_density: float = Field(ge=0.0)
    predicted_score: int = Field(ge=0, le=100)
    recommendation: Literal["hold", "monitor", "intervene"] = "monitor"


# ----------------------------------------------------------------------------
# Route — RoutingAgent sub-call.
# ----------------------------------------------------------------------------


class RouteReply(BaseModel):
    start: str
    dest: str
    path: list[str] = Field(default_factory=list)
    eta_seconds: int = Field(ge=0, default=0)
    score_avg: int = Field(ge=0, le=100, default=0)
    mode: Literal["time", "comfort"] = "comfort"
    error: str | None = None


# ----------------------------------------------------------------------------
# Safety — SafetyAgent risk report.
# ----------------------------------------------------------------------------


class SafetyFlag(BaseModel):
    zone_id: str
    level: Literal["calm", "building", "congested", "critical"]
    score: int = Field(ge=0, le=100)
    reason: str = Field(max_length=240)


class SafetyReport(BaseModel):
    critical_count: int = Field(ge=0)
    congested_count: int = Field(ge=0)
    flags: list[SafetyFlag] = Field(default_factory=list, max_length=10)


# ----------------------------------------------------------------------------
# Comms — CommsAgent draft output.
# ----------------------------------------------------------------------------


class CommsDraft(BaseModel):
    channel: Literal["push", "tannoy", "digital_signage"]
    audience_zone_id: str
    title: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=240)
    severity: Literal["info", "warn", "critical"] = "info"
