"""A failed CHECK is not a lapsed session.

`connected: false` meant two completely different things: "Kite rejected this
token, log in again" and "we could not reach Kite to ask". The stored token was
already deliberately kept in the second case — the comment on that branch has
said so for a long time — but the answer sent to the UI was identical.

So a single dropped request surfaced as a "Kite session expired" modal over a
session that was entirely fine, and the operator went hunting a `request_token`
they did not need. `transient` separates the two.
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.exchanges.kite import auth
from app.services.exchanges.kite.errors import KiteTokenError


def test_session_health_defaults_to_not_transient():
    # Only the network branch may set it. Defaulting the other way would make
    # every real expiry look recoverable.
    h = auth.SessionHealth(False, "nope")
    assert h.transient is False


@pytest.mark.asyncio
async def test_an_unreachable_kite_is_transient_and_keeps_the_token(monkeypatch):
    acct = _account()
    cleared: list[str] = []

    with patch.object(auth.kite_accounts, "acquire_client", new=AsyncMock(
                          return_value=_client(raises=OSError("connection reset")))), \
         patch.object(auth.kite_accounts, "clear_session",
                      side_effect=lambda *a, **k: cleared.append("cleared")), \
         patch.object(auth.kite_accounts, "release_client", new=AsyncMock()), \
         patch.object(auth.kite_accounts, "validated_age_ms", return_value=None):
        health = await auth.ensure_session("u1", acct)

    assert health.connected is False
    assert health.transient is True, "a dropped request is not an expiry"
    assert cleared == [], "the token must survive a failed check"
    assert "reach" in health.message.lower()


@pytest.mark.asyncio
async def test_a_token_kite_REFUSES_is_not_transient(monkeypatch):
    # The opposite case, and the reason this cannot simply default to true:
    # treating a refusal as recoverable leaves the operator waiting for a
    # reconnection that is never coming.
    acct = _account()
    with patch.object(auth.kite_accounts, "acquire_client", new=AsyncMock(
                          return_value=_client(raises=KiteTokenError("Token is invalid")))), \
         patch.object(auth.kite_accounts, "clear_session"), \
         patch.object(auth.kite_accounts, "release_client", new=AsyncMock()), \
         patch.object(auth.kite_accounts, "validated_age_ms", return_value=None), \
         patch.object(auth, "renew", new=AsyncMock(return_value=None)):
        health = await auth.ensure_session("u1", acct)

    assert health.connected is False
    assert health.transient is False, "a refusal needs a real re-login"


@pytest.mark.asyncio
async def test_a_healthy_session_is_not_transient():
    acct = _account()
    with patch.object(auth.kite_accounts, "acquire_client", new=AsyncMock(
                          return_value=_client(profile={"user_id": "AA1", "user_name": "N"}))), \
         patch.object(auth.kite_accounts, "mark_validated"), \
         patch.object(auth.kite_accounts, "validated_age_ms", return_value=None):
        health = await auth.ensure_session("u1", acct)

    assert health.connected is True
    assert health.transient is False


# ─── helpers ────────────────────────────────────────────────────────────────
def _account():
    class _A:
        id = "acct-1"
        api_key = "k"
        api_secret = "s"
        access_token_enc = "enc"
        refresh_token = ""
        is_paper = False
        kite_user_id = ""
        user_name = ""
        # Comfortably inside the window, so the code reaches the network branch.
        token_expires_at = 4_000_000_000_000
    return _A()


def _client(*, profile=None, raises=None):
    c = AsyncMock()
    if raises is not None:
        c.get_profile = AsyncMock(side_effect=raises)
    else:
        c.get_profile = AsyncMock(return_value=profile or {})
    return c
