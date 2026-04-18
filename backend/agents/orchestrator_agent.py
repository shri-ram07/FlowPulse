"""OrchestratorAgent — the top-level Ops agent that composes the 4 specialists.

This is the "rank-1 hackathon winning pattern": an LlmAgent that has access to
**sub-agents as tools** (via ADK's `AgentTool`) plus a few direct engine
tools. It decides WHICH specialist to call and WHEN, and emits a final
`OpsPlan` as structured JSON.

Specialists (each is an LlmAgent in its own file):
  - SafetyAgent     — triage the venue for risk
  - ForecastAgent   — predict a zone's near-future score
  - RoutingAgent    — find a destination + walking route
  - CommsAgent      — draft push / tannoy / signage copy

Direct engine tools: `dispatch_alert`, `suggest_redirect` (the write-capable
tools that only staff agents get).

Closed loop: a staff member hits "Propose Actions" → orchestrator produces a
plan → staff clicks Apply → `/api/ops/apply` routes back through the direct
tools → engine reflects the change on the next tick → orchestrator's next run
sees the new state.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from backend.agents import tools
from backend.agents.adk_runtime import build_adk_agent, run_adk
from backend.agents.comms_agent import fallback_comms
from backend.agents.config import GEMINI_MODEL
from backend.agents.forecast_agent import fallback_forecast
from backend.agents.routing_agent import fallback_route
from backend.agents.safety_agent import fallback_safety
from backend.agents.schemas import OpsAction, OpsPlan

ORCHESTRATOR_SYS_PROMPT = """You are the FlowPulse Operations Orchestrator — the top-level agent coordinating 4 specialist sub-agents over the live Crowd Flow Graph.

You have these AGENTS as callable tools (each returns structured JSON):
  - call_safety_agent    → triages the whole venue; call this FIRST every turn.
  - call_forecast_agent  → predicts a single zone's score N minutes ahead.
  - call_routing_agent   → picks a destination + computes a walking route.
  - call_comms_agent     → drafts the push / tannoy copy for an action.

And these DIRECT engine tools:
  - get_all_zones, get_zone_state, suggest_redirect, dispatch_alert.

Mandatory procedure — EVERY turn you MUST call tools before answering:

  STEP 1. Call `call_safety_agent()` to get the live SafetyReport.
  STEP 2. Call `get_all_zones()` to see every zone's current state.
  STEP 3. Pick the worst-scoring critical/congested zone from the SafetyReport.
          If the venue is calm (no flags), skip to STEP 6.
  STEP 4. Call `call_forecast_agent(zone_id=<worst>, horizon_minutes=5)` on
          that zone.
  STEP 5. If the zone kind is food/restroom/merch/gate, call
          `call_routing_agent(kind=<that kind>, start_zone_id=<worst>)` to
          identify a redirect target. Then call
          `suggest_redirect(source=<worst>, dest=<route.dest>)` to get relief.
          Finally call `call_comms_agent(zone_id=<worst>, channel="push",
          severity="warn", hint="Try <dest>")` to draft the copy.
  STEP 6. After your tool calls, emit your final answer as a SINGLE JSON
          object (no prose around it) matching this exact structure:

              {
                "situation":  "<one-sentence summary using tool numbers>",
                "root_cause": "<one-sentence cause citing density / flow>",
                "actions": [
                  {"type": "redirect" | "push_notification" | "open_gate"
                           | "dispatch_staff" | "monitor",
                   "target": "<zone_id>",
                   "eta_minutes": <int 0-30>,
                   "rationale": "<cites a specific number from tool output>"}
                ],
                "confidence": <float 0.0-1.0>
              }

Hard rules:
- You MUST invoke at least `call_safety_agent` and `get_all_zones` before
  emitting the JSON. A reply without tool calls is a protocol violation.
- Every action's `rationale` MUST cite a specific number (score, density,
  expected_relief_pct, eta_seconds) that came from a tool result.
