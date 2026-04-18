"""Event generator that drives the demo stadium.

Runs a compressed match cycle in ~10 real minutes:
    pre_match (0-2 min)  : entry surge at gates, filling seating.
    quarter_1 (2-4 min)  : steady seating, light food/restroom usage.
    halftime  (4-6 min)  : heavy food-court + restroom rush, concourse churn.
    quarter_2 (6-8 min)  : back to seating.
    exit      (8-10 min) : exit surge to gates + ramp.

The `chaos` slider (0..1) injects extra random spikes for live demos.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import time
from dataclasses import dataclass
from typing import Final

from backend.core.engine import CrowdFlowEngine

# ---- Phase timing ----------------------------------------------------------
# Each phase lasts PHASE_DURATION_SEC — 2 minutes in demo-compressed time.
# The full match cycle = 5 * PHASE_DURATION_SEC = 10 minutes.
PHASE_DURATION_SEC: Final[int] = 120

PHASES: Final[list[tuple[str, int]]] = [
    ("pre_match", PHASE_DURATION_SEC),
    ("quarter_1", PHASE_DURATION_SEC),
    ("halftime", PHASE_DURATION_SEC),
    ("quarter_2", PHASE_DURATION_SEC),
    ("exit", PHASE_DURATION_SEC),
]

# ---- Gate-drain rates (fraction of occupancy moved to concourses per step) --
GATE_DRAIN_FACTOR_NORMAL: Final[float] = 0.55
GATE_DRAIN_FACTOR_SOFT: Final[float] = 0.25

# ---- Simulator inner loop tick ---------------------------------------------
STEP_INTERVAL_SEC: Final[float] = 1.0

# ---- Background noise probability (per step) -------------------------------
BACKGROUND_MOVE_PROB: Final[float] = 0.5

# ---- Chaos slider — spike magnitude bounds (people injected per chaos roll)
CHAOS_SPIKE_MIN: Final[int] = 30
CHAOS_SPIKE_MAX: Final[int] = 80


@dataclass
class SimState:
    phase: str
    elapsed: float
    chaos: float


class Simulator:
    """Drives a compressed 10-minute match cycle over the Crowd Flow Engine.

    Not thread-safe — meant to run on a single asyncio event loop. Lifecycle
    is start/stop; each tick injects phase-appropriate inflow/outflow into the
    engine, optionally amplified by the `chaos` slider.
    """

    def __init__(self, engine: CrowdFlowEngine, *, seed: int = 42) -> None:
        """Bind to an engine instance with a seeded RNG for reproducibility.

        Args:
            engine: The Crowd Flow Engine whose zones will be mutated.
            seed: Seed for the internal `random.Random` so demo runs are
                repeatable when `chaos` = 0.
        """
        self.engine = engine
        self.rng = random.Random(seed)
        self.chaos = 0.0
        self._task: asyncio.Task[None] | None = None
        self._start_ts = 0.0

    # --- lifecycle -----------------------------------------------------
    def start(self) -> None:
        """Spawn the background simulation task.

        Idempotent — calling start() on an already-running simulator is a no-op.
        """
        if self._task and not self._task.done():
            return
        self._start_ts = time.monotonic()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Cancel the background task and wait for it to exit cleanly.

        Safe to call when the simulator is not running.
        """
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def state(self) -> SimState:
        """Return the current phase, elapsed seconds, and chaos level.

        Used by the `/api/sim/state` route so the frontend can show a phase
        badge + chaos slider position.
        """
        elapsed = time.monotonic() - self._start_ts if self._start_ts else 0.0
        return SimState(phase=self._phase_for(elapsed), elapsed=elapsed, chaos=self.chaos)

    def _phase_for(self, elapsed: float) -> str:
        """Map elapsed seconds to the current phase name.

        Args:
            elapsed: Seconds since the simulator started.

        Returns:
            The phase name (`pre_match`, `quarter_1`, `halftime`, `quarter_2`,
            `exit`) or `post` once the full cycle has finished.
        """
        t = 0.0
        for name, dur in PHASES:
            if elapsed < t + dur:
                return name
            t += dur
        return "post"

    # --- main loop -----------------------------------------------------
    async def _run(self) -> None:
        """Main simulation loop — one step + engine tick per STEP_INTERVAL_SEC.

        Catches `asyncio.CancelledError` so `stop()` shuts down without noise.
        """
        try:
            while True:
                await self._step()
                await self.engine.tick()
                await asyncio.sleep(STEP_INTERVAL_SEC)
        except asyncio.CancelledError:
            return

    async def _step(self) -> None:
        """Inject one step of phase-appropriate inflow/outflow into the engine.

        Each phase has its own crowd pattern (see module docstring). The
        `chaos` slider (0..1) additionally injects a random surge with
        probability `chaos` on every step.
        """
        phase = self.state().phase
        eng = self.engine
        z = eng.zones
        r = self.rng

        # Base background noise: small cross-movement everywhere.
        if r.random() < BACKGROUND_MOVE_PROB:
            a, b = r.sample(list(z.values()), 2)
            if a.occupancy > 2 and self._is_reachable(a.id, b.id):
                await eng.move(a.id, b.id, n=r.randint(1, 3))

        if phase == "pre_match":
            # Heavy entry surge — Gates A & B get hit hardest.
            await self._enter("gate_a", r.randint(25, 45))
            await self._enter("gate_b", r.randint(30, 55))
            await self._enter("gate_c", r.randint(8, 18))
            await self._enter("gate_d", r.randint(5, 12))
            await self._drain_gates_into_concourses()

        elif phase == "quarter_1":
            await self._drain_gates_into_concourses(soft=True)
            await self._route("con_n", "seat_n", r.randint(20, 40))
            await self._route("con_s", "seat_s", r.randint(20, 40))
            await self._route("con_w", "seat_w", r.randint(15, 25))
            await self._route("con_e", "seat_e", r.randint(15, 25))

        elif phase == "halftime":
            # Mass movement: seating -> concourses -> food/restrooms.
            for seat in ("seat_n", "seat_s", "seat_e", "seat_w"):
                target_conc = {"seat_n": "con_n", "seat_s": "con_s", "seat_e": "con_e", "seat_w": "con_w"}[
                    seat
                ]
                await self._route(seat, target_conc, r.randint(80, 130))
            # Concourses overflow to food courts & restrooms — deliberately lopsided.
            await self._route("con_n", "food_1", r.randint(25, 40))
            await self._route("con_n", "food_2", r.randint(30, 50))
            await self._route("con_s", "food_5", r.randint(15, 25))
            await self._route("con_s", "food_6", r.randint(10, 20))
            await self._route("con_w", "rest_1", r.randint(10, 18))
            await self._route("con_w", "rest_2", r.randint(10, 18))
            await self._route("con_e", "rest_4", r.randint(10, 18))
            await self._route("con_e", "rest_5", r.randint(10, 18))
            # Food courts serve people back to concourses (outflow).
            for fc in ("food_1", "food_2", "food_5", "food_6"):
                await self._route(fc, self._nearest_concourse(fc), r.randint(3, 8))
            for rr in ("rest_1", "rest_2", "rest_4", "rest_5"):
                await self._route(rr, self._nearest_concourse(rr), r.randint(8, 14))

        elif phase == "quarter_2":
            for conc, seat in (
                ("con_n", "seat_n"),
                ("con_s", "seat_s"),
                ("con_e", "seat_e"),
                ("con_w", "seat_w"),
            ):
                await self._route(conc, seat, r.randint(25, 50))

        elif phase == "exit":
            # Exit surge: seating -> concourses -> gates -> exit ramp.
            for seat in ("seat_n", "seat_s", "seat_e", "seat_w"):
                target = {"seat_n": "con_n", "seat_s": "con_s", "seat_e": "con_e", "seat_w": "con_w"}[seat]
                await self._route(seat, target, r.randint(80, 140))
            # Everyone funnels to south ramp (deliberately creates pressure).
            await self._route("con_n", "con_s", r.randint(40, 70))
            await self._route("con_e", "con_s", r.randint(30, 50))
            await self._route("con_w", "con_s", r.randint(30, 50))
            await self._route("con_s", "exit_ramp", r.randint(60, 120))
            await self._route("exit_ramp", "gate_g", r.randint(40, 90))

        # Chaos injection — random surge somewhere.
        if self.chaos > 0 and r.random() < self.chaos:
            chaos_zone = r.choice(list(z.values()))
            await self._enter(chaos_zone.id, r.randint(CHAOS_SPIKE_MIN, CHAOS_SPIKE_MAX))

    # --- helpers -------------------------------------------------------
    async def _enter(self, zone_id: str, n: int) -> None:
        """Convenience wrapper: n people enter `zone_id`."""
        await self.engine.enter(zone_id, n)

    async def _route(self, src: str, dst: str, n: int) -> None:
        """Move up to n people from `src` to `dst`, no-op when src is empty."""
        if self.engine.zones[src].occupancy <= 0:
            return
        await self.engine.move(src, dst, n)

    def _is_reachable(self, a: str, b: str) -> bool:
        """Return True when zone `a` has a directed edge to zone `b`."""
        return any(e.to == b for e in self.engine.zones[a].neighbors)

    def _nearest_concourse(self, zone_id: str) -> str:
        """Return the concourse a food/restroom zone drains back into.

        Used during halftime outflow so served customers return to the nearest
        concourse rather than teleporting back to seating.
        """
        mapping = {
            "food_1": "con_n",
            "food_2": "con_n",
            "food_3": "con_w",
            "food_4": "con_e",
            "food_5": "con_s",
            "food_6": "con_s",
            "rest_1": "con_w",
            "rest_2": "con_w",
            "rest_3": "con_w",
            "rest_4": "con_e",
            "rest_5": "con_e",
            "rest_6": "con_e",
        }
        return mapping.get(zone_id, "con_n")

    async def _drain_gates_into_concourses(self, *, soft: bool = False) -> None:
        """Move a fraction of every gate's occupants into their concourse.

        Args:
            soft: When True, uses GATE_DRAIN_FACTOR_SOFT (25%) — used during
                quiet phases. Default False uses GATE_DRAIN_FACTOR_NORMAL (55%)
                for the pre-match surge.
        """
        factor = GATE_DRAIN_FACTOR_SOFT if soft else GATE_DRAIN_FACTOR_NORMAL
        for gid in ("gate_a", "gate_b", "gate_c", "gate_d", "gate_e", "gate_f", "gate_g"):
            z = self.engine.zones[gid]
            n = max(0, int(z.occupancy * factor))
            if n:
                target = "con_n" if gid in ("gate_a", "gate_b", "gate_c", "gate_d") else "con_s"
                await self.engine.move(gid, target, n)
