"""Hypothesis property-based tests for scoring + routing invariants."""

from __future__ import annotations

from typing import Literal

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.core.scoring import congestion_level, crowd_flow_score, forecast
from backend.core.zone import Zone

ZoneKind = Literal["gate", "seating", "food", "restroom", "concourse", "exit", "merch"]


def _zone(
    occupancy: int,
    capacity: int,
    inflow: float,
    outflow: float,
    kind: ZoneKind = "food",
) -> Zone:
    return Zone(
        id="z",
        name="Z",
        kind=kind,
        capacity=capacity,
        x=0.0,
        y=0.0,
        occupancy=occupancy,
        inflow_rate=inflow,
        outflow_rate=outflow,
    )


@given(
    capacity=st.integers(min_value=10, max_value=5000),
    occupancy=st.integers(min_value=0, max_value=6000),
    inflow=st.floats(min_value=0, max_value=500, allow_nan=False),
    outflow=st.floats(min_value=0, max_value=500, allow_nan=False),
)
@settings(max_examples=200, deadline=None)
def test_crowd_flow_score_always_bounded(
    capacity: int,
    occupancy: int,
    inflow: float,
    outflow: float,
) -> None:
    """Invariant: the score stays in [0, 100] for any combination of inputs."""
    score = crowd_flow_score(_zone(occupancy, capacity, inflow, outflow))
    assert 0 <= score <= 100


@given(
    capacity=st.integers(min_value=10, max_value=5000),
    occupancy=st.integers(min_value=0, max_value=5000),
    inflow=st.floats(min_value=0, max_value=200, allow_nan=False),
    outflow=st.floats(min_value=0, max_value=200, allow_nan=False),
)
@settings(max_examples=200, deadline=None)
def test_congestion_level_is_known(
    capacity: int,
    occupancy: int,
    inflow: float,
    outflow: float,
) -> None:
    level = congestion_level(_zone(occupancy, capacity, inflow, outflow))
    assert level in {"calm", "building", "congested", "critical"}


@given(
    horizon=st.integers(min_value=1, max_value=15),
    capacity=st.integers(min_value=50, max_value=5000),
    occupancy=st.integers(min_value=0, max_value=5000),
)
@settings(max_examples=100, deadline=None)
def test_forecast_clamps_within_expected_range(
    horizon: int,
    capacity: int,
    occupancy: int,
) -> None:
    """Forecast occupancy never exceeds 1.3× capacity and never drops below 0."""
    z = _zone(occupancy, capacity, inflow=100.0, outflow=10.0)
    f = forecast(z, horizon_minutes=horizon)
    assert 0 <= f.predicted_occupancy <= int(capacity * 1.3)
    assert 0 <= f.predicted_score <= 100


@given(occupancy=st.integers(min_value=0, max_value=3000))
@settings(max_examples=100, deadline=None)
def test_concourse_balanced_flow_stays_healthy(occupancy: int) -> None:
    """A concourse (high service rate) with balanced flow and moderate
    density should stay healthy — no wait-time penalty is triggered."""
    z = _zone(occupancy, capacity=10000, inflow=10.0, outflow=10.0, kind="concourse")
    # Below 20% capacity the wait-time queue heuristic returns 0.
    if z.density < 0.2:
        assert crowd_flow_score(z) >= 90
