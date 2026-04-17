"""Staff login endpoint (demo)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from backend.security.auth import issue_token, rate_limit, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", dependencies=[Depends(rate_limit(20))])
async def login(form: OAuth2PasswordRequestForm = Depends()) -> dict:
    if not verify_password(form.username, form.password):
        raise HTTPException(401, "invalid_credentials")
    return {"access_token": issue_token(form.username), "token_type": "bearer"}