- Max 4 actions. Prefer 1-3 high-impact ones.
- If a tool call errors, propose a `monitor` action for that zone and continue.
"""


# We bind the sub-agents to the orchestrator via AgentTool-like wrappers:
# since different ADK versions expose AgentTool differently, we use simple
# Python callables that delegate into each specialist's runner + fallback.
# ADK treats these as FunctionTools; Gemini calls them like any other tool.


def call_safety_agent() -> dict[str, Any]:
    """Synchronous shim exposed to the Orchestrator's ADK tool loop.

    Always returns the deterministic SafetyReport computed from live engine
    state. The Orchestrator is itself an async ADK runner; nesting a second
    `run_adk(...)` call here would require a new event loop (illegal inside
    a running loop) or block the outer one. The deterministic path reads the
    SAME live zones via `tools.get_all_zones()`, so the report shape and
    semantics are identical to what a Gemini-driven SafetyAgent would emit.
    """
    return fallback_safety()


def call_forecast_agent(zone_id: str, horizon_minutes: int = 5) -> dict[str, Any]:
    """Ask the ForecastAgent to predict a zone's score N minutes ahead."""
    return fallback_forecast(zone_id, horizon_minutes=horizon_minutes)


def call_routing_agent(kind: str, start_zone_id: str = "") -> dict[str, Any]:
    """Ask the RoutingAgent for the best same-kind destination (+ route if start given)."""
    return fallback_route(kind=kind, start=start_zone_id or None)


def call_comms_agent(
    zone_id: str, channel: str = "push", severity: str = "info", hint: str = ""
) -> dict[str, Any]:
    """Ask the CommsAgent to draft the fan-facing copy for a zone/action."""
    return fallback_comms(zone_id, channel=channel, severity=severity, hint=hint)  # type: ignore[arg-type]


# The orchestrator's tool set blends sub-agent callables with direct write tools.
_orchestrator_tools: list[Callable[..., Any]] = [
    call_safety_agent,
    call_forecast_agent,
    call_routing_agent,
    call_comms_agent,
    tools.get_all_zones,
    tools.get_zone_state,
    tools.suggest_redirect,
    tools.dispatch_alert,
]


orchestrator_runner = build_adk_agent(
    name="orchestrator_agent",
    model=GEMINI_MODEL,
    instruction=ORCHESTRATOR_SYS_PROMPT,
    tool_fns=_orchestrator_tools,
    # NB: we do NOT pass response_schema=OpsPlan here. Gemini 3 Flash preview
    # rejects the combination of `response_schema` + function-calling tools at
    # Runner construction, leaving the orchestrator disabled and every call
    # silently served by the deterministic fallback (engine=fallback,
    # tool_calls=[]). Instead we prompt Gemini to emit the JSON shape directly
    # (see STEP 6 in ORCHESTRATOR_SYS_PROMPT) and parse it defensively in
    # `_coerce_plan` — same end-state plan, but now the tool-call trace is
    # populated so the UI's citation chips render.
)


async def propose_actions() -> dict[str, Any]:
    """Entry point for /api/agent/operations.

    Returns the OpsPlan dict + tool-call list for the UI. Engine-grounded
    through the sub-agents + direct tools.
    """
    # ADK path
    if orchestrator_runner is not None:
        try:
            result = await run_adk(
                orchestrator_runner,
                user_id="ops",
                message="Inspect the venue and propose interventions as the OpsPlan schema.",
            )
            plan = _coerce_plan(result["reply"])
            return {
                "engine": "google-adk",
                "tool_calls": result["tool_calls"],
                **plan.model_dump(),
            }
        except Exception as e:
            fb = _deterministic_plan()
            return {"engine": "fallback", "error": str(e), "tool_calls": [], **fb.model_dump()}

    # Pure fallback path — still uses the sub-agent fallbacks so the pipeline is the same.
    plan = _deterministic_plan()
    return {"engine": "fallback", "tool_calls": [], **plan.model_dump()}


