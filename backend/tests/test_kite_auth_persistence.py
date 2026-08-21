"""Kite session persistence: token lifetime, signed login state, silent renewal.

These cover the promise "log in once, and the app keeps working" — the parts that
are ours to keep. Zerodha's daily 2FA is not ours to remove, so nothing here
pretends a first token can be minted headlessly.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.services.exchanges.kite import accounts as kite_accounts
from app.services.exchanges.kite import auth as kite_auth
from app.services.exchanges.kite import session as kite_session
from app.services.exchanges.kite.errors import KiteTokenError
from app.services.exchanges.kite.models import KiteAccountCreate
from main import create_app


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


# ─── Token lifetime ───────────────────────────────────────────────────────────
def test_expiry_is_the_next_0600_ist_boundary():
    # A token minted during market hours lives until 06:00 the next morning.
    assert kite_session.token_expiry_ms(_ms("2026-08-22T09:20:00+05:30")) == \
        _ms("2026-08-23T06:00:00+05:30")


def test_expiry_before_0600_is_the_same_morning_not_a_full_day():
    """Kite's reset is a wall-clock event, not a rolling 24h window — a token
    minted at 05:30 IST is dead in 30 minutes, and must not claim a day."""
    issued = _ms("2026-08-22T05:30:00+05:30")
    assert kite_session.token_expiry_ms(issued) == _ms("2026-08-22T06:00:00+05:30")


def test_unknown_expiry_is_not_treated_as_immortal():
    assert kite_session.is_expired(None) is False        # unknown, not expired…
    acct = kite_accounts._Account(id="X", user_id="u", label="L", api_key="k")
    acct.access_token_enc = "enc"
    assert acct.token_is_live is False                   # …and never trusted either


def test_legacy_row_without_expiry_derives_one_from_its_login_time():
    """Rows written before expiry tracking must not force a re-login: the boundary
    is reconstructible from last_login_at_ms alone."""
    acct = kite_accounts._Account(id="X", user_id="u", label="L", api_key="k")
    acct.access_token_enc = "enc"
    acct.last_login_at_ms = _ms("2026-08-22T09:20:00+05:30")
    assert acct.token_expires_at == _ms("2026-08-23T06:00:00+05:30")


# ─── Signed login state ───────────────────────────────────────────────────────
def test_state_round_trips_user_and_account():
    st = kite_session.make_state("alice", "KITE-1")
    assert kite_session.parse_state(st) == ("alice", "KITE-1")


def test_tampered_state_is_rejected():
    st = kite_session.make_state("alice", "KITE-1")
    forged = kite_session.make_state("bob", "KITE-9")
    # Swapping the payload for another user's while keeping a valid-looking shape
    # must not authenticate — the signature covers the identity.
    assert kite_session.parse_state(st[:-4] + forged[-4:]) is None
    assert kite_session.parse_state("not-base64-at-all") is None
    assert kite_session.parse_state("") is None


def test_state_expires():
    stale = kite_session.make_state("alice", "KITE-1",
                                    issued_at_ms=kite_session.now_ms() - kite_session.STATE_TTL_MS - 1)
    assert kite_session.parse_state(stale) is None


def test_login_url_carries_state_through_redirect_params():
    url = kite_session.login_url("MYKEY", state="ST8")
    assert "api_key=MYKEY" in url
    # Kite appends redirect_params verbatim to the redirect URL.
    assert "redirect_params=state%3DST8" in url


# ─── Store ────────────────────────────────────────────────────────────────────
@pytest.fixture()
def acct():
    kite_accounts.clear()
    a = kite_accounts.add("u1", KiteAccountCreate(
        label="A", api_key="ak", api_secret="sec", is_paper=False))
    return a


def test_save_session_stamps_the_validity_window(acct):
    kite_accounts.save_session("u1", acct.id, access_token="AT")
    assert acct.token_expires_at_ms == kite_session.token_expiry_ms(acct.last_login_at_ms)
    assert acct.token_is_live is True


def test_a_freshly_issued_token_needs_no_network_proof(acct):
    """Kite just handed us this token, so the first status poll must not spend a
    round-trip asking whether it works."""
    kite_accounts.save_session("u1", acct.id, access_token="AT")
    assert kite_accounts.validated_age_ms(acct.id) is not None


def test_clear_session_drops_the_window_and_the_proof(acct):
    kite_accounts.save_session("u1", acct.id, access_token="AT")
    kite_accounts.clear_session("u1", acct.id)
    assert acct.token_expires_at_ms is None
    assert acct.token_is_live is False
    assert kite_accounts.validated_age_ms(acct.id) is None


# ─── ensure_session ───────────────────────────────────────────────────────────
async def test_recent_validation_skips_the_network(acct, monkeypatch):
    kite_accounts.save_session("u1", acct.id, access_token="AT")
    called = []
    monkeypatch.setattr(kite_accounts, "acquire_client",
                        AsyncMock(side_effect=lambda a: called.append(1)))
    health = await kite_auth.ensure_session("u1", acct)
    assert health.connected is True
    assert health.validated is False          # answered from the stored window
    assert called == []                       # and it cost nothing


async def test_stale_proof_revalidates_against_kite(acct, monkeypatch):
    kite_accounts.save_session("u1", acct.id, access_token="AT")
    kite_accounts.forget_validation(acct.id)
    client = MagicMock()
    client.get_profile = AsyncMock(return_value={"user_id": "AB1234", "user_name": "Trader"})
    monkeypatch.setattr(kite_accounts, "acquire_client", AsyncMock(return_value=client))
    health = await kite_auth.ensure_session("u1", acct)
    assert (health.connected, health.validated, health.kite_user_id) == (True, True, "AB1234")


async def test_expired_window_renews_silently_when_a_refresh_token_exists(acct, monkeypatch):
    kite_accounts.save_session("u1", acct.id, access_token="OLD", refresh_token="RT")
    acct.token_expires_at_ms = kite_session.now_ms() - 1        # window has closed
    client = MagicMock()
    client.renew_access_token = AsyncMock(return_value={"access_token": "NEW", "user_id": "AB1234"})
    client.close = AsyncMock()
    monkeypatch.setattr(kite_accounts, "build_client", lambda a: client)
    health = await kite_auth.ensure_session("u1", acct)
    assert (health.connected, health.auto_renewed) == (True, True)
    assert acct.access_token == "NEW"
    assert acct.token_is_live is True                            # window re-stamped


async def test_expired_window_without_a_refresh_token_clears_the_dead_token(acct, monkeypatch):
    kite_accounts.save_session("u1", acct.id, access_token="OLD")   # no refresh_token
    acct.token_expires_at_ms = kite_session.now_ms() - 1
    monkeypatch.setattr(kite_accounts, "acquire_client",
                        AsyncMock(side_effect=AssertionError("must not call Kite")))
    health = await kite_auth.ensure_session("u1", acct)
    assert health.connected is False
    assert acct.connected is False        # corpse dropped → UI offers "Log in"
    assert "06:00 IST" in health.message


async def test_a_rejected_token_is_renewed_rather_than_reported(acct, monkeypatch):
    """Kite can revoke a token inside its window (logout elsewhere). If we can
    renew, the caller should never see the interruption."""
    kite_accounts.save_session("u1", acct.id, access_token="OLD", refresh_token="RT")
    kite_accounts.forget_validation(acct.id)
    live = MagicMock()
    live.get_profile = AsyncMock(side_effect=KiteTokenError("token rejected"))
    monkeypatch.setattr(kite_accounts, "acquire_client", AsyncMock(return_value=live))
    renewer = MagicMock()
    renewer.renew_access_token = AsyncMock(return_value={"access_token": "NEW"})
    renewer.close = AsyncMock()
    monkeypatch.setattr(kite_accounts, "build_client", lambda a: renewer)
    health = await kite_auth.ensure_session("u1", acct)
    assert (health.connected, health.auto_renewed) == (True, True)


async def test_an_unreachable_kite_does_not_destroy_a_good_session(acct, monkeypatch):
    """A network blip is not an invalid token — clearing it here would force a
    pointless re-login every time the venue hiccups."""
    kite_accounts.save_session("u1", acct.id, access_token="AT")
    kite_accounts.forget_validation(acct.id)
    client = MagicMock()
    client.get_profile = AsyncMock(side_effect=RuntimeError("connection reset"))
    monkeypatch.setattr(kite_accounts, "acquire_client", AsyncMock(return_value=client))
    health = await kite_auth.ensure_session("u1", acct)
    assert health.connected is False
    assert acct.access_token == "AT"      # token survives


# ─── Environment seeding ──────────────────────────────────────────────────────
def test_seed_from_env_creates_and_activates_an_account(monkeypatch):
    kite_accounts.clear()
    monkeypatch.setenv("KITE_API_KEY", "envkey")
    monkeypatch.setenv("KITE_API_SECRET", "envsecret")
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "envtoken")
    acct_id = kite_auth.seed_from_env()
    a = kite_accounts.get("default", acct_id)
    assert a.is_active and a.api_key == "envkey" and a.access_token == "envtoken"
    # An env token has no proof Kite ever accepted it — the first call must check.
    assert kite_accounts.validated_age_ms(acct_id) is None


def test_seed_from_env_is_idempotent(monkeypatch):
    kite_accounts.clear()
    monkeypatch.setenv("KITE_API_KEY", "envkey")
    monkeypatch.setenv("KITE_API_SECRET", "envsecret")
    first = kite_auth.seed_from_env()
    second = kite_auth.seed_from_env()
    assert first == second
    assert len(kite_accounts.list_accounts("default")) == 1


def test_seed_from_env_never_clobbers_a_live_browser_login(monkeypatch):
    """The token in .env goes stale daily. A session obtained through the browser
    today must survive a restart, not be overwritten by yesterday's value."""
    kite_accounts.clear()
    monkeypatch.setenv("KITE_API_KEY", "envkey")
    monkeypatch.setenv("KITE_API_SECRET", "envsecret")
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "STALE")
    acct_id = kite_auth.seed_from_env()
    kite_accounts.save_session("default", acct_id, access_token="FRESH")
    kite_auth.seed_from_env()
    assert kite_accounts.get("default", acct_id).access_token == "FRESH"


