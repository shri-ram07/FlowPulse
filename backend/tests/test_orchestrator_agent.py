"""Orchestrator + specialist-agent deterministic pipeline coverage."""

from __future__ import annotations

import pytest

from backend.agents.comms_agent import fallback_comms
from backend.agents.forecast_agent import fallback_forecast
from backend.agents.orchestrator_agent import (
    _deterministic_plan,
    call_comms_agent,
    call_forecast_agent,
    call_routing_agent,
    call_safety_agent,
    propose_actions,
)
from backend.agents.routing_agent import fallback_route
from backend.agents.safety_agent import fallback_safety
from backend.agents.schemas import CommsDraft, ForecastReport, OpsPlan, RouteReply, SafetyReport
from backend.runtime import get_engine

# ----- specialist fallback functions --------------------------------------


@pytest.mark.asyncio
async def test_safety_fallback_reports_shape() -> None:
    report = fallback_safety()
    SafetyReport.model_validate(report)  # schema check
    assert "critical_count" in report
    assert isinstance(report["flags"], list)


@pytest.mark.asyncio
async def test_forecast_fallback_respects_horizon_and_recommendation() -> None:
    r = fallback_forecast("food_1", horizon_minutes=3)
    ForecastReport.model_validate(r)
    assert r["horizon_minutes"] == 3
    assert r["recommendation"] in ("hold", "monitor", "intervene")


@pytest.mark.asyncio
async def test_forecast_fallback_unknown_zone_returns_safe_default() -> None:
    r = fallback_forecast("does_not_exist")
    assert r["predicted_score"] == 0
    assert r["recommendation"] == "monitor"


@pytest.mark.asyncio
async def test_routing_fallback_returns_error_when_no_zones_match() -> None:
    r = fallback_route(kind="nonsense", start=None)
    assert r["error"]


@pytest.mark.asyncio
async def test_routing_fallback_with_start_computes_comfort_route() -> None:
    eng = get_engine()
    await eng.enter("food_1", 140)  # make food_1 unattractive
    r = fallback_route(kind="food", start="gate_a")
    RouteReply.model_validate(r)
    assert r["start"] == "gate_a"
    assert r["dest"]
    assert r["eta_seconds"] >= 0


@pytest.mark.asyncio
async def test_comms_fallback_has_required_fields() -> None:
    d = fallback_comms("food_2", channel="push", severity="warn", hint="Try Food Court 5 instead.")
    CommsDraft.model_validate(d)
    assert d["channel"] == "push"
    assert d["severity"] == "warn"
    assert d["title"] and d["body"]


# ----- orchestrator pipeline ---------------------------------------------


@pytest.mark.asyncio
async def test_deterministic_plan_calm_venue_emits_monitor() -> None:
    plan_dict = _deterministic_plan().model_dump()
    OpsPlan.model_validate(plan_dict)
    assert plan_dict["actions"]
    # Calm venue should produce a monitor plan.
    assert plan_dict["actions"][0]["type"] == "monitor"


@pytest.mark.asyncio
async def test_deterministic_plan_with_hot_zone_proposes_push_notification() -> None:
    """Saturating food_2 above capacity should cause SafetyAgent to flag it and
    the orchestrator to emit at least one push_notification action."""
    eng = get_engine()
    # Saturate food_2 so safety_agent flags it (+10% over capacity).
    await eng.enter("food_2", int(eng.zones["food_2"].capacity * 1.1))
    await eng.tick()  # populate EWMA + risk flags
    plan = _deterministic_plan().model_dump()
    OpsPlan.model_validate(plan)
    types = [a["type"] for a in plan["actions"]]
    # A hot zone MUST produce a push; `monitor` would mean SafetyAgent didn't
    # flag the zone, which would be a regression.
    assert "push_notification" in types, f"Expected push_notification in actions for hot zone, got: {types}"


@pytest.mark.asyncio
async def test_propose_actions_returns_serialisable_plan() -> None:
    reply = await propose_actions()
    assert reply["engine"] in ("google-adk", "fallback")
    assert "situation" in reply and "root_cause" in reply
    assert isinstance(reply["actions"], list)


@pytest.mark.asyncio
async def test_agent_as_tool_callables_are_safe_to_invoke() -> None:
    # These are the Python functions the Orchestrator's ADK runner binds.
    s = call_safety_agent()
    assert "critical_count" in s
    f = call_forecast_agent("food_1", horizon_minutes=2)
    assert "predicted_score" in f
    r = call_routing_agent(kind="food", start_zone_id="gate_a")
    assert "dest" in r
    c = call_comms_agent("food_1", severity="info")
    assert "body" in c