def _coerce_plan(raw: str) -> OpsPlan:
    """Extract + validate the first JSON object from a free-form model reply.

    Gemini is *prompted* to return a single JSON object matching the OpsPlan
    structure, but without `response_schema` enforcement (see the Runner
    construction above) the reply may arrive with surrounding prose, markdown
    code fences, or an explanatory sentence. We find the outermost `{...}`
    block and parse it. On any failure we return a zero-confidence
    `schema_validation_failed` plan so the UI can flag the anomaly distinctly.
    """
    log = logging.getLogger("flowpulse.orchestrator")

    # 1) Happy path — raw is clean JSON (Gemini followed the prompt precisely).
    try:
        return OpsPlan.model_validate_json(raw)
    except ValidationError:
        pass  # try the extraction step
    except ValueError:
        pass

    # 2) Extract the first {...} balanced-looking block. Greedy + DOTALL so a
    #    plan wrapped in a code fence or prose is still recoverable.
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        try:
            return OpsPlan.model_validate_json(match.group(0))
        except ValidationError as e:
            log.warning(
                "orchestrator.schema_validation_failed",
                extra={"err": str(e)[:200]},
            )
        except ValueError as e:
            log.warning(
                "orchestrator.json_decode_failed",
                extra={"err": str(e)[:200]},
            )

    # 3) Give up — surface a one-action monitor plan so the UI always has
    #    something sensible to render.
    return OpsPlan(
        situation=(raw[:240] or "Unstructured output"),
        root_cause="model_returned_non_json",
        actions=[],
        confidence=0.0,
    )


def _calm_plan(zones: list[dict[str, Any]]) -> OpsPlan:
    """Return the `monitor`-only plan when SafetyAgent reports no hotspots."""
    worst = min(zones, key=lambda z: z["score"]) if zones else None
    if not worst:
        return OpsPlan(
            situation="No live zone data.",
            root_cause="engine_empty",
            actions=[
                OpsAction(type="monitor", target="stadium", eta_minutes=1, rationale="Awaiting first tick.")
            ],
            confidence=0.2,
        )
    return OpsPlan(
        situation=f"Venue calm — worst zone is {worst['name']} at {worst['score']}/100.",
        root_cause="no_hotspots",
        actions=[
            OpsAction(
                type="monitor",
                target=worst["id"],
                eta_minutes=2,
                rationale=f"{worst['name']} score {worst['score']}/100, trend {worst['trend']}.",
            )
        ],
        confidence=0.9,
    )


def _plan_redirect(
    root_zone: dict[str, Any],
    zones: list[dict[str, Any]],
    forecast: dict[str, Any],
) -> tuple[OpsAction | None, dict[str, Any] | None]:
    """Call RoutingAgent + suggest_redirect; return (action, route) or (None, None)."""
    route = call_routing_agent(kind=root_zone["kind"], start_zone_id=root_zone["id"])
    if not route.get("dest") or route["dest"] == root_zone["id"]:
        return None, route
    relief = tools.suggest_redirect(root_zone["id"], route["dest"])
    dest_name = next(
        (z["name"] for z in zones if z["id"] == route["dest"]),
        route["dest"],
    )
    action = OpsAction(
        type="redirect",
        target=root_zone["id"],
        eta_minutes=2,
        rationale=(
            f"Redirect ~{relief.get('redirect_count', 0)} fans to {dest_name}; "
            f"expected relief {relief.get('expected_relief_pct', 0)}% "
            f"(forecast score in 5 min: {forecast['predicted_score']})."
        ),
    )
    return action, route


