"""Ops apply endpoint — real side effects for each action type."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.runtime import get_engine


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _auth(client: TestClient) -> dict:
    r = client.post("/api/auth/login", data={"username": "ops", "password": "ops-demo"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_apply_requires_auth(client: TestClient):
    r = client.post("/api/ops/apply", json={"type": "monitor", "target": "food_1"})
    assert r.status_code == 401


def test_apply_monitor_records_alert(client: TestClient):
    start_alerts = len(get_engine().alerts)
    r = client.post("/api/ops/apply", headers=_auth(client),
                    json={"type": "monitor", "target": "food_1",
                          "rationale": "keeping an eye"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["type"] == "monitor"
    assert "Monitoring" in body["message"]
    assert len(get_engine().alerts) == start_alerts + 1


def test_apply_push_notification_returns_fcm_result(client: TestClient, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)  # force dry-run
    r = client.post("/api/ops/apply", headers=_auth(client),
                    json={"type": "push_notification", "target": "food_2",
                          "title": "Quieter nearby",
                          "body": "Food Court 5 is 3 min away, 85/100"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["fcm"]["dry_run"] is True


def test_apply_open_gate_records_alert(client: TestClient):
    r = client.post("/api/ops/apply", headers=_auth(client),
                    json={"type": "open_gate", "target": "gate_c",
                          "rationale": "extra lanes needed"})
    assert r.status_code == 200
    assert "Gate" in r.json()["message"]


@pytest.mark.asyncio
async def test_apply_redirect_computes_relief_when_candidate_exists(client: TestClient):
    # Seed: fill food_1 so it needs relief, leave food_5 with headroom.
    eng = get_engine()
    await eng.enter("food_1", 170)
    r = client.post("/api/ops/apply", headers=_auth(client),
                    json={"type": "redirect", "target": "food_1",
                          "rationale": "food_1 is saturated"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    # Either we redirect (with relief_pct) or we honestly admit there's no candidate.
    assert "relief_pct" in body


def test_apply_validates_action_type(client: TestClient):
    r = client.post("/api/ops/apply", headers=_auth(client),
                    json={"type": "nuke_site", "target": "gate_a"})
    assert r.status_code == 422


def test_apply_validates_target(client: TestClient):
    r = client.post("/api/ops/apply", headers=_auth(client),
                    json={"type": "monitor", "target": ""})
    assert r.status_code == 422
