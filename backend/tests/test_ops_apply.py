"""Ops apply endpoint — real side effects for each action type."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.runtime import get_engine


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def _auth(client: TestClient) -> dict[str, str]:
    r = client.post("/api/auth/login", data={"username": "ops", "password": "ops-demo"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_apply_requires_auth(client: TestClient) -> None:
    r = client.post("/api/ops/apply", json={"type": "monitor", "target": "food_1"})
    assert r.status_code == 401


def test_apply_monitor_records_alert(client: TestClient) -> None:
    start_alerts = len(get_engine().alerts)
    r = client.post(
        "/api/ops/apply",
        headers=_auth(client),
        json={"type": "monitor", "target": "food_1", "rationale": "keeping an eye"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["type"] == "monitor"
    assert "Monitoring" in body["message"]
    assert len(get_engine().alerts) == start_alerts + 1


def test_apply_push_notification_returns_fcm_result(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)  # force dry-run
    r = client.post(
        "/api/ops/apply",
        headers=_auth(client),
        json={
            "type": "push_notification",
            "target": "food_2",
            "title": "Quieter nearby",
            "body": "Food Court 5 is 3 min away, 85/100",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["fcm"]["dry_run"] is True


def test_apply_open_gate_records_alert(client: TestClient) -> None:
    r = client.post(
        "/api/ops/apply",
        headers=_auth(client),
        json={"type": "open_gate", "target": "gate_c", "rationale": "extra lanes needed"},
    )
    assert r.status_code == 200
    assert "Gate" in r.json()["message"]


@pytest.mark.asyncio
async def test_apply_redirect_computes_relief_when_candidate_exists(client: TestClient) -> None:
    # Seed: fill food_1 so it needs relief, leave food_5 with headroom.
    eng = get_engine()
    await eng.enter("food_1", 170)
    r = client.post(
        "/api/ops/apply",
        headers=_auth(client),
        json={"type": "redirect", "target": "food_1", "rationale": "food_1 is saturated"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    # Either we redirect (with relief_pct) or we honestly admit there's no candidate.
    assert "relief_pct" in body


def test_apply_validates_action_type(client: TestClient) -> None:
    r = client.post("/api/ops/apply", headers=_auth(client), json={"type": "nuke_site", "target": "gate_a"})
    assert r.status_code == 422


def test_apply_validates_target(client: TestClient) -> None:
    r = client.post("/api/ops/apply", headers=_auth(client), json={"type": "monitor", "target": ""})
    assert r.status_code == 422


def test_apply_dispatch_staff_records_alert(client: TestClient) -> None:
    """dispatch_staff emits an alert + success message; no FCM/redirect side-effects."""
    start_alerts = len(get_engine().alerts)
    r = client.post(
        "/api/ops/apply",
        headers=_auth(client),
        json={"type": "dispatch_staff", "target": "food_2", "rationale": "second attendant to Food Court 2"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["type"] == "dispatch_staff"
    assert "Staff dispatched" in body["message"]
    assert len(get_engine().alerts) == start_alerts + 1


@pytest.mark.asyncio
async def test_apply_redirect_returns_409_when_no_candidate(client: TestClient) -> None:
    """When every same-kind zone is also crowded, redirect must 409 (not 200).

    The endpoint used to return 200 with relief_pct=0 — a silent no-op that
    muddled the audit trail. Post-refactor it returns HTTP 409 so the UI can
    surface 'nothing moved' distinctly.
    """
    eng = get_engine()
    # Saturate EVERY food zone over capacity*0.7 so no candidate can satisfy
    # occupancy < capacity * REDIRECT_MAX_CANDIDATE_LOAD.
    for zid, z in list(eng.zones.items()):
        if z.kind == "food":
            await eng.enter(zid, int(z.capacity * 0.85))
    r = client.post(
        "/api/ops/apply",
        headers=_auth(client),
        json={"type": "redirect", "target": "food_1", "rationale": "all food zones crowded"},
    )
    assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.json()}"
    detail = r.json()["detail"]
    assert detail["ok"] is False
    assert detail["reason"] == "no_redirect_candidate"
    assert detail["target"] == "food_1"
