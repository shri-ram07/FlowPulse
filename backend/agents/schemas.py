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
    "open_gate",
    "push_notification",
    "dispatch_staff",
    "redirect",
    "monitor",
]


class OpsAction(BaseModel):
    """A single intervention the Orchestrator proposes."""

    type: ActionType
    target: str = Field(min_length=1, max_length=64, description="Zone id the action applies to.")
    eta_minutes: int = Field(ge=0, le=30, description="Expected time-to-effect in minutes.")
    rationale: str = Field(
        min_length=1, max_length=240, description="One-sentence justification grounded in a tool result."
    )


class OpsPlan(BaseModel):
    """Structured response the Orchestrator returns to the Ops console."""

    situation: str = Field(min_length=1, max_length=240, description="One-sentence summary of current state.")
    root_cause: str = Field(
        min_length=1, max_length=240, description="One-sentence cause statement grounded in live numbers."
    )
    actions: list[OpsAction] = Field(
        default_factory=list,
        max_length=4,
        description="Ordered list of up to 4 interventions; each must cite a tool result.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.8,
        description="Model's self-reported confidence in the plan, 0.0-1.0.",
    )


# ----------------------------------------------------------------------------
# Forecast — ForecastAgent sub-call.
# ----------------------------------------------------------------------------


class ForecastReport(BaseModel):
    """Output of the ForecastAgent — strictly grounded in engine-forecast numbers."""

    zone_id: str = Field(description="The zone being forecast.")
    horizon_minutes: int = Field(
        ge=1,
        le=15,
        description="Minutes into the future the prediction covers.",
    )
    predicted_occupancy: int = Field(
        ge=0,
        description="Occupancy predicted by the engine at horizon.",
    )
    predicted_density: float = Field(
        ge=0.0,
        description="Predicted density (occupancy / capacity).",
    )
    predicted_score: int = Field(
        ge=0,
        le=100,
        description="Predicted Crowd Flow Score at horizon (0-100, higher is healthier).",
    )
    recommendation: Literal["hold", "monitor", "intervene"] = Field(
        default="monitor",
        description=(
            "Action band derived from predicted_score: < "
            "SCORE_INTERVENE_THRESHOLD -> intervene, "
            "< SCORE_MONITOR_THRESHOLD -> monitor, otherwise hold."
        ),
    )


# ----------------------------------------------------------------------------
# Route — RoutingAgent sub-call.
# ----------------------------------------------------------------------------


class RouteReply(BaseModel):
    """Output of the RoutingAgent — a picked destination plus a walking route."""

    start: str = Field(description="Source zone id (may be empty when no start was provided).")
    dest: str = Field(description="Chosen destination zone id.")
    path: list[str] = Field(
        default_factory=list,
        description="Ordered list of zone ids walked from start to dest.",
    )
    eta_seconds: int = Field(ge=0, default=0, description="Total walking time in seconds.")
    score_avg: int = Field(
        ge=0,
        le=100,
        default=0,
        description="Mean Crowd Flow Score along the path (higher = more comfortable walk).",
    )
    mode: Literal["time", "comfort"] = Field(
        default="comfort",
        description="Route optimisation mode used to produce `path`.",
    )
    error: str | None = Field(
        default=None,
        description="Non-null when no valid route was found (e.g. 'no_food_zones').",
    )


# ----------------------------------------------------------------------------
# Safety — SafetyAgent risk report.
# ----------------------------------------------------------------------------


class SafetyFlag(BaseModel):
    """A single flagged zone in a SafetyReport."""

    zone_id: str = Field(description="Zone currently at elevated risk.")
    level: Literal["calm", "building", "congested", "critical"] = Field(
        description="Congestion band — only `congested` / `critical` should be flagged.",
    )
    score: int = Field(ge=0, le=100, description="Current Crowd Flow Score.")
    reason: str = Field(
        max_length=240,
        description="Human-readable cause citing density / inflow / outflow / trend.",
    )


class SafetyReport(BaseModel):
    """Output of the SafetyAgent — venue-wide risk triage for the Orchestrator."""

    critical_count: int = Field(
        ge=0,
        description="Count of zones with level=critical at report time.",
    )
    congested_count: int = Field(
        ge=0,
        description="Count of zones with level=congested at report time.",
    )
    flags: list[SafetyFlag] = Field(
        default_factory=list,
        max_length=10,
        description="Up to 10 worst-score zones, sorted ascending by score.",
    )


# ----------------------------------------------------------------------------
# Comms — CommsAgent draft output.
# ----------------------------------------------------------------------------


class CommsDraft(BaseModel):
    """Output of the CommsAgent — drafted copy for a public-facing channel."""

    channel: Literal["push", "tannoy", "digital_signage"] = Field(
        description=(
            "Delivery channel: `push` (FCM), `tannoy` (stadium PA text), "
            "`digital_signage` (big-screen banner)."
        ),
    )
    audience_zone_id: str = Field(description="Zone the message targets — defines the audience.")
    title: str = Field(
        min_length=1,
        max_length=80,
        description="Short headline; first 80 chars shown on tickers + push previews.",
    )
    body: str = Field(
        min_length=1,
        max_length=240,
        description="Main message copy; push notifications truncate at ~150 chars on Android.",
    )
    severity: Literal["info", "warn", "critical"] = Field(
        default="info",
        description="Drives iconography/colour and push priority on the client.",
    )
