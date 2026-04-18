from backend.core.scoring import congestion_level, crowd_flow_score, forecast
from backend.core.zone import Zone


def _z(**kw):
    defaults = dict(id="x", name="X", kind="food", capacity=100, x=0, y=0)
    defaults.update(kw)
    return Zone(**defaults)


def test_empty_zone_is_perfect():
    assert crowd_flow_score(_z(occupancy=0)) == 100


def test_score_drops_with_density():
    low = crowd_flow_score(_z(occupancy=20))
    high = crowd_flow_score(_z(occupancy=100))
    assert low > high


def test_risk_penalty_applied():
    z = _z(occupancy=97, inflow_rate=10, outflow_rate=1)
    assert crowd_flow_score(z) < 40
    assert congestion_level(z) == "critical"


def test_forecast_extrapolates():
    z = _z(occupancy=40, inflow_rate=30, outflow_rate=10)  # +20/min net
    f = forecast(z, horizon_minutes=2)
    assert f.predicted_occupancy == 80
    assert 0 < f.predicted_score < 100


def test_forecast_clamps_to_capacity():
    z = _z(occupancy=90, inflow_rate=100, outflow_rate=0)
    f = forecast(z, horizon_minutes=5)
    # 1.3 * capacity = 130
    assert f.predicted_occupancy <= 130
