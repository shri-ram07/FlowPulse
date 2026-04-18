"""CrowdFlowEngine — the heart of FlowPulse.

Holds the live state of every zone and exposes safe mutation operations
(enter/exit/move). Computes EWMA flow rates on every tick and publishes
broadcast snapshots to the event bus.

Concurrency: guarded by a single asyncio.Lock. Every tick is O(Z) where Z is
the zone count (<100 for a stadium); well under 1 ms on any laptop.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Final

from .events import bus
from .scoring import (
    FORECAST_SATURATION_MULTIPLIER,
    congestion_level,
    crowd_flow_score,
    forecast,
)
from .zone import Zone

# ---- EWMA flow smoothing ---------------------------------------------------
EWMA_ALPHA: Final[float] = 0.3

# ---- Risk / alert thresholds -----------------------------------------------
# A zone is "at risk" when density > RISK_DENSITY_THRESHOLD AND inflow outpaces
# outflow by at least RISK_FLOW_RATIO x. Sustained for SUSTAINED_RISK_DURATION_SEC
# => a critical alert fires.
RISK_DENSITY_THRESHOLD: Final[float] = 0.9
RISK_FLOW_RATIO: Final[float] = 2.0
SUSTAINED_RISK_DURATION_SEC: Final[float] = 15.0

# De-dupe window: don't re-alert the same zone inside this.
ALERT_DEDUP_WINDOW_SEC: Final[float] = 60.0

# Alerts older than this are pruned from the live list.
ALERT_RETENTION_SEC: Final[float] = 300.0

# ---- Observability throttle -----------------------------------------------
# Cloud Monitoring + BigQuery writes happen at most once per this interval.
# 10 s ~ 6x per minute — comfortably under free-tier quotas.
OBS_EMIT_THROTTLE_SEC: Final[float] = 10.0

# Flow rate window normalisation (seconds → minutes).
SEC_PER_MIN: Final[float] = 60.0


@dataclass
class Alert:
    id: str
    zone_id: str
    severity: str  # info | warn | critical
    message: str
    ts: float


class CrowdFlowEngine:
    def __init__(self, zones: list[Zone]) -> None:
        self.zones: dict[str, Zone] = {z.id: z for z in zones}
        self._entered_since_tick: dict[str, int] = {z.id: 0 for z in zones}
        self._exited_since_tick: dict[str, int] = {z.id: 0 for z in zones}
        self._last_tick = time.monotonic()
        self._lock = asyncio.Lock()
        self.alerts: list[Alert] = []
        self._recent_risk_since: dict[str, float] = {}
        # Hash of fields that matter for UI; used to compute per-tick diffs.
        self._last_broadcast: dict[str, tuple[Any, ...]] = {}
        # Observability sink throttling — at most once every 10 s.
        self._last_obs_emit: float = 0.0

    # ---- mutations ----------------------------------------------------
    async def enter(self, zone_id: str, n: int = 1) -> None:
        async with self._lock:
            z = self._require(zone_id)
            z.occupancy = min(int(z.capacity * FORECAST_SATURATION_MULTIPLIER), z.occupancy + n)
            self._entered_since_tick[zone_id] += n

    async def exit(self, zone_id: str, n: int = 1) -> None:
        async with self._lock:
            z = self._require(zone_id)
            z.occupancy = max(0, z.occupancy - n)
            self._exited_since_tick[zone_id] += n

    async def move(self, src: str, dst: str, n: int = 1) -> None:
        async with self._lock:
            zs, zd = self._require(src), self._require(dst)
            n = min(n, zs.occupancy)
            if n <= 0:
                return
            zs.occupancy -= n
            zd.occupancy = min(int(zd.capacity * 1.3), zd.occupancy + n)
            self._exited_since_tick[src] += n
            self._entered_since_tick[dst] += n

    # ---- tick ---------------------------------------------------------
    async def tick(self) -> dict[str, Any]:
        """Advance one wall-clock step: update EWMA flow rates, evaluate risk,
        publish a snapshot diff on the event bus, return the broadcast payload.
        """
        async with self._lock:
            now = time.monotonic()
            dt = max(1e-3, now - self._last_tick)
            self._last_tick = now
            for zid, z in self.zones.items():
                # observed flow in people/minute over the tick window.
                observed_in = self._entered_since_tick[zid] * (SEC_PER_MIN / dt)
                observed_out = self._exited_since_tick[zid] * (SEC_PER_MIN / dt)
                z.inflow_rate = EWMA_ALPHA * observed_in + (1 - EWMA_ALPHA) * z.inflow_rate
                z.outflow_rate = EWMA_ALPHA * observed_out + (1 - EWMA_ALPHA) * z.outflow_rate
                z.history.append(z.occupancy)
                self._entered_since_tick[zid] = 0
                self._exited_since_tick[zid] = 0

            new_alerts = self._evaluate_risk(now)
            payload = self._snapshot_payload(new_alerts)

        await bus.publish("flowpulse:events", payload)

        # Observability fan-out (Cloud Monitoring + BigQuery). Throttled to
        # ~6x per minute so we stay comfortably under free-tier quotas.
        if now - self._last_obs_emit >= OBS_EMIT_THROTTLE_SEC:
            self._last_obs_emit = now
            self._emit_obs(payload)

        return payload

    def _emit_obs(self, payload: dict[str, Any]) -> None:
        """Write Cloud Monitoring points + stream BigQuery rows for this tick.

        Env-flagged; a missing `GOOGLE_CLOUD_PROJECT` makes both calls no-op.
        Failures never interrupt the main tick loop.
        """
        try:
            from backend.observability.bigquery import stream_tick_rows
            from backend.observability.metrics import write_tick_metric

            zones = payload.get("zones") or [self._zone_state(z) for z in self.zones.values()]
            total = len(zones)
            avg_score = (sum(z["score"] for z in zones) / total) if total else 0.0
            critical = sum(1 for z in zones if z["level"] == "critical")
            congested = sum(1 for z in zones if z["level"] == "congested")
            write_tick_metric(avg_score=avg_score, critical=critical, congested=congested, zones=total)
            stream_tick_rows(zones)
        except Exception as e:  # pragma: no cover — defensive
            # Observability is best-effort; never propagate into the tick loop.
            import logging

            logging.getLogger("flowpulse.engine").debug("obs.emit_failed", extra={"err": str(e)[:240]})

    # ---- snapshots ---------------------------------------------------
    def snapshot(self, zone_id: str) -> dict[str, Any]:
        z = self._require(zone_id)
        return self._zone_state(z)

    def snapshot_all(self, kind: str | None = None) -> list[dict[str, Any]]:
        return [self._zone_state(z) for z in self.zones.values() if kind is None or z.kind == kind]

    def _zone_state(self, z: Zone) -> dict[str, Any]:
        return {
            "id": z.id,
            "name": z.name,
            "kind": z.kind,
            "capacity": z.capacity,
            "occupancy": z.occupancy,
            "density": round(z.density, 3),
            "inflow_per_min": round(z.inflow_rate, 2),
            "outflow_per_min": round(z.outflow_rate, 2),
            "wait_minutes": z.wait_minutes,
            "trend": z.trend,
            "score": crowd_flow_score(z),
            "level": congestion_level(z),
            "x": z.x,
            "y": z.y,
        }

    def _snapshot_payload(self, new_alerts: list[Alert], *, full: bool = False) -> dict[str, Any]:
        """Build a tick payload. In diff mode, only include zones whose UI-facing
        fields actually changed since the last broadcast — this collapses most
        steady-state payloads to <200 bytes (vs ~3 KB for a full snapshot).
        """
        changed: list[dict[str, Any]] = []
        for z in self.zones.values():
            state = self._zone_state(z)
            # Hash the fields that actually matter to the UI.
            key = (state["occupancy"], state["score"], state["level"], state["wait_minutes"], state["trend"])
            if full or self._last_broadcast.get(z.id) != key:
                changed.append(state)
                self._last_broadcast[z.id] = key
        return {
            "type": "tick",
            "ts": time.time(),
            "full": full,
            "zones": changed,
            "alerts": [asdict(a) for a in new_alerts],
        }

    def full_snapshot_payload(self) -> dict[str, Any]:
        """Used by the WebSocket handler on first connect to send a complete state."""
        return self._snapshot_payload([], full=True)

    # ---- forecasting helpers -----------------------------------------
    def forecast(self, zone_id: str, horizon_minutes: int = 2) -> dict[str, Any]:
        z = self._require(zone_id)
        f = forecast(z, horizon_minutes)
        return {
            "zone_id": zone_id,
            "horizon_minutes": f.horizon_minutes,
            "predicted_occupancy": f.predicted_occupancy,
            "predicted_density": f.predicted_density,
            "predicted_score": f.predicted_score,
        }

    # ---- alerts & risk -----------------------------------------------
    def _evaluate_risk(self, now: float) -> list[Alert]:
        fired: list[Alert] = []
        for z in self.zones.values():
            risk = z.density > RISK_DENSITY_THRESHOLD and z.inflow_rate > RISK_FLOW_RATIO * z.outflow_rate
            if risk:
                started = self._recent_risk_since.setdefault(z.id, now)
                # Fire after sustained risk for > SUSTAINED_RISK_DURATION_SEC (scaled for demo).
                if now - started > SUSTAINED_RISK_DURATION_SEC and not self._already_alerted(z.id, now):
                    a = Alert(
                        id=str(uuid.uuid4()),
                        zone_id=z.id,
                        severity="critical",
                        message=f"{z.name}: density {z.density:.0%}, inflow outpacing outflow.",
                        ts=now,
                    )
                    self.alerts.append(a)
                    fired.append(a)
            else:
                self._recent_risk_since.pop(z.id, None)
        # Prune alerts older than ALERT_RETENTION_SEC (5 minutes).
        self.alerts = [a for a in self.alerts if now - a.ts < ALERT_RETENTION_SEC]
        return fired

    def _already_alerted(self, zone_id: str, now: float) -> bool:
        return any(a.zone_id == zone_id and now - a.ts < ALERT_DEDUP_WINDOW_SEC for a in self.alerts)

    # ---- util ---------------------------------------------------------
    def _require(self, zone_id: str) -> Zone:
        if zone_id not in self.zones:
            raise KeyError(f"unknown zone {zone_id!r}")
        return self.zones[zone_id]
