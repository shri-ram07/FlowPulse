"""Stadium zone graph + Dijkstra routing with congestion-aware edge weights."""
from __future__ import annotations

import heapq
from typing import Any, Literal

from .zone import Zone

RouteMode = Literal["time", "comfort"]


def best_route(
    zones: dict[str, Zone],
    start: str,
    dest: str,
    mode: RouteMode = "time",
) -> dict[str, Any]:
    """Return {path, eta_seconds, score_avg} or {"error": ...}.

    - mode="time": edge = walk_seconds only.
    - mode="comfort": edge = walk_seconds * (1 + penalty(dst_density)).
      Comfort mode routes around red zones even if the path is longer.
    """
    if start not in zones or dest not in zones:
        return {"error": "unknown_zone"}

    def penalty(z: Zone) -> float:
        d = z.density
        if d > 0.95:
            return 2.5
        if d > 0.85:
            return 1.2
        if d > 0.6:
            return 0.4
        return 0.0

    dist: dict[str, float] = {start: 0.0}
    prev: dict[str, str] = {}
    pq: list[tuple[float, str]] = [(0.0, start)]
    while pq:
        d_u, u = heapq.heappop(pq)
        if u == dest:
            break
        if d_u > dist.get(u, float("inf")):
            continue
        for edge in zones[u].neighbors:
            v = edge.to
            if v not in zones:
                continue
            w: float = float(edge.walk_seconds)
            if mode == "comfort":
                w = w * (1.0 + penalty(zones[v]))
            nd = d_u + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    if dest not in dist:
        return {"error": "no_path"}

    # Reconstruct path.
    path = [dest]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()

    from .scoring import crowd_flow_score
    scores = [crowd_flow_score(zones[z]) for z in path]
    return {
        "path": path,
        "eta_seconds": int(dist[dest]),
        "score_avg": round(sum(scores) / len(scores)),
        "mode": mode,
    }
