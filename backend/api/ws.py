"""WebSocket broadcast: every engine tick pushes a DIFF snapshot to clients.

Payload schema (`type`="tick"):
    {"type":"tick","ts":..., "full": bool, "zones":[{...}], "alerts":[{...}]}

- On connect: one `full=true` payload with every zone.
- Thereafter: `full=false` payloads containing only zones whose UI fields
  changed since the previous tick. Alerts are always included when new.

Clients merge diffs by id. Steady-state payload is typically <200 B.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.events import bus
from backend.runtime import get_engine

router = APIRouter()


@router.websocket("/ws")
async def stream(ws: WebSocket) -> None:
    await ws.accept()
    # Send a full snapshot immediately so the client can render the map.
    await ws.send_json(get_engine().full_snapshot_payload())

    sub = bus.subscribe("flowpulse:events")

    async def pump_bus() -> None:
        async for payload in sub:
            await ws.send_json(payload)

    async def pump_client() -> None:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})

    bus_task = asyncio.create_task(pump_bus())
    client_task = asyncio.create_task(pump_client())
    try:
        _done, pending = await asyncio.wait(
            {bus_task, client_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        bus_task.cancel()
        client_task.cancel()
