"""Zone domain model — the atomic unit of FlowPulse's flow graph."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Literal

ZoneKind = Literal["gate", "seating", "food", "restroom", "concourse", "exit", "merch"]

# Service rates (people served per minute) — heuristics per zone kind.
SERVICE_RATE = {
    "gate": 30.0,
    "food": 6.0,
    "restroom": 12.0,
    "merch": 4.0,
    "concourse": 120.0,
    "seating": 60.0,
    "exit": 40.0,
}


@dataclass
class Edge:
    to: str
    walk_seconds: int


@dataclass
class Zone:
    id: str
    name: str
    kind: ZoneKind
    capacity: int
    # Spatial coordinates used by the SVG map (0-1000 viewBox).
    x: float
    y: float
    occupancy: int = 0
    inflow_rate: float = 0.0   # people/min (EWMA)
    outflow_rate: float = 0.0  # people/min (EWMA)
    neighbors: list[Edge] = field(default_factory=list)
    # last 60 occupancy samples for trend visualisation.
    history: deque[int] = field(default_factory=lambda: deque(maxlen=60))

    @property
    def density(self) -> float:
        return self.occupancy / self.capacity if self.capacity else 0.0

    @property
    def wait_minutes(self) -> float:
        """Little's Law heuristic: queue / service rate."""
        rate = SERVICE_RATE.get(self.kind, 30.0)
        queue = max(0, self.occupancy - int(self.capacity * 0.2))
        return round(queue / rate, 2) if rate else 0.0

    @property
    def trend(self) -> Literal["rising", "falling", "steady"]:
        delta = self.inflow_rate - self.outflow_rate
        if delta > 1.0:
            return "rising"
        if delta < -1.0:
            return "falling"
        return "steady"
