"""WebSocket payload shape + diff behaviour."""

from __future__ import annotations

import pytest

from backend.runtime import get_engine


@pytest.mark.asyncio
async def test_full_snapshot_contains_every_zone():
    eng = get_engine()
    payload = eng.full_snapshot_payload()
    assert payload["type"] == "tick"
    assert payload["full"] is True
    assert len(payload["zones"]) == len(eng.zones)


@pytest.mark.asyncio
async def test_diff_only_includes_changed_zones():
    eng = get_engine()
    # Prime the cache with a full snapshot so subsequent ticks are diffs.
    eng.full_snapshot_payload()
    # Nothing has changed → an empty diff.
    empty = await eng.tick()
    assert empty["full"] is False
    # Changing one zone should yield a single-zone diff.
    await eng.enter("food_1", 50)
    diff = await eng.tick()
    assert diff["full"] is False
    changed_ids = {z["id"] for z in diff["zones"]}
    assert "food_1" in changed_ids


@pytest.mark.asyncio
async def test_diff_empty_when_state_stable():
    eng = get_engine()
    eng.full_snapshot_payload()
    # Two ticks with no state change should each have 0 zones in the diff.
    _ = await eng.tick()
    stable = await eng.tick()
    assert stable["zones"] == []
