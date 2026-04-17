"""WebSocket endpoint — full snapshot on connect, diff frames thereafter."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_ws_emits_full_snapshot_on_connect():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "tick"
        assert first["full"] is True
        assert len(first["zones"]) >= 20


def test_ws_ping_pong_round_trip():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        # Drain the initial full snapshot.
        ws.receive_json()
        ws.send_json({"type": "ping"})
        # The server may publish a tick before answering the ping; read until
        # we see the pong.
        for _ in range(5):
            msg = ws.receive_json()
            if msg.get("type") == "pong":
                return
        raise AssertionError("did not receive pong within 5 frames")


def test_ws_accepts_concurrent_clients():
    client1 = TestClient(app)
    client2 = TestClient(app)
    with client1.websocket_connect("/ws") as ws1, client2.websocket_connect("/ws") as ws2:
        a = ws1.receive_json()
        b = ws2.receive_json()
        # Both should see the same zone count on their full snapshot.
        assert a["full"] is True
        assert b["full"] is True
        assert len(a["zones"]) == len(b["zones"])
