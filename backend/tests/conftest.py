import pytest_asyncio

from backend import runtime
from backend.core.engine import CrowdFlowEngine
from backend.security import auth
from backend.sim.simulator import Simulator
from backend.stadium_config import default_stadium


@pytest_asyncio.fixture(autouse=True)
async def reset_runtime():
    """Ensure every test sees a fresh engine + simulator + rate-limit buckets.

    Without this, the in-memory per-IP rate limit (module-level state in
    `backend.security.auth`) would accumulate calls from previous tests and
    eventually 429 on /api/auth/login.
    """
    runtime._engine = CrowdFlowEngine(default_stadium())
    runtime._sim = Simulator(runtime._engine)
    auth._BUCKETS.clear()
    yield
    runtime._engine = None
    runtime._sim = None
    auth._BUCKETS.clear()
