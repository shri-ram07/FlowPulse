"""Session continuity + reset for the attendee agent.

ADK is not available under test (no GOOGLE_API_KEY), so we drive the fallback
path and rely on contract-level checks (session id accepted, reset endpoint
works, no crash). A dedicated unit test exercises the ADK session-cache helper
with a tiny stub runner.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.agents import adk_runtime
from backend.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def test_attendee_accepts_session_id(client: TestClient) -> None:
    r = client.post(
        "/api/agent/attendee",
        json={
            "message": "where to eat?",
            "session_id": "tab-abc123",
        },
    )
    assert r.status_code == 200
    assert r.json()["reply"]


def test_attendee_reset_endpoint(client: TestClient) -> None:
    r = client.post("/api/agent/attendee/reset", json={"session_id": "tab-abc123"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "session_id": "tab-abc123"}


def test_session_cache_reuses_across_calls() -> None:
    """run_adk should call create_session once per session_id, not per call."""

    class StubSessionService:
        def __init__(self):
            self.created = 0

        async def create_session(self, **_):
            self.created += 1
            return SimpleNamespace(id=f"s{self.created}")

    class StubRunner:
        def __init__(self):
            self.session_service = StubSessionService()

        async def run_async(self, **_):
            if False:
                yield  # make this a generator

    runner = StubRunner()
    # First call with a session_id creates a session.
    asyncio.get_event_loop().run_until_complete(adk_runtime.run_adk(runner, "u", "hi", session_id="sess-1"))
    # Second call with the same session_id must REUSE, not recreate.
    asyncio.get_event_loop().run_until_complete(
        adk_runtime.run_adk(runner, "u", "again", session_id="sess-1")
    )
    assert runner.session_service.created == 1

    # Reset clears the cache → next call creates a new session.
    adk_runtime.reset_session(runner, "sess-1")
    asyncio.get_event_loop().run_until_complete(
        adk_runtime.run_adk(runner, "u", "third", session_id="sess-1")
    )
    assert runner.session_service.created == 2

    # A call with no session_id is ephemeral — never cached.
    asyncio.get_event_loop().run_until_complete(adk_runtime.run_adk(runner, "u", "anon"))
    # Cached keys should still only contain the one we set.
    cache_keys = {k for k in adk_runtime._SESSION_CACHE if k[0] == id(runner)}
    assert cache_keys == {(id(runner), "sess-1")}
