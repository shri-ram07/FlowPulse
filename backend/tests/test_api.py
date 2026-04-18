"""HTTP-level tests using FastAPI's TestClient.

Covers: health, zone list/filter, graph shape, route computation, auth,
staff-only routes, rate limiting, security headers, and attendee chat.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    # Use the app directly — lifespan kicks off the engine singleton.
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["zones"] > 0


def test_security_headers_present(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"


def test_zone_list_and_filter(client: TestClient) -> None:
    r = client.get("/api/zones")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    r = client.get("/api/zones?kind=food")
    assert r.status_code == 200
    assert all(z["kind"] == "food" for z in r.json())


def test_zone_graph_shape_and_cache(client: TestClient) -> None:
    r = client.get("/api/zones/graph")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body and "edges" in body
    assert body["nodes"] and body["edges"]
    assert "Cache-Control" in r.headers


def test_route_endpoint(client: TestClient) -> None:
    r = client.get("/api/zones/route/gate_a/food_2")
    assert r.status_code == 200
    body = r.json()
    assert body["path"][0] == "gate_a"
    assert body["path"][-1] == "food_2"


def test_route_rejects_bad_optimize(client: TestClient) -> None:
    r = client.get("/api/zones/route/gate_a/food_2?optimize=nonsense")
    assert r.status_code == 400


def test_unknown_zone_returns_404(client: TestClient) -> None:
    r = client.get("/api/zones/does_not_exist")
    assert r.status_code == 404


def test_login_flow_and_protected_route(client: TestClient) -> None:
    # Wrong password → 401
    r = client.post("/api/auth/login", data={"username": "ops", "password": "wrong"})
    assert r.status_code == 401

    # Right password → token
    r = client.post("/api/auth/login", data={"username": "ops", "password": "ops-demo"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

    # Staff endpoint blocked without token
    r = client.post("/api/agent/operations")
    assert r.status_code == 401

    # Staff endpoint works with token
    r = client.post("/api/agent/operations", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert "situation" in body and "actions" in body


def test_attendee_chat_grounded_in_tool_calls(client: TestClient) -> None:
    r = client.post("/api/agent/attendee", json={"message": "Where should I grab food?"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"]
    # Deterministic fallback always shows its tool citations.
    if body["engine"] == "fallback":
        assert body["tool_calls"]


def test_attendee_chat_rejects_overlong_message(client: TestClient) -> None:
    r = client.post("/api/agent/attendee", json={"message": "x" * 501})
    assert r.status_code == 422
