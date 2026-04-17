"""Read-only zone APIs for the attendee PWA + staff console."""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.agents import tools
from backend.security.auth import rate_limit

router = APIRouter(prefix="/api/zones", tags=["zones"])


@router.get("", dependencies=[Depends(rate_limit(240))])
async def list_zones(kind: str | None = Query(default=None, max_length=20)) -> list[dict]:
    return tools.get_all_zones(kind=kind)


@lru_cache(maxsize=1)
def _graph_payload() -> dict:
    from backend.runtime import get_engine
    eng = get_engine()
    nodes = [
        {"id": z.id, "name": z.name, "kind": z.kind, "x": z.x, "y": z.y}
        for z in eng.zones.values()
    ]
    seen: set[tuple[str, str]] = set()
    edges: list[dict] = []
    for z in eng.zones.values():
        for e in z.neighbors:
            key = tuple(sorted((z.id, e.to)))
            if key in seen:
                continue
            seen.add(key)
            edges.append({"from": z.id, "to": e.to, "walk_seconds": e.walk_seconds})
    return {"nodes": nodes, "edges": edges}


@router.get("/graph", dependencies=[Depends(rate_limit(60))])
async def zone_graph(response: Response) -> dict:
    """Static graph of the venue — nodes (with coords) and edges (walk_seconds).

    Fetched once on page load so the frontend can draw paths + flow animation.
    Cached server-side (lru_cache) and client-side (Cache-Control: 1 hour).
    """
    response.headers["Cache-Control"] = "public, max-age=3600"
    return _graph_payload()


@router.get("/{zone_id}", dependencies=[Depends(rate_limit(240))])
async def get_zone(zone_id: str) -> dict:
    try:
        return tools.get_zone_state(zone_id)
    except KeyError as e:
        raise HTTPException(404, "unknown_zone") from e


@router.get("/{zone_id}/forecast", dependencies=[Depends(rate_limit(120))])
async def zone_forecast(zone_id: str, horizon_min: int = 2) -> dict:
    try:
        return tools.forecast_zone(zone_id, horizon_minutes=horizon_min)
    except KeyError as e:
        raise HTTPException(404, "unknown_zone") from e


@router.get("/route/{start}/{dest}", dependencies=[Depends(rate_limit(120))])
async def route(start: str, dest: str, optimize: str = "comfort") -> dict:
    if optimize not in ("time", "comfort"):
        raise HTTPException(400, "optimize must be 'time' or 'comfort'")
    return tools.get_best_route(start, dest, optimize=optimize)  # type: ignore[arg-type]
