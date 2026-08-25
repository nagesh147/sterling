"""
Authentication endpoints — OAuth2 password flow issuing signed JWTs.

* ``POST /api/v1/auth/login``   — OAuth2PasswordRequestForm → access + refresh
* ``POST /api/v1/auth/refresh`` — refresh token → fresh access token
* ``POST /api/v1/auth/logout``  — bump token_version (invalidate all tokens)
* ``GET  /api/v1/auth/me``      — current identity

Login is rate-limited (brute-force guard, all environments) and does a dummy
password verify on the user-miss path so a bad username costs the same time as a
bad password (no user enumeration via timing).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core import tokens
from app.core.auth import UserContext, get_current_user
from app.core.passwords import hash_password, verify_password
from app.core.rate_limit import check_login
from app.services.auth import user_store

router = APIRouter(prefix="/auth", tags=["auth"])

# A real Argon2id hash of a random string, computed once at import. Verifying
# against it on the user-miss path spends ~the same time as a real check, so a
# nonexistent username can't be distinguished from a wrong password by timing.
import secrets as _secrets
_DUMMY_HASH = hash_password(_secrets.token_urlsafe(32))


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    user_id: str
    username: str
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    check_login(request)
    user = user_store.get_by_username(form.username)
    if user is None or not user.is_active:
        # Spend the verify time anyway, then fail identically to a wrong password.
        verify_password(form.password, _DUMMY_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=tokens.mint_access(user.id, user.username, user.role, user.token_version),
        refresh_token=tokens.mint_refresh(user.id, user.username, user.role, user.token_version),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest) -> TokenResponse:
    try:
        claims = tokens.decode(body.refresh_token, expected_typ="refresh")
    except tokens.TokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = user_store.get_by_id(claims.get("sub") or "")
    if user is None or not user.is_active or int(claims.get("ver", -1)) != int(user.token_version):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=tokens.mint_access(user.id, user.username, user.role, user.token_version),
        refresh_token=tokens.mint_refresh(user.id, user.username, user.role, user.token_version),
    )


@router.post("/logout")
async def logout(user: UserContext = Depends(get_current_user)) -> dict:
    """Invalidate every outstanding token for the caller (logout everywhere)."""
    user_store.bump_token_version(user.user_id)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
async def me(user: UserContext = Depends(get_current_user)) -> MeResponse:
    return MeResponse(user_id=user.user_id, username=user.username, role=user.role)
