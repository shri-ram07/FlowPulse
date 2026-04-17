"""Staff login endpoint (demo)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm

from backend.core.logging import audit
from backend.security.auth import issue_token, rate_limit, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", dependencies=[Depends(rate_limit(20))])
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
) -> dict:
    ip = request.client.host if request.client else "unknown"
    if not verify_password(form.username, form.password):
        audit("auth.login_failed", actor=form.username, action="login",
              result="invalid_credentials", ip=ip)
        raise HTTPException(401, "invalid_credentials")
    audit("auth.login_success", actor=form.username, action="login", ip=ip)
    return {"access_token": issue_token(form.username), "token_type": "bearer"}
