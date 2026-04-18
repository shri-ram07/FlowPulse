"""Crowd Flow Score + lightweight trend-based forecasting.

The Crowd Flow Score collapses density, wait time, pressure, and risk into one
0–100 number per zone. Higher = healthier. The formula is intentionally simple
and explainable — judges and ops staff can read it off a page.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .zone import Zone

# ---- Scoring weights (sum to 100 by design) --------------------------------
DENSITY_WEIGHT: Final[int] = 40
WAIT_WEIGHT: Final[int] = 30
PRESSURE_WEIGHT: Final[int] = 20
RISK_WEIGHT: Final[int] = 10

# ---- Clamp bounds — contributions pin at 1.0 beyond these -------------------
DENSITY_CLAMP: Final[float] = 1.5  # density / DENSITY_CLAMP -> [0, 1]
WAIT_MINUTES_CLAMP: Final[int] = 15
PRESSURE_UNITS_PER_MIN: Final[int] = 60  # convert per-second flow to per-minute pressure

# ---- Congestion bands (see congestion_level) -------------------------------
CRITICAL_DENSITY: Final[float] = 0.95
CONGESTED_DENSITY: Final[float] = 0.85
BUILDING_DENSITY: Final[float] = 0.6

# ---- Forecast saturation ceiling -------------------------------------------
# Predicted occupancy is clamped to [0, FORECAST_SATURATION_MULTIPLIER * capacity].
# Beyond that the zone is saturated and surplus spills to neighbours upstream.
FORECAST_SATURATION_MULTIPLIER: Final[float] = 1.3


@dataclass
class ForecastResult:
    horizon_minutes: int
    predicted_occupancy: int
    predicted_density: float
    predicted_score: int


def crowd_flow_score(z: Zone) -> int:
    """Return an integer 0..100 — higher is healthier."""
    d = min(z.density, DENSITY_CLAMP) / DENSITY_CLAMP
    w = min(z.wait_minutes, WAIT_MINUTES_CLAMP) / WAIT_MINUTES_CLAMP
    pressure_raw = max(0.0, z.inflow_rate - z.outflow_rate) / max(z.capacity, 1) * PRESSURE_UNITS_PER_MIN
    pressure = min(pressure_raw, 1.0)
    risk = 1.0 if (z.density > CRITICAL_DENSITY and z.inflow_rate > z.outflow_rate) else 0.0
    score = 100 - DENSITY_WEIGHT * d - WAIT_WEIGHT * w - PRESSURE_WEIGHT * pressure - RISK_WEIGHT * risk
    return max(0, min(100, round(score)))


def congestion_level(z: Zone) -> str:
    """Four-band classifier used for colour bands and alerts."""
    d = z.density
    rising = z.inflow_rate > z.outflow_rate
    if d > CRITICAL_DENSITY and rising:
        return "critical"
    if d > CONGESTED_DENSITY:
        return "congested"
    if d > BUILDING_DENSITY and rising:
        return "building"
    return "calm"


def forecast(z: Zone, horizon_minutes: int = 2) -> ForecastResult:
    """Extrapolate occupancy using current EWMA inflow/outflow.

    Clamped to [0, FORECAST_SATURATION_MULTIPLIER * capacity] — beyond that the
    zone is saturated and the surplus spills to neighbours (handled upstream by
    the engine).
    """
    delta_per_min = z.inflow_rate - z.outflow_rate
    predicted_occ = int(z.occupancy + delta_per_min * horizon_minutes)
    predicted_occ = max(
        0,
        min(int(z.capacity * FORECAST_SATURATION_MULTIPLIER), predicted_occ),
    )
    predicted_density = predicted_occ / z.capacity if z.capacity else 0.0
    # Build a temporary zone snapshot to reuse scoring logic.
    shadow = Zone(
        id=z.id,
        name=z.name,
        kind=z.kind,
        capacity=z.capacity,
        x=z.x,
        y=z.y,
        occupancy=predicted_occ,
        inflow_rate=z.inflow_rate,
        outflow_rate=z.outflow_rate,
        neighbors=z.neighbors,
    )
    return ForecastResult(
        horizon_minutes=horizon_minutes,
        predicted_occupancy=predicted_occ,
        predicted_density=round(predicted_density, 3),
        predicted_score=crowd_flow_score(shadow),
    )
