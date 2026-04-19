"""Chat endpoints for the AttendeeAgent + OperationsAgent.

Staff-only routes require a valid JWT. Attendee chat is public read-only.
A stable `session_id` (generated once per PWA tab) is passed on every
attendee call so multi-turn memory survives.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.agents.attendee_agent import ask_attendee, reset_attendee_session
from backend.agents.orchestrator_agent import propose_actions
from backend.security.auth import (
    RATE_LIMIT_AGENT_PER_MIN,
    RATE_LIMIT_FCM_PUSH_PER_MIN,
    StaffToken,
    rate_limit,
    require_staff,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AttendeeQuery(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    location: str | None = Field(default=None, max_length=32)
    session_id: str | None = Field(default=None, max_length=64)


class ResetQuery(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)


@router.post("/attendee", dependencies=[Depends(rate_limit(RATE_LIMIT_AGENT_PER_MIN))])
async def attendee_ask(q: AttendeeQuery) -> dict[str, Any]:
    """Ask the Attendee Concierge a question.

    Returns the agent's reply plus the chronological tool-call trace (used to
    render the UI citation chips). Preserves multi-turn memory via session_id.
    """
    try:
        return await ask_attendee(q.message, location=q.location, session_id=q.session_id)
    except Exception as e:
        raise HTTPException(500, f"agent_error: {e}") from e


@router.post("/attendee/reset", dependencies=[Depends(rate_limit(RATE_LIMIT_FCM_PUSH_PER_MIN))])
async def attendee_reset(q: ResetQuery) -> dict[str, bool | str]:
    """Drop the cached conversation so the next message starts a new session."""
    reset_attendee_session(q.session_id)
    return {"ok": True, "session_id": q.session_id}


@router.post("/operations")
async def operations_plan(_user: StaffToken = Depends(require_staff)) -> dict[str, Any]:
    """Run the 5-agent orchestration pipeline and return a typed `OpsPlan`."""
    try:
        return await propose_actions()
    except Exception as e:
        raise HTTPException(500, f"agent_error: {e}") from e
