import os

# ── Auth test posture (set BEFORE any app import) ─────────────────────────────
# Fixed keys so JWT mint/verify and at-rest encryption are stable within a run;
# a known bootstrap admin (id="default") so real-auth tests can log in. These are
# test-only values, never used outside pytest.
os.environ.setdefault("STERLING_SECRET_KEY", "test-secret-key-fixed-0123456789-abcdefghij")
os.environ.setdefault("STERLING_JWT_SECRET", "test-jwt-secret-fixed-0123456789-abcdefghij")
os.environ.setdefault("STERLING_ADMIN_USERNAME", "testadmin")
os.environ.setdefault("STERLING_ADMIN_PASSWORD", "test-admin-password-xyz-123")

import numpy as np
import pytest
from typing import List
from app.schemas.market import Candle


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "real_auth: exercise the real JWT auth gate (skip the fake-identity "
        "fixture so 401/403 enforcement can be asserted)",
    )


def make_candles(n: int = 100, base: float = 30000.0, trend: float = 10.0) -> List[Candle]:
    np.random.seed(42)
    candles = []
    price = base
    for i in range(n):
        price += trend + np.random.normal(0, base * 0.002)
        o = price - abs(np.random.normal(0, base * 0.001))
        c = price + abs(np.random.normal(0, base * 0.001))
        h = max(o, c) + abs(np.random.normal(0, base * 0.0005))
        l = min(o, c) - abs(np.random.normal(0, base * 0.0005))
        candles.append(
            Candle(
                timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                open=round(o, 2), high=round(h, 2),
                low=round(l, 2), close=round(c, 2),
                volume=float(np.random.uniform(100, 500)),
            )
        )
    return candles


def make_bearish_candles(n: int = 100, base: float = 30000.0) -> List[Candle]:
    return make_candles(n, base, trend=-50.0)


def _default_risk():
    from app.schemas.risk import RiskParams
    from app.core.config import settings
    return RiskParams(
        capital=settings.default_capital,
        max_position_pct=settings.max_position_pct,
        max_contracts=settings.max_contracts,
    )


def _reset_exchange_store(eas) -> None:
    """Reset both exchange-account memory and its SQLite write-through table."""
    from app.services import db

    try:
        if db._available:
            with db._conn() as connection:
                connection.execute("DELETE FROM exchange_configs")
    except Exception:
        pass
    eas._configs.clear()
    eas._loaded = False
    eas.bootstrap()


def _reset_user_store() -> None:
    """Reset the users table + in-memory store, then reseed the bootstrap admin."""
    from app.services import db
    from app.services.auth import user_store

    try:
        if db._available:
            with db._conn() as connection:
                connection.execute("DELETE FROM users")
    except Exception:
        pass
    user_store.clear()
    user_store.bootstrap()


@pytest.fixture(autouse=True)
def reset_global_stores():
    """Reset every module-level and persisted mutable test store."""
    from app.services import paper_store, eval_history, arrow_store
    from app.services import alert_store, pnl_history, webhook_store
    from app.services import exchange_account_store as eas
    from app.services.exchanges.kite import accounts as kite_accounts
    import app.api.v1.endpoints.config as config_ep
    from app.engines.directional.regime_engine import _REGIME_CACHE
    from app.engines.directional.signal_engine import _SIGNAL_CACHE

    paper_store._positions.clear()
    paper_store._loaded = True
    eval_history.clear()
    arrow_store.clear()
    arrow_store._bootstrapped = True
    alert_store.clear()
    alert_store._loaded = True
    pnl_history.clear()
    pnl_history._loaded = True
    webhook_store.clear()
    webhook_store._loaded = True
    _reset_exchange_store(eas)
    _reset_user_store()
    kite_accounts.clear()
    config_ep._risk = _default_risk()
    _REGIME_CACHE.clear()
    _SIGNAL_CACHE.clear()

    yield

    paper_store._positions.clear()
    eval_history.clear()
    arrow_store.clear()
    arrow_store._bootstrapped = False
    alert_store.clear()
    pnl_history.clear()
    webhook_store.clear()
    _reset_exchange_store(eas)
    _reset_user_store()
    kite_accounts.clear()
    config_ep._risk = _default_risk()
    _REGIME_CACHE.clear()
    _SIGNAL_CACHE.clear()


@pytest.fixture(autouse=True)
def _fake_auth(request, monkeypatch):
    """Neutralize the global auth gate for the vast majority of tests, which
    predate auth and assume an implicit ``"default"`` identity.

    We replace the single identity seam ``auth.authenticate_request`` with one
    that reads the legacy ``X-User-Id`` header (so the existing multi-tenant
    isolation tests still switch tenants) and always resolves to an admin. This
    is the test analogue of ``app.dependency_overrides`` — the production code
    keeps NO header path. Tests marked ``real_auth`` opt out and exercise the
    real JWT gate (to assert 401/403)."""
    if "real_auth" in request.keywords:
        return
    from app.core import auth

    async def _fake(req):
        uid = (req.headers.get("X-User-Id") or "").strip() or auth.DEFAULT_USER_ID
        return auth.UserContext(user_id=uid, username=uid, role="admin")

    monkeypatch.setattr(auth, "authenticate_request", _fake)


@pytest.fixture
def real_admin_token():
    """A genuine signed access token for the seeded bootstrap admin. Use in
    ``real_auth``-marked tests."""
    from app.core import tokens
    from app.services.auth import user_store
    u = user_store.get_by_id(user_store.DEFAULT_ADMIN_ID)
    assert u is not None, "bootstrap admin not seeded"
    return tokens.mint_access(u.id, u.username, u.role, u.token_version)


@pytest.fixture
def auth_headers(real_admin_token):
    return {"Authorization": f"Bearer {real_admin_token}"}


@pytest.fixture
def unauth_client():
    """A TestClient with the real auth gate active (no fake identity). Pair with
    ``@pytest.mark.real_auth``."""
    from fastapi.testclient import TestClient
    from main import create_app
    return TestClient(create_app())
