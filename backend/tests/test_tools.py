import pytest

from backend.agents import tools
from backend.agents.operations_agent import propose_actions
from backend.runtime import get_engine


@pytest.mark.asyncio
async def test_get_zone_state_returns_live_data():
    eng = get_engine()
    await eng.enter("food_1", 50)
    s = tools.get_zone_state("food_1")
    assert s["occupancy"] == 50
    assert 0 <= s["score"] <= 100


@pytest.mark.asyncio
async def test_get_all_zones_filters_by_kind():
    zones = tools.get_all_zones(kind="food")
    assert zones and all(z["kind"] == "food" for z in zones)


@pytest.mark.asyncio
async def test_forecast_zone_shape():
    f = tools.forecast_zone("gate_a", horizon_minutes=3)
    for k in ("predicted_occupancy", "predicted_density", "predicted_score"):
        assert k in f


@pytest.mark.asyncio
async def test_suggest_redirect_reports_headroom():
    eng = get_engine()
    await eng.enter("food_1", 170)  # > capacity
    r = tools.suggest_redirect("food_1", "food_6")
    assert r["redirect_count"] > 0
    assert r["expected_relief_pct"] > 0


@pytest.mark.asyncio
async def test_dispatch_alert_registers_alert():
    r = tools.dispatch_alert("food_2", "test message", severity="warn")
    assert r["delivered"] is True
    assert any(a.zone_id == "food_2" for a in get_engine().alerts)


@pytest.mark.asyncio
async def test_ops_plan_is_grounded():
    # Create congestion so the plan should react.
    eng = get_engine()
    await eng.enter("food_2", int(eng.zones["food_2"].capacity * 1.05))
    await eng.tick()
    plan = await propose_actions()
    assert "situation" in plan
    assert plan["actions"], "plan must contain at least one action"
    assert all("rationale" in a for a in plan["actions"])
