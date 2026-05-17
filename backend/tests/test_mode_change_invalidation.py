"""
Regression test for the mode-change cache invalidation bug.

Before fix: SSE served signals computed under the *previous* mode for up to
~75 s after a mode swap (45 s snap-cache TTL + 30 s background-refresh window).
Result: INTRADAY-mode UI rendering scalping signal IDs (BTCFUT-SC-...).

After fix: PUT /trading-mode atomically clears snapshot_cache and
_active_signal_ids so the next SSE/REST tick has nothing stale to serve.
"""
from __future__ import annotations
import pytest

from app.services import snapshot_cache
from app.api.v1.endpoints.directional import _active_signal_ids


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import create_app
    from app.core.trading_mode import MODES, DEFAULT_MODE
    from unittest.mock import AsyncMock

    app = create_app()
    app.state.trading_mode = MODES[DEFAULT_MODE]

    mock_adapter = AsyncMock()
    mock_adapter.ping = AsyncMock(return_value=True)
    app.state.adapter = mock_adapter

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_mode_change_clears_snapshot_cache(client):
    # Seed a stale snapshot for BTC (as if scalping mode had just populated it)
    snapshot_cache.put(
        sym="BTC", spot_price=80_000.0, ivr=50.0,
        green_arrow=False, red_arrow=True,
        current_state="ENTRY_ARMED_PULLBACK",
        direction="short", regime="BEAR_TREND",
        score_long=0.0, score_short=100.0,
        stop_price=80_800.0, target_price=79_200.0,
        atr=400.0, signal_score=18.0, signal_strength="STRONG",
    )
    assert snapshot_cache.get("BTC") is not None

    # Seed an old-mode signal id
    _active_signal_ids["BTC_scalping_short"] = "BTCFUT-SC-LL6"
    assert _active_signal_ids.get("BTC_scalping_short") == "BTCFUT-SC-LL6"

    # Switch mode → caches must be wiped
    resp = client.put("/api/v1/config/trading-mode", json={"name": "intraday"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "intraday"

    assert snapshot_cache.get("BTC") is None, "snapshot cache must be cleared on mode change"
    assert "BTC_scalping_short" not in _active_signal_ids, (
        "_active_signal_ids must be cleared so old-mode IDs cannot leak through"
    )


def test_mode_change_to_same_mode_still_clears(client):
    """Defensive: even a no-op mode change clears caches. Cheap and safer."""
    snapshot_cache.put(
        sym="ETH", spot_price=3_000.0, ivr=40.0,
        green_arrow=False, red_arrow=False,
        current_state="IDLE",
    )
    _active_signal_ids["ETH_swing_long"] = "ETHFUT-SW-AAA"

    resp = client.put("/api/v1/config/trading-mode", json={"name": "swing"})
    assert resp.status_code == 200

    assert snapshot_cache.get("ETH") is None
    assert "ETH_swing_long" not in _active_signal_ids
