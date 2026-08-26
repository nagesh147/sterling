"""
JWT mint / verify — PyJWT, HS256.

Access + refresh tokens carry: ``sub`` (our user id), ``username``, ``role``,
``typ`` (access|refresh), ``ver`` (== ``users.token_version`` — bump it to
invalidate every outstanding token for a user, i.e. logout-all), ``iat``,
``exp``, ``iss`` ("sterling").

Decode always passes an explicit ``algorithms=[...]`` allowlist — this is the
mitigation for the classic JWT algorithm-confusion attack (a token forged with
``alg: none`` or an RS/HS swap is rejected). Signing key comes from
:func:`app.core.security.get_jwt_key`.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict

import jwt

from app.core.security import get_jwt_key

_ALG = "HS256"
_ISS = "sterling"


def _ttl(name: str, default: int) -> int:
    try:
        return int((os.environ.get(name, "") or "").strip() or default)
    except Exception:
        return default


ACCESS_TTL_S = _ttl("STERLING_ACCESS_TTL_S", 30 * 60)          # 30 minutes
REFRESH_TTL_S = _ttl("STERLING_REFRESH_TTL_S", 7 * 24 * 60 * 60)  # 7 days


class TokenError(Exception):
    """Raised on any invalid/expired/malformed/wrong-type token."""


def _mint(sub: str, username: str, role: str, ver: int, typ: str, ttl: int) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "username": username,
        "role": role,
        "typ": typ,
        "ver": int(ver),
        "iat": now,
        "exp": now + ttl,
        "iss": _ISS,
    }
    return jwt.encode(payload, get_jwt_key(), algorithm=_ALG)


def mint_access(sub: str, username: str, role: str, ver: int) -> str:
    return _mint(sub, username, role, ver, "access", ACCESS_TTL_S)


def mint_refresh(sub: str, username: str, role: str, ver: int) -> str:
    return _mint(sub, username, role, ver, "refresh", REFRESH_TTL_S)


def decode(token: str, expected_typ: str) -> Dict[str, Any]:
    """Verify signature/expiry/issuer and that the token is of ``expected_typ``.

    Raises :class:`TokenError` on any failure. ``algorithms=[_ALG]`` is explicit
    on purpose — never trust the token's own ``alg`` header."""
    try:
        claims = jwt.decode(
            token,
            get_jwt_key(),
            algorithms=[_ALG],
            issuer=_ISS,
            options={"require": ["exp", "iat", "sub", "typ", "ver"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if claims.get("typ") != expected_typ:
        raise TokenError(f"expected {expected_typ} token, got {claims.get('typ')!r}")
    return claims
