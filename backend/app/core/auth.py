"""
First-party authentication seam.

Identity is derived **only** from a verified Bearer access token (OAuth2 password
flow → signed JWT). The former ``X-User-Id`` header trust path is gone: a header
is client-controlled and let anyone impersonate any tenant.

Enforcement is a single global middleware in ``create_app`` (fail-closed: every
route is protected unless explicitly exempted). :func:`get_current_user` reads the
context the middleware stashed on ``request.state``; it also re-resolves directly
so it still works as a plain dependency on exempt routes. :func:`authenticate_request`
is the one function that turns a request into an identity — tests monkeypatch it to
inject a fixed identity without minting real tokens.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.core import tokens
from app.core.tokens import TokenError
from app.services.auth import user_store

# Retained: the bootstrap admin's id, imported by callers that need a concrete
# owner id outside a request (e.g. notifications/telegram_kite.py).
DEFAULT_USER_ID = "default"

# auto_error=False → the middleware owns the 401, and exempt routes can still opt
# into an optional identity without this scheme forcing a 401.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


@dataclass(frozen=True)
class UserContext:
    user_id: str
    username: str = ""
    role: str = "user"


def _bearer_from(request: Request) -> str:
    header = request.headers.get("Authorization") or ""
    if header[:7].lower() == "bearer ":
        return header[7:].strip()
    return ""


async def authenticate_request(request: Request) -> Optional[UserContext]:
    """Resolve identity from the Bearer access token, or ``None`` if the request
    is not authenticated. This is the single seam tests replace."""
    token = _bearer_from(request)
    if not token:
        return None
    try:
        claims = tokens.decode(token, expected_typ="access")
    except TokenError:
        return None
    user = user_store.get_by_id(claims.get("sub") or "")
    if user is None or not user.is_active:
        return None
    # token_version mismatch → the token was invalidated (logout-all / rotation).
    if int(claims.get("ver", -1)) != int(user.token_version):
        return None
    return UserContext(user_id=user.id, username=user.username, role=user.role)


async def get_current_user(request: Request) -> UserContext:
    """FastAPI dependency → the calling user's context. 401 if unauthenticated."""
    ctx = getattr(request.state, "user_ctx", None)
    if ctx is not None:
        return ctx
    ctx = await authenticate_request(request)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ctx


async def get_current_admin(request: Request) -> UserContext:
    """Dependency for privileged actions (credential CRUD, kill-switch, mode)."""
    ctx = await get_current_user(request)
    if ctx.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return ctx
