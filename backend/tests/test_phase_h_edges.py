"""
Phase H — algo-loop edge-case test backfill.

Targets specific failure modes that the happy-path P0 tests don't cover:

  H1  Cooldown persistence — _algo_last_ordered survives across the algo
      function being invoked twice in quick succession.
  H2  has_options + futures-only behaviour — instruments without options
      still produce valid futures algo orders (no NPE, correct symbol).
  H3  Timeout vs other-error handling on place_order — both paths must
      end up enqueuing a retry rather than crashing the SSE refresher.
  H4  Preflight idempotency — the same idem_key submitted twice must
      short-circuit on the second submission and reuse the first order_id.
"""
from __future__ import annotations
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import (
    exchange_account_store as eas,
    live_safety,
    paper_store,
    snapshot_cache,
)
from app.services.snapshot_cache import SnapshotEntry
from app.core.trading_mode import MODES
from main import _auto_place_algo_order, _algo_last_ordered


def _seed_active_exchange():
    from app.schemas.exchange_config import ExchangeConfigCreate
    cfg = eas.add_exchange(ExchangeConfigCreate(
        name="delta_india", display_name="Delta India",
        api_key="REAL-KEY", api_secret="REAL-SECRET",
        is_paper=False,
    ))
    eas.set_active(cfg.id)


def _make_snap(sym: str = "BTC", direction: str = "long") -> SnapshotEntry:
    return SnapshotEntry(
        sym=sym, spot_price=100_000.0, ivr=50.0,
        green_arrow=False, red_arrow=True,
        current_state="ENTRY_ARMED_PULLBACK",
        computed_at_ms=int(time.time() * 1000),
        direction=direction, regime="BULL_TREND",
        score_long=100.0 if direction == "long" else 0.0,
        score_short=0.0 if direction == "long" else 100.0,
        atr=1_000.0, adx=25.0, atr_percentile=55.0,
        signal_score=18.0, signal_strength="STRONG",
    )


@pytest.fixture(autouse=True)
def _reset():
    _algo_last_ordered.clear()
    live_safety.reset_all_for_tests()
    snapshot_cache._cache.clear()
    yield
    _algo_last_ordered.clear()
    live_safety.reset_all_for_tests()


@pytest.fixture
def fake_adapter():
    a = MagicMock()
    a.get_product_id = AsyncMock(return_value=12345)
    a.set_leverage = AsyncMock(return_value=None)
    a.get_index_price = AsyncMock(return_value=100_000.0)
    a.place_order = AsyncMock(return_value={
        "id": "ORD-H-1", "average_fill_price": 100_010.0, "state": "filled",
    })
    return a


# ── H1: Cooldown persistence ────────────────────────────────────────────────


class TestH1CooldownPersistence:
    @pytest.mark.asyncio
    async def test_second_call_within_cooldown_skipped(self, fake_adapter):
        _seed_active_exchange()
        app = MagicMock()
        app.state.algo_router_mode = "live"
        app.state.correlation_tracker = None

        with patch(
            "app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
            return_value=fake_adapter,
        ):
            await _auto_place_algo_order(app, "BTC", _make_snap(), MODES["swing"])
            # Same direction, same minute, idempotency would also block.
            # Force-clear idem so cooldown is the only gate left.
            live_safety._IDEMPOTENCY_CACHE.clear()
            await _auto_place_algo_order(app, "BTC", _make_snap(), MODES["swing"])

        # Cooldown stops the second call from reaching the exchange
        assert fake_adapter.place_order.call_count == 1
        assert "BTC_long" in _algo_last_ordered


# ── H2: futures-only mode + has_options behaviour ──────────────────────────


class TestH2FuturesOnlyMode:
    @pytest.mark.asyncio
    async def test_xrp_no_options_still_places_futures(self, fake_adapter):
        """XRP has has_options=False — algo path should still place a
        futures-mode order using delta_perp_symbol."""
        _seed_active_exchange()
        app = MagicMock()
        app.state.algo_router_mode = "live"
        app.state.correlation_tracker = None

        snap = _make_snap(sym="XRP")
        # XRP price is ~$0.50 ish in real life; signal still fires
        snap.spot_price = 0.50
        snap.atr = 0.005

        with patch(
            "app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
            return_value=fake_adapter,
        ):
            await _auto_place_algo_order(app, "XRP", snap, MODES["swing"])

        fake_adapter.place_order.assert_called_once()
        # Confirm it asked for the right exchange symbol (XRP-specific)
        kwargs = fake_adapter.place_order.call_args.kwargs
        assert "XRP" in kwargs.get("symbol", "").upper()


# ── H3: Timeout vs other-error ─────────────────────────────────────────────


class TestH3ErrorPaths:
    @pytest.mark.asyncio
    async def test_timeout_enqueues_retry_no_crash(self):
        _seed_active_exchange()
        app = MagicMock()
        app.state.algo_router_mode = "live"
        app.state.correlation_tracker = None

        fake = MagicMock()
        fake.get_product_id = AsyncMock(return_value=12345)
        fake.set_leverage = AsyncMock(return_value=None)
        fake.get_index_price = AsyncMock(return_value=100_000.0)
        fake.place_order = AsyncMock(side_effect=asyncio.TimeoutError("read timeout"))

        with patch(
            "app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
            return_value=fake,
        ):
            # Must not raise — the router catches & enqueues
            await _auto_place_algo_order(app, "BTC", _make_snap(), MODES["swing"])

        # Retry queue should now contain the failed order
        items = live_safety.list_retries(include_poison=True)
        assert len(items) == 1
        assert "timeout" in items[0].last_error.lower() or "timed out" in items[0].last_error.lower()

    @pytest.mark.asyncio
    async def test_generic_error_also_enqueues_retry(self):
        _seed_active_exchange()
        app = MagicMock()
        app.state.algo_router_mode = "live"
        app.state.correlation_tracker = None

        fake = MagicMock()
        fake.get_product_id = AsyncMock(return_value=12345)
        fake.set_leverage = AsyncMock(return_value=None)
        fake.get_index_price = AsyncMock(return_value=100_000.0)
        fake.place_order = AsyncMock(side_effect=RuntimeError("rate_limited"))

        with patch(
            "app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
            return_value=fake,
        ):
            await _auto_place_algo_order(app, "BTC", _make_snap(), MODES["swing"])

        items = live_safety.list_retries(include_poison=True)
        assert len(items) == 1
        assert "rate_limited" in items[0].last_error


# ── H4: Preflight idempotency ──────────────────────────────────────────────


class TestH4Idempotency:
    @pytest.mark.asyncio
    async def test_replayed_idem_key_short_circuits(self, fake_adapter):
        """When the same logical signal fires within the 60s TTL window the
        algo path's preflight short-circuit returns early — never reaches the
        adapter, never duplicates the order."""
        _seed_active_exchange()
        app = MagicMock()
        app.state.algo_router_mode = "live"
        app.state.correlation_tracker = None

        with patch(
            "app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
            return_value=fake_adapter,
        ):
            await _auto_place_algo_order(app, "BTC", _make_snap(), MODES["swing"])
            # Same minute_bucket → same idem_key → preflight detects it
            _algo_last_ordered.clear()   # bypass cooldown to isolate idempotency
            await _auto_place_algo_order(app, "BTC", _make_snap(), MODES["swing"])

        assert fake_adapter.place_order.call_count == 1
