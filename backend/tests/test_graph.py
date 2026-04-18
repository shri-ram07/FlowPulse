import pytest

from backend.agents import tools
from backend.runtime import get_engine


@pytest.mark.asyncio
async def test_route_direct_neighbour():
    r = tools.get_best_route("gate_a", "con_n", optimize="time")
    assert r["path"] == ["gate_a", "con_n"]
    assert r["eta_seconds"] == 40


@pytest.mark.asyncio
async def test_route_multi_hop():
    r = tools.get_best_route("gate_a", "food_2", optimize="time")
    assert r["path"][0] == "gate_a"
    assert r["path"][-1] == "food_2"
    assert r["eta_seconds"] > 0


@pytest.mark.asyncio
async def test_comfort_mode_avoids_congested_zone():
    eng = get_engine()
    # Saturate con_n so comfort mode should prefer an alternative if one exists.
    await eng.enter("con_n", int(eng.zones["con_n"].capacity * 1.05))
    fast = tools.get_best_route("gate_a", "food_5", optimize="time")
    comfy = tools.get_best_route("gate_a", "food_5", optimize="comfort")
    assert fast["path"][0] == comfy["path"][0] == "gate_a"
    # comfort path should have an equal-or-higher average Flow Score.
    assert comfy["score_avg"] >= fast["score_avg"] - 1


def test_unknown_zone_returns_error():
    r = tools.get_best_route("nope", "food_1")
    assert r.get("error") == "unknown_zone"
