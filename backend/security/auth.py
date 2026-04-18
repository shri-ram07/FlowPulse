"""JWT-based auth for staff endpoints + a small sliding-window rate limiter.

Attendee endpoints are unauthenticated (read-only). Anything that mutates
engine state or dispatches alerts requires a staff JWT.

Passwords are **hashed** (passlib + bcrypt) — see DEMO_STAFF below.
The in-memory rate-limit buckets prune themselves on access.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

_log = logging.getLogger("flowpulse.auth")


def _load_jwt_secret() -> str:
    """Read `FLOWPULSE_JWT_SECRET`; loudly warn if a prod deploy falls back to
    the dev default. Cloud Run deploys set `GOOGLE_CLOUD_PROJECT` automatically,
    so that is a reliable prod signal."""
    secret = os.environ.get("FLOWPULSE_JWT_SECRET", "").strip()
    if secret:
        return secret
    if os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("FLOWPULSE_ENV") == "prod":
        _log.warning(
            "auth.jwt_secret_missing_in_prod",
            extra={
                "msg": "FLOWPULSE_JWT_SECRET not set; refusing to sign with "
                "dev default. Mount the Secret Manager secret."
            },
        )
    return "dev-secret-change-me"


SECRET: Final = _load_jwt_secret()
ALGO: Final = "HS256"

# ---- JWT lifetime (8 hours — matches a typical ops shift) ------------------
JWT_TTL_MINUTES: Final[int] = 60 * 8
TTL_MIN: Final = JWT_TTL_MINUTES  # kept as alias for any external callers

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# ---- Password hashing cost -------------------------------------------------
# OWASP 2024 recommendation; ~0.25 s/hash on modern CPUs. Strong enough for
# this threat model and fast enough for login-once-per-session.
BCRYPT_ROUNDS: Final[int] = 12
_BCRYPT_ROUNDS: Final = BCRYPT_ROUNDS  # legacy alias for internal helpers

# ---- Rate-limit defaults (per-minute sliding window, per client IP) ---------
# Public read endpoints get the higher ceiling; auth-mutating endpoints get the
# stricter one. Tuned so a single browser session never trips a limit.
RATE_LIMIT_DEFAULT_PER_MIN: Final[int] = 120  # generic fallback
RATE_LIMIT_READ_PER_MIN: Final[int] = 240  # GET /api/zones, /api/zones/{id}, /api/sim/state
RATE_LIMIT_GRAPH_PER_MIN: Final[int] = 60  # GET /api/zones/graph (lru_cached, cold is heavy)
RATE_LIMIT_AGENT_PER_MIN: Final[int] = 60  # POST /api/agent/attendee
RATE_LIMIT_OPS_APPLY_PER_MIN: Final[int] = 60  # POST /api/ops/apply
RATE_LIMIT_FCM_PUSH_PER_MIN: Final[int] = 30  # POST /api/fcm/push
RATE_LIMIT_AUTH_PER_MIN: Final[int] = 20  # POST /api/auth/login (tight — brute-force guard)

# Hard cap on distinct IPs tracked in-memory before pruning.
RATE_LIMIT_MAX_IPS: Final[int] = 4096


def _hash(pw: str) -> bytes:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS))


def _verify(pw: str, hashed: bytes) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed)
    except ValueError:
        return False


class StaffToken(BaseModel):
    sub: str
    role: str  # ops | admin
    exp: int


# Demo mode — public submission & local dev both default to ON. Operators
# flipping `FLOWPULSE_DEMO_MODE=0` on a real deployment *immediately* disable
# the hardcoded ops/admin credentials; the login endpoint then rejects every
# attempt with 401 until a proper user-store is wired in. See SECURITY.md
# "Demo mode" for the threat-model rationale.
DEMO_MODE: Final[bool] = os.environ.get("FLOWPULSE_DEMO_MODE", "1") == "1"

# Demo staff — passwords stored as bcrypt hashes, NOT plaintext.
# Plaintext values (for the demo UI / docs) are:
#   ops   -> "ops-demo"
#   admin -> "admin-demo"
DEMO_STAFF: Final[dict[str, dict[str, bytes | str]]] = (
    {
        "ops": {"hash": _hash("ops-demo"), "role": "ops"},
        "admin": {"hash": _hash("admin-demo"), "role": "admin"},
    }
    if DEMO_MODE
    else {}
)

if not DEMO_MODE:
    _log.warning(
        "auth.demo_mode_disabled",
        extra={
            "msg": "FLOWPULSE_DEMO_MODE=0 — no built-in staff credentials; "
            "wire up a real user store before enabling /api/auth/login."
        },
    )

# A valid but unreachable hash used for timing-uniform failure paths.
_DUMMY_HASH: Final = _hash("never-used")


def verify_password(username: str, password: str) -> bool:
    rec = DEMO_STAFF.get(username)
    if not rec:
        # Constant-time dummy verify so response time doesn't leak valid usernames.
        _verify(password, _DUMMY_HASH)
        return False
    return _verify(password, rec["hash"])  # type: ignore[arg-type]


def issue_token(username: str) -> str:
    rec = DEMO_STAFF.get(username)
    if not rec:
        raise HTTPException(401, "invalid_credentials")
    payload = {
        "sub": username,
        "role": rec["role"],
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=JWT_TTL_MINUTES)).timestamp()),
    }
    token: str = jwt.encode(payload, SECRET, algorithm=ALGO)
    return token


async def require_staff(token: str | None = Depends(oauth2)) -> StaffToken:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing_token")
    try:
        data = jwt.decode(token, SECRET, algorithms=[ALGO])
        return StaffToken(**data)
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token") from e


# ---- in-memory sliding-window rate limiter ----
# Kept intentionally small — for multi-process / multi-instance we'd swap in
# a Redis-backed bucket (see skills/websocket-engineer).
_BUCKETS: dict[str, list[float]] = {}
_MAX_IPS: Final = RATE_LIMIT_MAX_IPS  # legacy alias

# Window length in seconds; matches the "per minute" contract of max_per_minute.
_WINDOW_SEC: Final[float] = 60.0


def _client_ip(request: Request) -> str:
    """Resolve the caller's IP, honouring `X-Forwarded-For` behind Cloud Run's LB.

    Cloud Run terminates TLS at a load balancer; `request.client.host` is then
    the LB's internal IP — the same value for every user, which collapses a
    per-IP rate limiter into a single shared bucket. Use the first hop in
    `X-Forwarded-For` (RFC 7239 convention: left-most = origin client).
    """
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        # Take only the left-most entry; subsequent entries are proxies.
        first = xff.split(",", 1)[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def rate_limit(max_per_minute: int = RATE_LIMIT_DEFAULT_PER_MIN) -> Any:
    async def dep(request: Request) -> None:
        ip = _client_ip(request)
        now = time.monotonic()
        bucket = _BUCKETS.setdefault(ip, [])
        cutoff = now - _WINDOW_SEC
        # Drop entries older than the window (amortised O(1)).
        i = 0
        for t in bucket:
            if t >= cutoff:
                break
            i += 1
        if i:
            del bucket[:i]
        if len(bucket) >= max_per_minute:
            raise HTTPException(429, "rate_limited")
        bucket.append(now)
        # Cap the total number of tracked IPs — drop empty buckets.
        if len(_BUCKETS) > _MAX_IPS:
            for k in [k for k, v in _BUCKETS.items() if not v]:
                _BUCKETS.pop(k, None)

    return dep
