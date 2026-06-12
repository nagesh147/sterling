"""
Pluggable multi-tenant user context.

Sterling has no first-party identity provider yet, but the Kite integration is
designed multi-user from day one: every Kite credential, session and tick stream
is scoped to a ``user_id``. This module is the single seam where a real auth
provider (JWT/session/SSO) plugs in later — swap :func:`get_current_user` and
everything downstream becomes truly authenticated with no further changes.

v1 resolves the user id from the ``X-User-Id`` request header, falling back to
``"default"`` so single-user/local usage just works.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

DEFAULT_USER_ID = "default"
USER_ID_HEADER = "X-User-Id"


@dataclass(frozen=True)
class UserContext:
    user_id: str


def get_current_user(request: Request) -> UserContext:
    """FastAPI dependency → the calling user's context."""
    uid = (request.headers.get(USER_ID_HEADER) or "").strip() or DEFAULT_USER_ID
    return UserContext(user_id=uid)
