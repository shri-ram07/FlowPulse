"""Read-only zone APIs for the attendee PWA + staff console."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from starlette.responses import Response as StarletteResponse

from backend.agents import tools
from backend.security.auth import (
    RATE_LIMIT_AGENT_PER_MIN,
    RATE_LIMIT_GRAPH_PER_MIN,
    RATE_LIMIT_READ_PER_MIN,
    rate_limit,
)

router = APIRouter(prefix="/api/zones", tags=["zones"])


@router.get("", dependencies=[Depends(rate_limit(RATE_LIMIT_READ_PER_MIN))])
async def list_zones(
    kind: str | None = Query(default=None, max_length=20),
) -> list[dict[str, object]]:
    """Return a snapshot of every zone, optionally filtered by `kind`.

    Args:
        kind: Optional kind filter — one of `gate`, `seating`, `concourse`,
            `food`, `restroom`, `merch`, `exit`. When omitted, all zones are
            returned.

    Returns:
        A list of zone-state dicts (id, name, kind, occupancy, density,
        inflow/outflow, wait, trend, score, level, x, y).
    """
    return tools.get_all_zones(kind=kind)


@lru_cache(maxsize=1)
def _graph_payload() -> dict[str, list[dict[str, object]]]:
    """Build the static node+edge graph payload once and memoise it.

    Nodes carry layout coordinates for the frontend SVG map; edges carry
    walk_seconds for route rendering. The payload is deterministic for a given
    zone configuration — safe to cache for the process lifetime.
    """
    from backend.runtime import get_engine

    eng = get_engine()
    nodes: list[dict[str, object]] = [
        {"id": z.id, "name": z.name, "kind": z.kind, "x": z.x, "y": z.y} for z in eng.zones.values()
    ]
    seen: set[tuple[str, str]] = set()
    edges: list[dict[str, object]] = []
    for z in eng.zones.values():
        for e in z.neighbors:
            a, b = sorted((z.id, e.to))
            key: tuple[str, str] = (a, b)
            if key in seen:
                continue
            seen.add(key)
            edges.append({"from": z.id, "to": e.to, "walk_seconds": e.walk_seconds})
    return {"nodes": nodes, "edges": edges}


@lru_cache(maxsize=1)
def _graph_etag() -> str:
    """Strong ETag derived from the graph payload bytes — stable across restarts
    as long as the zone configuration is unchanged."""
    body = json.dumps(_graph_payload(), sort_keys=True).encode()
    return '"' + hashlib.sha256(body).hexdigest()[:16] + '"'


@router.get("/graph", dependencies=[Depends(rate_limit(RATE_LIMIT_GRAPH_PER_MIN))], response_model=None)
async def zone_graph(
    response: Response,
    if_none_match: str | None = Header(default=None),
) -> StarletteResponse | dict[str, list[dict[str, object]]]:
    """Static graph of the venue — nodes (with coords) and edges (walk_seconds).

    Fetched once on page load so the frontend can draw paths + flow animation.
    Cached server-side (lru_cache), client-side (Cache-Control: 1 hour), and
    revalidated via ETag → 304 Not Modified when the client already has it.

    Args:
        response: Injected by FastAPI; used to set Cache-Control + ETag headers.
        if_none_match: The client's cached ETag (from a prior response). When
            it matches the current payload, we return HTTP 304 with an empty
            body to skip the transfer.

    Returns:
        Either a 304 `StarletteResponse` (cache hit) or the graph dict.
    """
    etag = _graph_etag()
    if if_none_match == etag:
        # 304 saves the full payload transfer on reloads.
        return StarletteResponse(status_code=304, headers={"ETag": etag})
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["ETag"] = etag
    return _graph_payload()


@router.get("/{zone_id}", dependencies=[Depends(rate_limit(RATE_LIMIT_READ_PER_MIN))])
async def get_zone(zone_id: str) -> dict[str, object]:
    """Return live state for a single zone.

    Args:
        zone_id: Zone identifier from the stadium graph (e.g. `gate_a`,
            `food_1`, `con_n`).

    Returns:
        The same zone-state dict returned by `list_zones`.

    Raises:
        HTTPException: 404 if the zone id is unknown.
    """
    try:
        return tools.get_zone_state(zone_id)
    except KeyError as e:
        raise HTTPException(404, "unknown_zone") from e


@router.get("/{zone_id}/forecast", dependencies=[Depends(rate_limit(RATE_LIMIT_AGENT_PER_MIN * 2))])
async def zone_forecast(zone_id: str, horizon_min: int = 2) -> dict[str, object]:
    """Forecast a zone's occupancy and Flow Score `horizon_min` minutes ahead.

    Args:
        zone_id: Zone to forecast.
        horizon_min: Minutes ahead to predict (1-10 reasonable). Defaults to 2.

    Returns:
        `{zone_id, horizon_minutes, predicted_occupancy, predicted_density,
        predicted_score}`.

    Raises:
        HTTPException: 404 if the zone id is unknown.
    """
    try:
        return tools.forecast_zone(zone_id, horizon_minutes=horizon_min)
    except KeyError as e:
        raise HTTPException(404, "unknown_zone") from e


@router.get("/route/{start}/{dest}", dependencies=[Depends(rate_limit(RATE_LIMIT_AGENT_PER_MIN * 2))])
async def route(start: str, dest: str, optimize: str = "comfort") -> dict[str, object]:
    """Best walking path from `start` to `dest` through the zone graph.

    Args:
        start: Source zone id.
        dest: Destination zone id.
        optimize: `comfort` (default) skirts red / congested zones; `time`
            takes the shortest walk regardless of congestion.

    Returns:
        `{path, eta_seconds, score_avg, mode}`.

    Raises:
        HTTPException: 400 if `optimize` is neither `time` nor `comfort`.
    """
    if optimize not in ("time", "comfort"):
        raise HTTPException(400, "optimize must be 'time' or 'comfort'")
    return tools.get_best_route(start, dest, optimize=optimize)  # type: ignore[arg-type]
