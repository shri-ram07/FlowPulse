"""Load-test scenario for FlowPulse HTTP endpoints.

Run:
    locust -f tests/load/locustfile.py --headless -u 200 -r 20 \\
        --host=http://localhost:8000 -t 60s

Simulates a mixed-traffic profile weighted towards attendee reads
(map refresh, concierge chat, route lookup) with occasional ops plans.
"""
from __future__ import annotations

import random

from locust import HttpUser, between, task


STARTS = ["gate_a", "gate_b", "gate_c", "gate_e", "gate_f"]
DESTS = ["food_1", "food_2", "food_5", "rest_2", "rest_5", "exit_ramp"]
CHAT = [
    "Where should I grab food?",
    "Nearest restroom from gate A?",
    "How busy is Gate B?",
    "What's the forecast in 5 minutes?",
    "Quick snack?",
]


class AttendeeUser(HttpUser):
    wait_time = between(0.8, 2.5)
    weight = 8

    @task(5)
    def list_zones(self) -> None:
        self.client.get("/api/zones")

    @task(3)
    def zone_graph(self) -> None:
        self.client.get("/api/zones/graph")

    @task(2)
    def route(self) -> None:
        s = random.choice(STARTS)
        d = random.choice(DESTS)
        self.client.get(f"/api/zones/route/{s}/{d}", name="/api/zones/route")

    @task(2)
    def concierge(self) -> None:
        self.client.post(
            "/api/agent/attendee",
            json={"message": random.choice(CHAT)},
        )


class StaffUser(HttpUser):
    wait_time = between(4, 8)
    weight = 1
    token: str | None = None

    def on_start(self) -> None:
        r = self.client.post(
            "/api/auth/login",
            data={"username": "ops", "password": "ops-demo"},
        )
        if r.status_code == 200:
            self.token = r.json()["access_token"]

    @task
    def ops_plan(self) -> None:
        if not self.token:
            return
        self.client.post(
            "/api/agent/operations",
            headers={"Authorization": f"Bearer {self.token}"},
        )
