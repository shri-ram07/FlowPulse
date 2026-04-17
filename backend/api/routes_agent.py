"""Chat endpoints for the AttendeeAgent + OperationsAgent.

Staff-only routes require a valid JWT. Attendee chat is public read-only.
A stable `session_id` (generated once per PWA tab) is passed on every
attendee call so multi-turn memory survives.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.agents.attendee_agent import ask_attendee, reset_attendee_session
from backend.agents.operations_agent import propose_actions
from backend.security.auth import StaffToken, rate_limit, require_staff

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AttendeeQuery(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    location: str | None = Field(default=None, max_length=32)
    session_id: str | None = Field(default=None, max_length=64)


class ResetQuery(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)


@router.post("/attendee", dependencies=[Depends(rate_limit(60))])
async def attendee_ask(q: AttendeeQuery) -> dict:
    try:
        return await ask_attendee(q.message, location=q.location, session_id=q.session_id)
    except Exception as e:
        raise HTTPException(500, f"agent_error: {e}") from e


@router.post("/attendee/reset", dependencies=[Depends(rate_limit(30))])
async def attendee_reset(q: ResetQuery) -> dict:
    """Drop the cached conversation so the next message starts a new session."""
    reset_attendee_session(q.session_id)
    return {"ok": True, "session_id": q.session_id}


@router.post("/operations")
async def operations_plan(_user: StaffToken = Depends(require_staff)) -> dict:
    try:
        return await propose_actions()
    except Exception as e:
        raise HTTPException(500, f"agent_error: {e}") from e
