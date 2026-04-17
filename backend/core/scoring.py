"""Crowd Flow Score + lightweight trend-based forecasting.

The Crowd Flow Score collapses density, wait time, pressure, and risk into one
0–100 number per zone. Higher = healthier. The formula is intentionally simple
and explainable — judges and ops staff can read it off a page.
"""
from __future__ import annotations

from dataclasses import dataclass

from .zone import Zone


@dataclass
class ForecastResult:
    horizon_minutes: int
    predicted_occupancy: int
    predicted_density: float
    predicted_score: int


def crowd_flow_score(z: Zone) -> int:
    """Return an integer 0..100 — higher is healthier."""
    d = min(z.density, 1.5) / 1.5
    w = min(z.wait_minutes, 15) / 15
    pressure_raw = max(0.0, z.inflow_rate - z.outflow_rate) / max(z.capacity, 1) * 60
    pressure = min(pressure_raw, 1.0)
    risk = 1.0 if (z.density > 0.95 and z.inflow_rate > z.outflow_rate) else 0.0
    score = 100 - 40 * d - 30 * w - 20 * pressure - 10 * risk
    return max(0, min(100, round(score)))


def congestion_level(z: Zone) -> str:
    """Four-band classifier used for colour bands and alerts."""
    d = z.density
    rising = z.inflow_rate > z.outflow_rate
    if d > 0.95 and rising:
        return "critical"
    if d > 0.85:
        return "congested"
    if d > 0.6 and rising:
        return "building"
    return "calm"


def forecast(z: Zone, horizon_minutes: int = 2) -> ForecastResult:
    """Extrapolate occupancy using current EWMA inflow/outflow.

    Clamped to [0, 1.3*capacity] — beyond that the zone is saturated and the
    surplus spills to neighbours (handled upstream by the engine).
    """
    delta_per_min = z.inflow_rate - z.outflow_rate
    predicted_occ = int(z.occupancy + delta_per_min * horizon_minutes)
    predicted_occ = max(0, min(int(z.capacity * 1.3), predicted_occ))
    predicted_density = predicted_occ / z.capacity if z.capacity else 0.0
    # Build a temporary zone snapshot to reuse scoring logic.
    shadow = Zone(
        id=z.id, name=z.name, kind=z.kind, capacity=z.capacity,
        x=z.x, y=z.y, occupancy=predicted_occ,
        inflow_rate=z.inflow_rate, outflow_rate=z.outflow_rate,
        neighbors=z.neighbors,
    )
    return ForecastResult(
        horizon_minutes=horizon_minutes,
        predicted_occupancy=predicted_occ,
        predicted_density=round(predicted_density, 3),
        predicted_score=crowd_flow_score(shadow),
    )
