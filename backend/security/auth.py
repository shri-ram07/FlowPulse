"""JWT-based auth for staff endpoints + a small sliding-window rate limiter.

Attendee endpoints are unauthenticated (read-only). Anything that mutates
engine state or dispatches alerts requires a staff JWT.

Passwords are **hashed** (passlib + bcrypt) — see DEMO_STAFF below.
The in-memory rate-limit buckets prune themselves on access.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

SECRET: Final = os.environ.get("FLOWPULSE_JWT_SECRET", "dev-secret-change-me")
ALGO: Final = "HS256"
TTL_MIN: Final = 60 * 8

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Bcrypt rounds — 10 is the common default, fast enough for login-once-per-session
# and strong enough for this threat model. Bump to 12 in prod.
_BCRYPT_ROUNDS: Final = 12  # OWASP 2024 recommendation; ~0.25s/hash on modern CPUs


def _hash(pw: str) -> bytes:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))


def _verify(pw: str, hashed: bytes) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed)
    except ValueError:
        return False


class StaffToken(BaseModel):
    sub: str
    role: str  # ops | admin
    exp: int


# Demo staff — passwords stored as bcrypt hashes, NOT plaintext.
# Plaintext values (for the demo UI / docs) are:
#   ops   -> "ops-demo"
#   admin -> "admin-demo"
DEMO_STAFF: Final[dict[str, dict[str, bytes | str]]] = {
    "ops":   {"hash": _hash("ops-demo"),   "role": "ops"},
    "admin": {"hash": _hash("admin-demo"), "role": "admin"},
}

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
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=TTL_MIN)).timestamp()),
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
_MAX_IPS: Final = 4096  # hard cap on tracked IPs


def rate_limit(max_per_minute: int = 120) -> Any:
    async def dep(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = _BUCKETS.setdefault(ip, [])
        cutoff = now - 60.0
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
