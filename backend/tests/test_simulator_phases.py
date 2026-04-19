"""Simulator — end-to-end phase behaviour.

Exercises the 5-phase match cycle (`pre_match`, `quarter_1`, `halftime`,
`quarter_2`, `exit`) by fast-forwarding the simulator clock and asserting
the macro shape of the resulting engine state changes.
"""

from __future__ import annotations

import pytest

from backend.runtime import get_engine, get_simulator


@pytest.mark.asyncio
async def test_phase_transitions_cover_every_phase() -> None:
    sim = get_simulator()
    # Fast-forward by manipulating _start_ts; for each phase, call the step
    # helper directly and assert the sim reports the expected phase name.
    import time as _time

    expected = ["pre_match", "quarter_1", "halftime", "quarter_2", "exit"]
    for i, name in enumerate(expected):
        # Move "start" back so elapsed falls inside this phase window.
        sim._start_ts = _time.monotonic() - (i * 120 + 60)  # 60s into phase i
        assert sim.state().phase == name


@pytest.mark.asyncio
async def test_pre_match_phase_drives_gate_inflow() -> None:
    sim = get_simulator()
    eng = get_engine()

    import time as _time

    sim._start_ts = _time.monotonic() - 30  # 30s into pre_match
    total_before = sum(z.occupancy for z in eng.zones.values())
    await sim._step()
    total_now = sum(z.occupancy for z in eng.zones.values())
    # Entries happen at gates; some drain into concourses during the same
    # step, but the NET venue population must have grown.
    assert total_now > total_before


@pytest.mark.asyncio
async def test_halftime_moves_seating_to_concourses() -> None:
    sim = get_simulator()
    eng = get_engine()
    import time as _time

    # Seed: populate seating so halftime has something to move.
    for zid in ("seat_n", "seat_s", "seat_e", "seat_w"):
        await eng.enter(zid, 500)

    seats_before = sum(eng.zones[z].occupancy for z in ("seat_n", "seat_s", "seat_e", "seat_w"))
    conc_before = sum(eng.zones[z].occupancy for z in ("con_n", "con_s", "con_e", "con_w"))

    sim._start_ts = _time.monotonic() - (2 * 120 + 30)  # 30s into halftime
    assert sim.state().phase == "halftime"
    await sim._step()

    seats_after = sum(eng.zones[z].occupancy for z in ("seat_n", "seat_s", "seat_e", "seat_w"))
    conc_after = sum(eng.zones[z].occupancy for z in ("con_n", "con_s", "con_e", "con_w"))

    assert seats_after < seats_before  # seating depleted
    assert conc_after > conc_before  # concourse filled


@pytest.mark.asyncio
async def test_chaos_slider_increases_entries() -> None:
    sim = get_simulator()
    eng = get_engine()
    import time as _time

    sim.chaos = 1.0  # guaranteed inject each step
    sim._start_ts = _time.monotonic() - 30

    total_before = sum(z.occupancy for z in eng.zones.values())
    for _ in range(3):
        await sim._step()
    total_after = sum(z.occupancy for z in eng.zones.values())
    assert total_after > total_before


@pytest.mark.asyncio
async def test_start_and_stop_lifecycle() -> None:
    sim = get_simulator()
    sim.start()
    assert sim._task is not None and not sim._task.done()
    await sim.stop()
    assert sim._task is None
