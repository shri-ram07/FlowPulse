"""Simulator control — staff-only except GET /state which the attendee map reads."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.core.logging import audit
from backend.runtime import get_simulator
from backend.security.auth import (
    RATE_LIMIT_READ_PER_MIN,
    StaffToken,
    rate_limit,
    require_staff,
)

router = APIRouter(prefix="/api/sim", tags=["sim"])


class ChaosPayload(BaseModel):
    chaos: float = Field(ge=0.0, le=1.0)


@router.get("/state", dependencies=[Depends(rate_limit(RATE_LIMIT_READ_PER_MIN))])
async def state() -> dict[str, float | str]:
    """Return the simulator's current `{phase, elapsed, chaos}`."""
    s = get_simulator().state()
    return {"phase": s.phase, "elapsed": round(s.elapsed, 1), "chaos": s.chaos}


@router.post("/start")
async def start(user: StaffToken = Depends(require_staff)) -> dict[str, bool]:
    """Start the simulator (idempotent). Requires staff auth."""
    get_simulator().start()
    audit("sim.start", actor=user.sub, action="simulator_start", target="simulator")
    return {"ok": True}


@router.post("/stop")
async def stop(user: StaffToken = Depends(require_staff)) -> dict[str, bool]:
    """Stop the simulator (idempotent). Requires staff auth."""
    await get_simulator().stop()
    audit("sim.stop", actor=user.sub, action="simulator_stop", target="simulator")
    return {"ok": True}


@router.post("/chaos")
async def chaos(
    p: ChaosPayload,
    user: StaffToken = Depends(require_staff),
) -> dict[str, bool | float]:
    """Set the chaos slider (0..1) — probability of random surge per step."""
    sim = get_simulator()
    sim.chaos = p.chaos
    audit("sim.chaos", actor=user.sub, action="set_chaos", target="simulator", chaos=sim.chaos)
    return {"ok": True, "chaos": sim.chaos}
