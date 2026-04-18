"""Singleton wiring for the engine + simulator so routes share one state object.

Kept in its own module to avoid circular imports between api/, agents/, sim/.
"""

from __future__ import annotations

from backend.core.engine import CrowdFlowEngine
from backend.sim.simulator import Simulator
from backend.stadium_config import default_stadium

_engine: CrowdFlowEngine | None = None
_sim: Simulator | None = None


def get_engine() -> CrowdFlowEngine:
    global _engine
    if _engine is None:
        _engine = CrowdFlowEngine(default_stadium())
    return _engine


def get_simulator() -> Simulator:
    global _sim
    if _sim is None:
        _sim = Simulator(get_engine())
    return _sim


def _reset_engine_for_tests() -> None:
    """Test-only hook — rebuild the engine + simulator from a fresh default
    stadium. Called by `backend/tests/conftest.py` as an autouse fixture so
    each test starts with occupancies at 0 regardless of test-collection order.
    """
    global _engine, _sim
    _engine = None
    _sim = None
