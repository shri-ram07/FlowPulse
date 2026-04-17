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

from backend.core.engine import CrowdFlowEngine

PHASES = [
    ("pre_match", 120),
    ("quarter_1", 120),
    ("halftime", 120),
    ("quarter_2", 120),
    ("exit", 120),
]


@dataclass
class SimState:
    phase: str
    elapsed: float
    chaos: float


class Simulator:
    def __init__(self, engine: CrowdFlowEngine, *, seed: int = 42) -> None:
        self.engine = engine
        self.rng = random.Random(seed)
        self.chaos = 0.0
        self._task: asyncio.Task | None = None
        self._start_ts = 0.0

    # --- lifecycle -----------------------------------------------------
    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._start_ts = time.monotonic()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def state(self) -> SimState:
        elapsed = time.monotonic() - self._start_ts if self._start_ts else 0.0
        return SimState(phase=self._phase_for(elapsed), elapsed=elapsed, chaos=self.chaos)

    def _phase_for(self, elapsed: float) -> str:
        t = 0.0
        for name, dur in PHASES:
            if elapsed < t + dur:
                return name
            t += dur
        return "post"

    # --- main loop -----------------------------------------------------
    async def _run(self) -> None:
        try:
            while True:
                await self._step()
                await self.engine.tick()
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            return

    async def _step(self) -> None:
        phase = self.state().phase
        eng = self.engine
        z = eng.zones
        r = self.rng

        # Base background noise: small cross-movement everywhere.
        if r.random() < 0.5:
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
                target_conc = {"seat_n": "con_n", "seat_s": "con_s",
                               "seat_e": "con_e", "seat_w": "con_w"}[seat]
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
            for conc, seat in (("con_n","seat_n"),("con_s","seat_s"),
                               ("con_e","seat_e"),("con_w","seat_w")):
                await self._route(conc, seat, r.randint(25, 50))

        elif phase == "exit":
            # Exit surge: seating -> concourses -> gates -> exit ramp.
            for seat in ("seat_n","seat_s","seat_e","seat_w"):
                target = {"seat_n":"con_n","seat_s":"con_s",
                          "seat_e":"con_e","seat_w":"con_w"}[seat]
                await self._route(seat, target, r.randint(80, 140))
            # Everyone funnels to south ramp (deliberately creates pressure).
            await self._route("con_n", "con_s", r.randint(40, 70))
            await self._route("con_e", "con_s", r.randint(30, 50))
            await self._route("con_w", "con_s", r.randint(30, 50))
            await self._route("con_s", "exit_ramp", r.randint(60, 120))
            await self._route("exit_ramp", "gate_g", r.randint(40, 90))

        # Chaos injection — random surge somewhere.
        if self.chaos > 0 and r.random() < self.chaos:
            target = r.choice(list(z.values()))
            await self._enter(target.id, r.randint(30, 80))

    # --- helpers -------------------------------------------------------
    async def _enter(self, zone_id: str, n: int) -> None:
        await self.engine.enter(zone_id, n)

    async def _route(self, src: str, dst: str, n: int) -> None:
        if self.engine.zones[src].occupancy <= 0:
            return
        await self.engine.move(src, dst, n)

    def _is_reachable(self, a: str, b: str) -> bool:
        return any(e.to == b for e in self.engine.zones[a].neighbors)

    def _nearest_concourse(self, zone_id: str) -> str:
        mapping = {
            "food_1": "con_n", "food_2": "con_n",
            "food_3": "con_w", "food_4": "con_e",
            "food_5": "con_s", "food_6": "con_s",
            "rest_1": "con_w", "rest_2": "con_w", "rest_3": "con_w",
            "rest_4": "con_e", "rest_5": "con_e", "rest_6": "con_e",
        }
        return mapping.get(zone_id, "con_n")

    async def _drain_gates_into_concourses(self, *, soft: bool = False) -> None:
        factor = 0.25 if soft else 0.55
        for gid in ("gate_a","gate_b","gate_c","gate_d","gate_e","gate_f","gate_g"):
            z = self.engine.zones[gid]
            n = max(0, int(z.occupancy * factor))
            if n:
                target = "con_n" if gid in ("gate_a","gate_b","gate_c","gate_d") else "con_s"
                await self.engine.move(gid, target, n)
