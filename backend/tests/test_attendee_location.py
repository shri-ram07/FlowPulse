"""AttendeeAgent — location context handling."""

from __future__ import annotations

import pytest

from backend.agents.attendee_agent import ask_attendee, build_contextual_message


def test_contextual_message_without_location_instructs_general_answer() -> None:
    msg = build_contextual_message("where should I grab food?", None)
    assert "NOT shared their location" in msg
    assert "where should I grab food?" in msg


def test_contextual_message_with_location_uses_zone_name() -> None:
    msg = build_contextual_message("quick snack", "food_1")
    # Should include both the id (for tool calls) and the human name (for clarity).
    assert "food_1" in msg
    assert "Food Court 1" in msg
    # Prompt nudges the model toward the routing sub-agent.
    assert "routing_sub_agent" in msg
    assert "quick snack" in msg


def test_contextual_message_tolerates_unknown_location() -> None:
    # If the frontend somehow sends a stale id, we still produce a prompt.
    msg = build_contextual_message("any food?", "does_not_exist")
    assert "does_not_exist" in msg


@pytest.mark.asyncio
async def test_attendee_fallback_includes_walking_time_when_location_set() -> None:
    # Fallback path is the one hit in tests (no GOOGLE_API_KEY).
    out = await ask_attendee("quick snack", location="gate_a")
    assert out["engine"] == "fallback"
    # The Concierge now delegates to routing_sub_agent which internally
    # calls get_best_route; the chip surfaces the sub-agent name.
    names = [c["name"] for c in out["tool_calls"]]
    assert "routing_sub_agent" in names
    # Walking time string should appear in the reply when location is provided.
    assert "min walk" in out["reply"]


@pytest.mark.asyncio
async def test_attendee_fallback_invites_location_when_missing() -> None:
    out = await ask_attendee("food?", location=None)
    assert out["engine"] == "fallback"
    assert "tap a zone" in out["reply"].lower() or "tap" in out["reply"].lower()