def test_seed_from_env_without_credentials_is_a_no_op(monkeypatch):
    kite_accounts.clear()
    monkeypatch.delenv("KITE_API_KEY", raising=False)
    monkeypatch.delenv("KITE_API_SECRET", raising=False)
    assert kite_auth.seed_from_env() is None


# ─── Router ───────────────────────────────────────────────────────────────────
def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.close = AsyncMock(return_value=None)
    return a


@pytest.fixture()
def client():
    app = create_app()
    app.state.adapter = _mock_adapter()
    with TestClient(app) as c:
        c.app.state.adapter = app.state.adapter
        yield c


def _add(client, headers=None):
    r = client.post("/api/v1/kite/accounts", headers=headers or {}, json={
        "label": "A", "api_key": "apikey123", "api_secret": "topsecret", "is_paper": True})
    assert r.status_code == 200, r.text
    return r.json()


def test_login_url_returns_a_state_and_the_redirect_to_register(client):
    _add(client, headers={"X-User-Id": "alice"})
    body = client.get("/api/v1/kite/login-url", headers={"X-User-Id": "alice"}).json()
    assert body["state"]
    assert body["redirect_uri"] == "/api/v1/kite/callback"
    assert "redirect_params=state%3D" in body["login_url"]
    assert kite_session.parse_state(body["state"])[0] == "alice"


