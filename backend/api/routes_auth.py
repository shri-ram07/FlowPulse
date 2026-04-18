"""Staff login endpoint (demo)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm

from backend.core.logging import audit
from backend.security.auth import (
    RATE_LIMIT_AUTH_PER_MIN,
    _client_ip,
    issue_token,
    rate_limit,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", dependencies=[Depends(rate_limit(RATE_LIMIT_AUTH_PER_MIN))])
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
) -> dict[str, str]:
    """Exchange username/password for a short-lived JWT.

    Args:
        request: Injected by FastAPI; used for IP-based audit logging.
        form: Standard OAuth2 `username` + `password` form fields.

    Returns:
        `{access_token, token_type}` on success.

    Raises:
        HTTPException: 401 when the credentials don't match.
    """
    ip = _client_ip(request)
    if not verify_password(form.username, form.password):
        audit("auth.login_failed", actor=form.username, action="login", result="invalid_credentials", ip=ip)
        raise HTTPException(401, "invalid_credentials")
    audit("auth.login_success", actor=form.username, action="login", ip=ip)
    return {"access_token": issue_token(form.username), "token_type": "bearer"}
