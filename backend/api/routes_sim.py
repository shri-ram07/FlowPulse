"""Simulator control — staff-only except GET /state which the attendee map reads."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.runtime import get_simulator
from backend.security.auth import StaffToken, rate_limit, require_staff

router = APIRouter(prefix="/api/sim", tags=["sim"])


class ChaosPayload(BaseModel):
    chaos: float = Field(ge=0.0, le=1.0)


@router.get("/state", dependencies=[Depends(rate_limit(240))])
async def state() -> dict:
    s = get_simulator().state()
    return {"phase": s.phase, "elapsed": round(s.elapsed, 1), "chaos": s.chaos}


@router.post("/start")
async def start(_user: StaffToken = Depends(require_staff)) -> dict:
    get_simulator().start()
    return {"ok": True}


@router.post("/stop")
async def stop(_user: StaffToken = Depends(require_staff)) -> dict:
    await get_simulator().stop()
    return {"ok": True}


@router.post("/chaos")
async def chaos(p: ChaosPayload, _user: StaffToken = Depends(require_staff)) -> dict:
    sim = get_simulator()
    sim.chaos = p.chaos
    return {"ok": True, "chaos": sim.chaos}
