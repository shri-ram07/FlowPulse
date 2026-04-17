"""Closed-loop Ops action executor.

The Operations Agent emits plans like:
    {"type": "redirect", "target": "food_2", "rationale": "..."}

This endpoint accepts one of those action objects and actually DOES something:
every supported action dispatches an alert onto the engine's event bus (so the
effect is visible on the live map) and, where meaningful, calls the relevant
tool (FCM push for notifications, suggest_redirect for rerouting). Returns a
summary the UI can turn into a toast.
"""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.agents import tools
from backend.api.routes_fcm import PushPayload
from backend.api.routes_fcm import push as fcm_push
from backend.core.logging import audit, log
from backend.security.auth import StaffToken, rate_limit, require_staff

router = APIRouter(prefix="/api/ops", tags=["ops"])

ActionType = Literal[
    "push_notification", "redirect", "open_gate", "dispatch_staff", "monitor",
]


class ApplyAction(BaseModel):
    type: ActionType
    target: str = Field(min_length=1, max_length=64)
    rationale: str = Field(default="", max_length=400)
    severity: str = Field(default="info")
    # Optional override for push_notification
    title: str | None = Field(default=None, max_length=80)
    body: str | None = Field(default=None, max_length=240)


@router.post("/apply", dependencies=[Depends(rate_limit(60))])
async def apply_action(p: ApplyAction, user: StaffToken = Depends(require_staff)) -> dict:
    """Execute one Ops-agent action. Returns a summary for the toast/feedback UI."""
    action_id = f"act-{uuid.uuid4().hex[:10]}"

    # Every action records an alert so the effect is visible on the live map.
    severity_map = {
        "push_notification": "info",
        "redirect":          "warn",
        "open_gate":         "warn",
        "dispatch_staff":    "warn",
        "monitor":           "info",
    }
    alert_severity = p.severity if p.severity in ("info", "warn", "critical") \
        else severity_map.get(p.type, "info")

    result: dict = {"action_id": action_id, "type": p.type, "target": p.target,
                    "applied_by": user.sub}

    if p.type == "push_notification":
        title = p.title or "Crowd tip from FlowPulse"
        body = p.body or p.rationale or "A quieter option is nearby."
        fcm = await fcm_push(
            PushPayload(zone_id=p.target, title=title, body=body, severity=alert_severity),
            _user=user,
        )
        tools.dispatch_alert(p.target, f"Push sent: {title}", severity=alert_severity)
        result.update({
            "message": f"Push dispatched to zone {p.target}",
            "fcm": fcm,
        })

    elif p.type == "redirect":
        # Destination can come via the agent plan; when missing we pick the
        # best-scored same-kind neighbour (mirrors the deterministic planner).
        zones = tools.get_all_zones()
        src = next((z for z in zones if z["id"] == p.target), None)
        if not src:
            raise HTTPException(404, "unknown_source_zone")
        candidates = [
            z for z in zones
            if z["kind"] == src["kind"] and z["id"] != src["id"]
            and z["score"] >= 60 and z["occupancy"] < z["capacity"] * 0.7
        ]
        if not candidates:
            tools.dispatch_alert(p.target,
                                 "Redirect requested but no green alternative has headroom.",
                                 severity="warn")
            result.update({"message": "No redirect candidate available right now.",
                           "relief_pct": 0})
        else:
            dest = max(candidates, key=lambda z: z["score"])
            relief = tools.suggest_redirect(p.target, dest["id"])
            tools.dispatch_alert(
                p.target,
                f"Redirecting ~{relief['redirect_count']} fans to {dest['name']} "
                f"(expected relief {relief['expected_relief_pct']}%).",
                severity=alert_severity,
            )
            result.update({
                "message": f"Redirecting {relief['redirect_count']} fans "
                           f"from {src['name']} → {dest['name']}",
                "to": dest["id"],
                "relief_pct": relief["expected_relief_pct"],
            })

    elif p.type == "open_gate":
        tools.dispatch_alert(
            p.target,
            f"Gate opened / extra lanes live. {p.rationale}".strip(),
            severity=alert_severity,
        )
        result["message"] = f"Gate {p.target} marked open — inflow capacity increased."

    elif p.type == "dispatch_staff":
        tools.dispatch_alert(
            p.target,
            f"Staff dispatched. {p.rationale}".strip(),
            severity=alert_severity,
        )
        result["message"] = f"Staff dispatched to {p.target}."

    elif p.type == "monitor":
        tools.dispatch_alert(p.target, "Ops is monitoring this zone.", severity="info")
        result["message"] = f"Monitoring {p.target}."

    # `extra=` can't reuse reserved LogRecord keys like `message`, so pass a copy
    # with user-facing keys renamed.
    log_ctx = {f"act_{k}" if k in ("message", "args") else k: v for k, v in result.items()}
    log.info("ops.apply", extra=log_ctx)
    # Audit trail for every privileged write — queryable via auditEvent=true.
    audit("ops.apply", actor=user.sub, action=p.type, target=p.target,
          action_id=action_id)
    result["ok"] = True
    return result
