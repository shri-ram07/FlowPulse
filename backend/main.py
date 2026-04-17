"""FlowPulse FastAPI gateway.

Entry point: `uvicorn backend.main:app --reload --port 8000`.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import (
    routes_agent,
    routes_auth,
    routes_fcm,
    routes_ops,
    routes_sim,
    routes_zones,
    ws,
)
from backend.core.logging import configure_logging, log
from backend.observability.tracing import configure_tracing
from backend.runtime import get_engine, get_simulator
from backend.security.headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    configure_tracing()
    log.info("flowpulse.startup")

    # Warm up singletons; auto-start sim so the demo is live on first load.
    get_engine()
    sim = get_simulator()
    sim.start()

    # Heartbeat: even if the sim is stopped, tick the engine so WS stays live.
    async def heartbeat() -> None:
        while True:
            try:
                if sim._task is None or sim._task.done():  # type: ignore[attr-defined]
                    await get_engine().tick()
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                return
    hb = asyncio.create_task(heartbeat())
    try:
        yield
    finally:
        hb.cancel()
        await sim.stop()
        log.info("flowpulse.shutdown")


app = FastAPI(
    title="FlowPulse",
    description="Crowd-orchestration platform for live venues.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(routes_auth.router)
app.include_router(routes_zones.router)
app.include_router(routes_agent.router)
app.include_router(routes_sim.router)
app.include_router(routes_fcm.router)
app.include_router(routes_ops.router)
app.include_router(ws.router)


@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    eng = get_engine()
    return {"status": "ok", "zones": len(eng.zones), "alerts": len(eng.alerts)}
