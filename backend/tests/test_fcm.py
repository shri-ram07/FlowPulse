"""FCM push route — dry-run behaviour when no credentials are configured."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _auth(client: TestClient) -> dict:
    r = client.post("/api/auth/login", data={"username": "ops", "password": "ops-demo"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_fcm_push_requires_auth(client: TestClient):
    r = client.post("/api/fcm/push", json={
        "zone_id": "food_1", "title": "Test", "body": "Hello"
    })
    assert r.status_code == 401


def test_fcm_push_dry_run_when_project_missing(client: TestClient, monkeypatch):
    # Missing project → dry-run regardless of credentials.
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    r = client.post("/api/fcm/push",
        headers=_auth(client),
        json={"zone_id": "food_1", "title": "Quieter nearby",
              "body": "Food Court 5 is 3 min away, score 85/100",
              "severity": "info"})
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True
    assert body["topic"] == "zone_food_1"
    assert body["message_id"].startswith("dryrun-")
    assert body["reason"] == "missing_project"


def test_fcm_push_validates_input(client: TestClient):
    r = client.post("/api/fcm/push",
        headers=_auth(client),
        json={"zone_id": "", "title": "x", "body": "y"})  # empty zone_id
    assert r.status_code == 422