def test_callback_binds_the_session_to_the_state_not_the_url(client, monkeypatch):
    """The registered redirect URL is one static value shared by every tenant, so
    the callback must take the identity from the signature it cannot forge."""
    alice = _add(client, headers={"X-User-Id": "alice"})
    _add(client, headers={"X-User-Id": "bob"})
    state = client.get("/api/v1/kite/login-url",
                       headers={"X-User-Id": "alice"}).json()["state"]

    fake = MagicMock()
    fake.generate_session = AsyncMock(return_value={
        "access_token": "AT", "user_id": "AB1234", "user_name": "Trader"})
    fake.close = AsyncMock()
    monkeypatch.setattr(kite_accounts, "build_client", lambda a: fake)

    # `uid=bob` in the URL must be ignored in favour of the signed state.
    r = client.get(f"/api/v1/kite/callback?request_token=rt&status=success&state={state}&uid=bob")
    assert r.status_code == 200
    assert kite_accounts.get("alice", alice["id"]).access_token == "AT"
    assert not any(a.connected for a in kite_accounts.list_accounts("bob"))


def test_callback_rejects_a_forged_state(client):
    _add(client, headers={"X-User-Id": "alice"})
    r = client.get("/api/v1/kite/callback?request_token=rt&status=success&state=deadbeef")
    assert r.status_code == 400
    assert "expired" in r.text.lower()


def test_callback_announces_the_session_to_the_app_tab(client, monkeypatch):
    """Without this the app waits up to 30s for its next status poll before the
    badge flips — which reads as "the login didn't work"."""
    _add(client, headers={"X-User-Id": "alice"})
    state = client.get("/api/v1/kite/login-url",
                       headers={"X-User-Id": "alice"}).json()["state"]
    fake = MagicMock()
    fake.generate_session = AsyncMock(return_value={"access_token": "AT", "user_id": "AB1234"})
    fake.close = AsyncMock()
    monkeypatch.setattr(kite_accounts, "build_client", lambda a: fake)
    r = client.get(f"/api/v1/kite/callback?request_token=rt&status=success&state={state}")
    assert "sterling-kite-auth" in r.text
    assert "kite-connected" in r.text


def test_status_reports_the_validity_window(client, monkeypatch):
    acc = _add(client, headers={"X-User-Id": "alice"})
    kite_accounts.save_session("alice", acc["id"], access_token="AT", kite_user_id="AB1234")
    body = client.get("/api/v1/kite/status", headers={"X-User-Id": "alice"}).json()
    assert body["connected"] is True
    assert body["token_expires_at_ms"] == kite_session.token_expiry_ms(
        kite_accounts.get("alice", acc["id"]).last_login_at_ms)
    assert body["expires_in_s"] > 0
    assert body["validated"] is False        # trusted the window, no round-trip
