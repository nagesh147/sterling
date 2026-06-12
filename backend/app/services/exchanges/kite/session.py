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

import hashlib

from . import constants as K


def login_url(api_key: str) -> str:
    """The URL to send the user to for the Kite login handshake."""
    return f"{K.LOGIN_URL_BASE}?api_key={api_key}&v={K.KITE_VERSION}"


def checksum(api_key: str, request_token: str, api_secret: str) -> str:
    """SHA-256 of api_key + request_token + api_secret (Kite session checksum)."""
    raw = f"{api_key}{request_token}{api_secret}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