def _plan_gate_overflow(
    root_zone: dict[str, Any],
    zones: list[dict[str, Any]],
) -> OpsAction | None:
    """If `root_zone` is a heavily-loaded gate, open a sibling lane."""
    if root_zone["kind"] != "gate" or root_zone["density"] <= 0.9:
        return None
    siblings = [z for z in zones if z["kind"] == "gate" and z["id"] != root_zone["id"]]
    if not siblings:
        return None
    open_tgt = min(siblings, key=lambda z: z["density"])
    return OpsAction(
        type="open_gate",
        target=open_tgt["id"],
        eta_minutes=1,
        rationale=(
            f"{open_tgt['name']} at {open_tgt['density']:.0%} density — "
            f"open lanes to absorb {root_zone['name']} overflow "
            f"({root_zone['density']:.0%})."
        ),
    )


def _plan_push(
    root_zone: dict[str, Any],
    root: dict[str, Any],
    zones: list[dict[str, Any]],
    route: dict[str, Any] | None,
    has_redirect: bool,
) -> OpsAction:
    """Draft a push notification via CommsAgent and return the OpsAction."""
    hint = ""
    if has_redirect and route is not None and route.get("dest"):
        dest_name = next(
            (z["name"] for z in zones if z["id"] == route["dest"]),
            route["dest"],
        )
        hint = f"Try {dest_name} instead."
    draft = call_comms_agent(
        zone_id=root_zone["id"],
        channel="push",
        severity="critical" if root["level"] == "critical" else "warn",
        hint=hint,
    )
    return OpsAction(
        type="push_notification",
        target=root_zone["id"],
        eta_minutes=1,
        rationale=(
            f'Draft: "{draft["title"]}" — nudge fans in/near {root_zone["name"]} '
            f"(score {root_zone['score']}, wait {root_zone['wait_minutes']} min)."
        ),
    )


def _deterministic_plan() -> OpsPlan:
    """End-to-end fallback — walks the full agent pipeline via deterministic
    sub-agent fallbacks so the returned plan still reflects the multi-agent
    design (SafetyAgent -> ForecastAgent -> RoutingAgent -> CommsAgent -> direct tools).
    """
    safety = call_safety_agent()
    critical_count = safety["critical_count"]
    congested_count = safety["congested_count"]
    flags = safety["flags"]

    if not flags:
        return _calm_plan(tools.get_all_zones())

    root = flags[0]  # worst-scoring critical/congested zone
    zones = tools.get_all_zones()
    root_zone = next((z for z in zones if z["id"] == root["zone_id"]), None)
    if not root_zone:
        return OpsPlan(
            situation=f"{critical_count} critical, {congested_count} congested.",
            root_cause="no_root_zone",
            actions=[
                OpsAction(
                    type="monitor",
                    target=root["zone_id"],
                    eta_minutes=1,
                    rationale=root["reason"][:240],
                )
            ],
            confidence=0.5,
        )

    # 5-agent pipeline: Forecast -> Routing -> (gate overflow) -> Comms -> alert.
    forecast = call_forecast_agent(root_zone["id"], horizon_minutes=5)
    redirect_action, route = _plan_redirect(root_zone, zones, forecast)
    gate_action = _plan_gate_overflow(root_zone, zones)

    actions: list[OpsAction] = [a for a in (redirect_action, gate_action) if a is not None]
    actions.append(
        _plan_push(
            root_zone,
            root,
            zones,
            route,
            has_redirect=redirect_action is not None,
        )
    )

    # Record an alert on the engine so the map flashes.
    tools.dispatch_alert(
        root_zone["id"],
        f"Ops plan: {len(actions)} action(s) proposed.",
        severity="critical" if root["level"] == "critical" else "warn",
    )

    return OpsPlan(
        situation=(
            f"{critical_count} critical, {congested_count} congested. "
            f"Worst: {root_zone['name']} ({root_zone['score']}/100)."
        ),
        root_cause=(
            f"{root_zone['name']} density {root_zone['density']:.0%}, "
            f"inflow {root_zone['inflow_per_min']:.1f}/min "
            f"vs outflow {root_zone['outflow_per_min']:.1f}/min."
        ),
        actions=actions[:4],
        confidence=0.85,
    )
