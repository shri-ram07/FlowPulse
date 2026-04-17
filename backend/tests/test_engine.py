import pytest

from backend.runtime import get_engine


@pytest.mark.asyncio
async def test_enter_and_exit_balance():
    eng = get_engine()
    await eng.enter("gate_a", 50)
    assert eng.zones["gate_a"].occupancy == 50
    await eng.exit("gate_a", 10)
    assert eng.zones["gate_a"].occupancy == 40


@pytest.mark.asyncio
async def test_move_preserves_headcount():
    eng = get_engine()
    await eng.enter("gate_a", 30)
    await eng.move("gate_a", "con_n", 20)
    assert eng.zones["gate_a"].occupancy == 10
    assert eng.zones["con_n"].occupancy == 20


@pytest.mark.asyncio
async def test_tick_updates_flow_rates():
    eng = get_engine()
    await eng.enter("gate_a", 40)
    payload = await eng.tick()
    assert payload["type"] == "tick"
    assert any(z["inflow_per_min"] > 0 for z in payload["zones"] if z["id"] == "gate_a")


@pytest.mark.asyncio
async def test_snapshot_shape():
    eng = get_engine()
    s = eng.snapshot("food_1")
    for key in ("id","name","kind","capacity","occupancy","density","score","level","x","y"):
        assert key in s
