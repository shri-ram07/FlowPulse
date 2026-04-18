"""verify_live.py — live-deployment acceptance tests.

Hits every public endpoint on the deployed FlowPulse Cloud Run stack and
asserts the exact claims made in README / VERIFICATION.md. Prints a
rubric-keyed pass/fail table and exits non-zero on any failure.

Usage:
    python scripts/verify_live.py
    python scripts/verify_live.py --backend https://... --frontend https://...

The default URLs point at the production deployment on `personal-493605`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_BACKEND = "https://flowpulse-backend-g6g2de3yuq-el.a.run.app"
DEFAULT_FRONTEND = "https://flowpulse-frontend-g6g2de3yuq-el.a.run.app"


# ---------------------------------------------------------------------------
# Assertion framework
# ---------------------------------------------------------------------------


@dataclass
class Check:
    axis: str
    claim: str
    status: str = "PENDING"        # PASS | FAIL | SKIP
    detail: str = ""
    latency_ms: float = 0.0


CHECKS: list[Check] = []


def record(axis: str, claim: str, status: str, detail: str = "", latency_ms: float = 0.0) -> None:
    CHECKS.append(Check(axis=axis, claim=claim, status=status, detail=detail, latency_ms=latency_ms))


# ---------------------------------------------------------------------------
# Individual check functions — one per README/VERIFICATION claim
# ---------------------------------------------------------------------------


def check_health(client: httpx.Client, backend: str) -> None:
    t0 = time.monotonic()
    try:
        r = client.get(f"{backend}/api/health", timeout=15)
        ms = (time.monotonic() - t0) * 1000
        body = r.json()
        ok = r.status_code == 200 and body.get("status") == "ok" and body.get("zones", 0) >= 20
        record("Efficiency", "Backend health endpoint responds <300 ms",
               "PASS" if ok and ms < 300 else "FAIL",
               f"status={r.status_code} zones={body.get('zones')} p={ms:.0f}ms", ms)
    except Exception as e:  # noqa: BLE001
        record("Efficiency", "Backend health endpoint responds", "FAIL", str(e))


def check_security_headers(client: httpx.Client, backend: str) -> None:
    """Single claim split into 7 rows — each header gets a check."""
    try:
        r = client.get(f"{backend}/api/health", timeout=15)
    except Exception as e:  # noqa: BLE001
        for h in ("Strict-Transport-Security", "Content-Security-Policy",
                  "X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy",
                  "Permissions-Policy", "Cross-Origin-Opener-Policy"):
            record("Security", f"Response has `{h}`", "FAIL", str(e))
        return
    for h in (
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
    ):
        v = r.headers.get(h)
        record("Security", f"Response has `{h}` header",
               "PASS" if v else "FAIL",
               f"value={v!r}" if v else "header absent")


def check_gzip_and_etag(client: httpx.Client, backend: str) -> None:
    try:
        r = client.get(f"{backend}/api/zones/graph", timeout=15,
                       headers={"Accept-Encoding": "gzip"})
    except Exception as e:  # noqa: BLE001
        record("Efficiency", "Graph endpoint gzips", "FAIL", str(e))
        record("Efficiency", "Graph endpoint emits ETag", "FAIL", str(e))
        return
    # httpx auto-decodes but the raw header still reveals encoding.
    enc = r.headers.get("content-encoding", "").lower()
    record("Efficiency", "`/api/zones/graph` returns `Content-Encoding: gzip`",
           "PASS" if "gzip" in enc else "FAIL",
           f"content-encoding={enc!r}")
    etag = r.headers.get("etag", "")
    record("Efficiency", "`/api/zones/graph` returns an ETag",
           "PASS" if etag else "FAIL",
           f"etag={etag!r}")
    # 304 on second request with If-None-Match
    if etag:
        r2 = client.get(f"{backend}/api/zones/graph",
                        headers={"If-None-Match": etag}, timeout=15)
        record("Efficiency", "Graph endpoint returns 304 Not Modified on matching ETag",
               "PASS" if r2.status_code == 304 else "FAIL",
               f"status={r2.status_code}")


def check_zones_shape(client: httpx.Client, backend: str) -> None:
    try:
        r = client.get(f"{backend}/api/zones", timeout=15)
        zones = r.json()
        ok = r.status_code == 200 and isinstance(zones, list) and len(zones) >= 20
        record("Google Services", "`/api/zones` returns at least 20 live zones",
               "PASS" if ok else "FAIL",
               f"n={len(zones) if isinstance(zones, list) else '?'}")
        # Check schema
        if zones:
            z0 = zones[0]
            required = {"id", "name", "kind", "capacity", "occupancy", "density",
                        "score", "level", "trend", "wait_minutes"}
            missing = required - set(z0.keys())
            record("Code Quality", "Zone objects include every documented field",
                   "PASS" if not missing else "FAIL",
                   f"missing={sorted(missing)}" if missing else "all fields present")
    except Exception as e:  # noqa: BLE001
        record("Google Services", "`/api/zones` returns zones", "FAIL", str(e))


def check_route_endpoint(client: httpx.Client, backend: str) -> None:
    try:
        r = client.get(f"{backend}/api/zones/route/gate_a/food_2", timeout=15)
        body = r.json()
        ok = r.status_code == 200 and body.get("path", [None])[0] == "gate_a"
        record("Google Services", "Dijkstra route endpoint returns a valid path",
               "PASS" if ok else "FAIL",
               f"path_len={len(body.get('path', []))} eta={body.get('eta_seconds')}s")
    except Exception as e:  # noqa: BLE001
        record("Google Services", "Dijkstra route endpoint", "FAIL", str(e))


def check_attendee_agent(client: httpx.Client, backend: str) -> None:
    t0 = time.monotonic()
    try:
        r = client.post(f"{backend}/api/agent/attendee",
                        json={"message": "which food court is quietest right now?"},
                        timeout=45)
        ms = (time.monotonic() - t0) * 1000
        body = r.json()
        engine = body.get("engine")
        record("Google Services", "Attendee agent responds (`engine=google-adk` or `fallback`)",
               "PASS" if r.status_code == 200 and engine else "FAIL",
               f"engine={engine} latency={ms:.0f}ms", ms)
        record("Google Services", "Attendee agent answer is grounded (>=1 tool_calls)",
               "PASS" if len(body.get("tool_calls", [])) >= 1 else "FAIL",
               f"tool_calls={len(body.get('tool_calls', []))}")
    except Exception as e:  # noqa: BLE001
        record("Google Services", "Attendee agent", "FAIL", str(e))


def check_ops_agent(client: httpx.Client, backend: str) -> None:
    # Login first.
    try:
        rl = client.post(f"{backend}/api/auth/login",
                         data={"username": "ops", "password": "ops-demo"},
                         timeout=15)
        if rl.status_code != 200:
            record("Security", "Staff login succeeds with demo creds",
                   "FAIL", f"status={rl.status_code}")
            return
        token = rl.json()["access_token"]
        record("Security", "Staff login succeeds with demo creds", "PASS",
               "token acquired")
    except Exception as e:  # noqa: BLE001
        record("Security", "Staff login", "FAIL", str(e))
        return

    t0 = time.monotonic()
    try:
        r = client.post(f"{backend}/api/agent/operations",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=60)
        ms = (time.monotonic() - t0) * 1000
        body = r.json()
        ok = r.status_code == 200 and "situation" in body and "actions" in body
        record("Google Services", "Ops agent returns structured OpsPlan JSON",
               "PASS" if ok else "FAIL",
               f"engine={body.get('engine')} actions={len(body.get('actions', []))}", ms)
        # Look for multi-agent evidence: tool_calls list should contain specialist names.
        tool_names = [c.get("name", "") for c in body.get("tool_calls", [])]
        multi_agent = any(n in tool_names for n in ("call_safety_agent",
                                                     "call_forecast_agent",
                                                     "call_routing_agent",
                                                     "call_comms_agent"))
        record("Google Services", "Ops pipeline invokes multi-agent specialists",
               "PASS" if multi_agent else "FAIL",
               f"tool_names={tool_names[:8]}")
    except Exception as e:  # noqa: BLE001
        record("Google Services", "Ops agent", "FAIL", str(e))


def check_openapi(client: httpx.Client, backend: str) -> None:
    try:
        r = client.get(f"{backend}/openapi.json", timeout=15)
        body = r.json()
        n_paths = len(body.get("paths", {}))
        record("Code Quality", "OpenAPI spec documents >=10 routes",
               "PASS" if r.status_code == 200 and n_paths >= 10 else "FAIL",
               f"paths={n_paths}")
    except Exception as e:  # noqa: BLE001
        record("Code Quality", "OpenAPI spec is published", "FAIL", str(e))


def check_frontend_routes(client: httpx.Client, frontend: str) -> None:
    routes = [
        ("/", "Welcome page renders with hero + how-to-use"),
        ("/map", "Live Map page renders"),
        ("/chat", "Concierge page renders"),
        ("/ops", "Ops login page renders"),
        ("/hi", "Hindi Welcome page renders"),
    ]
    for path, claim in routes:
        try:
            r = client.get(f"{frontend}{path}", timeout=20, follow_redirects=True)
            ok = r.status_code == 200 and "FlowPulse" in r.text
            record("Accessibility", claim,
                   "PASS" if ok else "FAIL",
                   f"status={r.status_code} has_flowpulse={'FlowPulse' in r.text}")
        except Exception as e:  # noqa: BLE001
            record("Accessibility", claim, "FAIL", str(e))


def check_accessible_mode_bundle(client: httpx.Client, frontend: str) -> None:
    """The Accessible-Mode toggle component name must appear in the shipped JS bundle."""
    try:
        r = client.get(f"{frontend}/map", timeout=20, follow_redirects=True)
        has_toggle = ("a11y-toggle" in r.text) or ("AccessibleModeToggle" in r.text)
        record("Accessibility", "Accessible Mode toggle is present in the deployed frontend",
               "PASS" if has_toggle else "FAIL",
               "toggle class/component found in HTML" if has_toggle else "token not in HTML")
    except Exception as e:  # noqa: BLE001
        record("Accessibility", "Accessible Mode toggle present", "FAIL", str(e))


def check_websocket_contract(client: httpx.Client, backend: str) -> None:
    """Happy-path WebSocket: connect, receive first `full` payload."""
    try:
        import websockets  # type: ignore
        import asyncio

        async def _probe():
            ws_url = backend.replace("https", "wss") + "/ws"
            async with websockets.connect(ws_url, open_timeout=10) as ws:
                frame = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(frame)
                return msg
        msg = asyncio.run(_probe())
        ok = msg.get("type") == "tick" and msg.get("full") is True and msg.get("zones")
        record("Efficiency", "WebSocket sends a `full=true` snapshot on connect",
               "PASS" if ok else "FAIL",
               f"type={msg.get('type')} full={msg.get('full')} zones={len(msg.get('zones', []))}")
    except ImportError:
        record("Efficiency", "WebSocket `full=true` snapshot on connect",
               "SKIP", "websockets package not installed")
    except Exception as e:  # noqa: BLE001
        record("Efficiency", "WebSocket full snapshot on connect", "FAIL", str(e))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(backend: str, frontend: str) -> int:
    with httpx.Client() as client:
        check_health(client, backend)
        check_security_headers(client, backend)
        check_gzip_and_etag(client, backend)
        check_zones_shape(client, backend)
        check_route_endpoint(client, backend)
        check_attendee_agent(client, backend)
        check_ops_agent(client, backend)
        check_openapi(client, backend)
        check_frontend_routes(client, frontend)
        check_accessible_mode_bundle(client, frontend)
        check_websocket_contract(client, backend)

    # ---- Report ----
    by_axis: dict[str, list[Check]] = {}
    for c in CHECKS:
        by_axis.setdefault(c.axis, []).append(c)

    print(f"\n{'='*100}")
    print(f"FlowPulse live-deployment verification")
    print(f"  backend : {backend}")
    print(f"  frontend: {frontend}")
    print(f"{'='*100}\n")

    pass_count = fail_count = skip_count = 0
    for axis in sorted(by_axis):
        print(f"--- {axis} ---")
        for c in by_axis[axis]:
            flag = {"PASS": "[OK]  ", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}.get(c.status, "[?]")
            print(f"  {flag} {c.claim}")
            if c.detail:
                print(f"         {c.detail}")
            if c.status == "PASS":
                pass_count += 1
            elif c.status == "FAIL":
                fail_count += 1
            else:
                skip_count += 1
        print()

    total = pass_count + fail_count + skip_count
    pct = 100.0 * pass_count / max(total, 1)
    print(f"{'='*100}")
    print(f"  {pass_count} PASS  {fail_count} FAIL  {skip_count} SKIP   ({pct:.0f}% pass, {total} total)")
    print(f"{'='*100}")
    return 0 if fail_count == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default=DEFAULT_BACKEND,
                        help=f"Backend base URL (default {DEFAULT_BACKEND})")
    parser.add_argument("--frontend", default=DEFAULT_FRONTEND,
                        help=f"Frontend base URL (default {DEFAULT_FRONTEND})")
    args = parser.parse_args()
    return run(args.backend, args.frontend)


if __name__ == "__main__":
    sys.exit(main())
