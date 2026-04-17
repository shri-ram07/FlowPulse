"""Firebase Cloud Messaging bridge — FCM HTTP v1 (OAuth 2.0).

Google retired the legacy `/fcm/send` API in 2024. This module uses the
modern v1 endpoint:

    POST https://fcm.googleapis.com/v1/projects/{project_id}/messages:send

Authentication: a Google service-account JSON file (Application Default
Credentials). The server account needs the `firebase.messaging` scope.

Behaviour:
  * If both GOOGLE_CLOUD_PROJECT and a credentials source are present,
    real push notifications are sent.
  * Otherwise the endpoint runs in dry-run mode — logs the would-be push
    and returns a fake message_id so the "Apply" UI flow still works.
"""
from __future__ import annotations

import os
import uuid
from functools import lru_cache

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.core.logging import audit, log
from backend.security.auth import StaffToken, rate_limit, require_staff

router = APIRouter(prefix="/api/fcm", tags=["fcm"])

_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class PushPayload(BaseModel):
    zone_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=240)
    severity: str = Field(default="info")


@lru_cache(maxsize=1)
def _credentials() -> object | None:
    """Load service-account credentials via Application Default Credentials.

    Honours GOOGLE_APPLICATION_CREDENTIALS (path to a key.json) and the
    default Cloud-Run / GCE metadata server. Returns None when no usable
    credentials are available — the endpoint then falls back to dry-run.
    """
    try:
        import google.auth  # type: ignore
        creds, _ = google.auth.default(scopes=[_SCOPE])
        return creds
    except Exception as e:  # pragma: no cover — env-dependent
        log.info("fcm.no_credentials", extra={"err": str(e)})
        return None


def _access_token(creds: object) -> str:
    from google.auth.transport.requests import Request  # type: ignore
    if not creds.valid:  # type: ignore[attr-defined]
        creds.refresh(Request())  # type: ignore[attr-defined]
    return creds.token  # type: ignore[attr-defined,return-value]


@router.post("/push", dependencies=[Depends(rate_limit(30))])
async def push(p: PushPayload, _user: StaffToken = Depends(require_staff)) -> dict:
    """Dispatch a zone-scoped push via FCM v1 (or dry-run if not configured)."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    creds = _credentials()
    topic = f"zone_{p.zone_id}"

    if not project or creds is None:
        msg_id = f"dryrun-{uuid.uuid4()}"
        log.info("fcm.dryrun", extra={"topic": topic, "title": p.title, "msg_id": msg_id})
        audit("fcm.push", actor=_user.sub, action="push_dry_run", target=topic,
              msg_id=msg_id)
        return {"ok": True, "dry_run": True, "message_id": msg_id, "topic": topic,
                "reason": "missing_project" if not project else "missing_credentials"}

    url = f"https://fcm.googleapis.com/v1/projects/{project}/messages:send"
    body = {
        "message": {
            "topic": topic,
            "notification": {"title": p.title, "body": p.body},
            "data": {"zone_id": p.zone_id, "severity": p.severity},
            "android": {"priority": "high" if p.severity == "critical" else "normal"},
        }
    }
    try:
        token = _access_token(creds)
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.post(
                url,
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json; UTF-8"},
                json=body,
            )
    except httpx.HTTPError as e:
        log.error("fcm.network_error", extra={"topic": topic, "err": str(e)})
        raise HTTPException(502, "fcm_upstream_error") from e

    if r.status_code >= 400:
        log.warning("fcm.rejected", extra={"topic": topic, "status": r.status_code})
        audit("fcm.push", actor=_user.sub, action="push", target=topic,
              result=f"rejected_{r.status_code}")
        raise HTTPException(502, f"fcm_rejected: {r.status_code}")
    j = r.json()
    audit("fcm.push", actor=_user.sub, action="push", target=topic,
          message_id=j.get("name"))
    return {"ok": True, "dry_run": False, "message_id": j.get("name"), "topic": topic}
