"""
Kite login/session helpers (pure functions — no I/O).

Kite Connect uses a daily login handshake:
  1. Redirect the user to ``login_url(api_key)``.
  2. Kite redirects back to the app's registered redirect URL with a ``request_token``.
  3. The backend exchanges ``request_token`` for an ``access_token`` by POSTing
     ``{api_key, request_token, checksum}`` to ``/session/token`` where
     ``checksum = SHA256(api_key + request_token + api_secret)``.

The network exchange itself lives on :class:`KiteClient` (it owns the http client);
these helpers are isolated so the security-critical checksum is trivially unit-tested.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import urlencode

from . import constants as K


def login_url(api_key: str, *, state: str = "") -> str:
    """The URL to send the user to for the Kite login handshake.

    When ``state`` is given it is round-tripped through Kite's ``redirect_params``,
    which Kite appends verbatim to the redirect URL. That is how the unauthenticated
    ``/callback`` learns which app user and account this login belongs to (see
    :func:`make_state`) without trusting a caller-supplied ``uid``.
    """
    url = f"{K.LOGIN_URL_BASE}?api_key={api_key}&v={K.KITE_VERSION}"
    if state:
        url += "&" + urlencode({"redirect_params": urlencode({"state": state})})
    return url


def checksum(api_key: str, request_token: str, api_secret: str) -> str:
    """SHA-256 of api_key + request_token + api_secret (Kite session checksum)."""
    raw = f"{api_key}{request_token}{api_secret}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# ─── Token lifetime ───────────────────────────────────────────────────────────
# Kite Connect access tokens are day-scoped: every token issued is invalidated at
# 06:00 IST the following morning, regardless of when it was minted. Knowing that
# boundary locally is what lets the app stop asking Kite "is this still good?" on
# every status poll — it only has to ask once per validity window.
IST = timezone(timedelta(hours=5, minutes=30))
TOKEN_RESET_HOUR_IST = 6


def now_ms() -> int:
    return int(time.time() * 1000)


def token_expiry_ms(issued_at_ms: Optional[int] = None) -> int:
    """The epoch-ms of the next 06:00 IST boundary at/after ``issued_at_ms``.

    A token minted at 09:20 IST expires 06:00 the next day; one minted at 05:30
    IST expires at 06:00 the *same* day (30 minutes later) — Kite's reset is a
    wall-clock event, not a rolling 24h window.
    """
    at = datetime.fromtimestamp((issued_at_ms if issued_at_ms is not None else now_ms()) / 1000, tz=IST)
    boundary = at.replace(hour=TOKEN_RESET_HOUR_IST, minute=0, second=0, microsecond=0)
    if at >= boundary:
        boundary += timedelta(days=1)
    return int(boundary.timestamp() * 1000)


def is_expired(expires_at_ms: Optional[int], at_ms: Optional[int] = None) -> bool:
    """True when the token's validity window has closed. ``None`` expiry is
    *unknown*, not immortal — callers must fall back to a network validation."""
    if not expires_at_ms:
        return False
    return (at_ms if at_ms is not None else now_ms()) >= expires_at_ms


# ─── Signed login state ───────────────────────────────────────────────────────
# Kite redirects the browser to our callback with no auth header, so the callback
# must learn *which* app user started the login from the URL itself. A plaintext
# ``?uid=`` would let anyone drive another tenant's session, so we round-trip an
# HMAC-signed, short-lived, self-describing token through Kite's
# ``redirect_params`` instead.
STATE_TTL_MS = 15 * 60 * 1000
_SEP = "\x1f"


def _state_key() -> bytes:
    secret = os.environ.get("STERLING_SECRET_KEY") or "sterling-dev-insecure-key"
    return hashlib.sha256(("kite-login-state:" + secret).encode("utf-8")).digest()


def make_state(user_id: str, account_id: str, *, issued_at_ms: Optional[int] = None) -> str:
    """An opaque, tamper-evident token binding a login attempt to (user, account)."""
    expires = (issued_at_ms if issued_at_ms is not None else now_ms()) + STATE_TTL_MS
    payload = _SEP.join((user_id, account_id, str(expires)))
    sig = hmac.new(_state_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    raw = _SEP.join((payload, sig)).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def parse_state(state: str, *, at_ms: Optional[int] = None) -> Optional[Tuple[str, str]]:
    """``(user_id, account_id)`` for a valid, unexpired state — else ``None``."""
    if not state:
        return None
    try:
        padded = state + "=" * (-len(state) % 4)
        parts = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8").split(_SEP)
        if len(parts) != 4:
            return None
        user_id, account_id, expires_s, sig = parts
        payload = _SEP.join((user_id, account_id, expires_s))
        want = hmac.new(_state_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, want):
            return None
        if (at_ms if at_ms is not None else now_ms()) >= int(expires_s):
            return None
        return user_id, account_id
    except Exception:
        return None
