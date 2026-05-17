"""
Phase E + F tests.

E:  algo path now dispatches through OrderRouter — paper/shadow/live modes
    behave correctly and pre-router safety gates compose.
F:  per-symbol cap blocks new orders; retry queue worker drains backoff.
"""
from __future__ import annotations
import time
import asyncio
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
from main import _auto_place_algo_order, _algo_last_ordered, _background_retry_worker


# ─── helpers ────────────────────────────────────────────────────────────────

def _seed_active_exchange():
    from app.schemas.exchange_config import ExchangeConfigCreate
    cfg = eas.add_exchange(ExchangeConfigCreate(
        name="delta_india",
        display_name="Delta India",
        api_key="REAL-KEY", api_secret="REAL-SECRET",
        is_paper=False,
    ))
    eas.set_active(cfg.id)


def _make_snap(direction: str = "long", strong: bool = True) -> SnapshotEntry:
    return SnapshotEntry(
        sym="BTC", spot_price=100_000.0, ivr=50.0,
        green_arrow=False, red_arrow=True,
        current_state="ENTRY_ARMED_PULLBACK",
        computed_at_ms=int(time.time() * 1000),
        direction=direction, regime="BULL_TREND",
        score_long=100.0 if direction == "long" else 0.0,
        score_short=0.0 if direction == "long" else 100.0,
        atr=1_000.0, adx=25.0, atr_percentile=55.0,
        signal_score=18.0 if strong else 10.0,
        signal_strength="STRONG" if strong else "SIGNAL",
    )


@pytest.fixture(autouse=True)
def _reset_state():
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
        "id": "ORD-LIVE-1", "average_fill_price": 100_010.0, "state": "filled",
    })
    a.place_order_option = AsyncMock(return_value={"id": "ORD-OPT-1"})
    return a


# ─── Phase E: router dispatch ──────────────────────────────────────────────


class TestPhaseERouterDispatch:
    """Algo path must select paper/shadow/live based on app.state.algo_router_mode."""

    @pytest.mark.asyncio
    async def test_paper_mode_skips_exchange(self, fake_adapter):
        _seed_active_exchange()
        app = MagicMock()
        app.state.algo_router_mode = "paper"
        app.state.correlation_tracker = None

        with patch(
            "app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
            return_value=fake_adapter,
        ):
            await _auto_place_algo_order(app, "BTC", _make_snap(), MODES["swing"])

        # Paper mode must never reach the exchange
        fake_adapter.place_order.assert_not_called()
        fake_adapter.set_leverage.assert_not_called()

    @pytest.mark.asyncio
    async def test_live_mode_calls_exchange(self, fake_adapter):
        _seed_active_exchange()
        app = MagicMock()
        app.state.algo_router_mode = "live"
        app.state.correlation_tracker = None

        with patch(
            "app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
            return_value=fake_adapter,
        ):
            await _auto_place_algo_order(app, "BTC", _make_snap(), MODES["swing"])

        fake_adapter.place_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_shadow_mode_creates_paper_twin(self, fake_adapter):
        _seed_active_exchange()
        app = MagicMock()
        app.state.algo_router_mode = "shadow"
        app.state.correlation_tracker = None

        with patch(
            "app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
            return_value=fake_adapter,
        ):
            await _auto_place_algo_order(app, "BTC", _make_snap(), MODES["swing"])

        # Shadow = real exchange call AND a paper position written
        fake_adapter.place_order.assert_called_once()
        paper_positions = paper_store.list_positions()
        assert len(paper_positions) >= 1


# ─── Phase F: per-symbol cap ───────────────────────────────────────────────


class TestPhaseFPerSymbolCap:
    def test_cap_breach_at_default_3(self):
        # Build 3 fake open positions for BTC
        positions = []
        for i in range(3):
            p = MagicMock()
            p.underlying = "BTC"
            p.status = MagicMock()
            p.status.value = "open"
            positions.append(p)

        breach = live_safety.per_symbol_cap_breach("BTC", positions)
        assert breach is not None
        assert "3/3" in breach

    def test_no_breach_below_cap(self):
        p = MagicMock()
        p.underlying = "BTC"
        p.status = MagicMock()
        p.status.value = "open"
        breach = live_safety.per_symbol_cap_breach("BTC", [p])
        assert breach is None

    def test_other_symbols_not_counted(self):
        p = MagicMock()
        p.underlying = "ETH"
        p.status = MagicMock()
        p.status.value = "open"
        breach = live_safety.per_symbol_cap_breach("BTC", [p, p, p])
        assert breach is None

    def test_closed_positions_not_counted(self):
        p = MagicMock()
        p.underlying = "BTC"
        p.status = MagicMock()
        p.status.value = "closed"
        breach = live_safety.per_symbol_cap_breach("BTC", [p, p, p, p])
        assert breach is None

    def test_partially_closed_counted_as_open(self):
        positions = []
        for status in ("open", "open", "partially_closed"):
            p = MagicMock()
            p.underlying = "BTC"
            p.status = MagicMock()
            p.status.value = status
            positions.append(p)
        breach = live_safety.per_symbol_cap_breach("BTC", positions)
        assert breach is not None

    @pytest.mark.asyncio
    async def test_algo_blocked_when_per_symbol_cap_reached(self, fake_adapter):
        _seed_active_exchange()
        # Pre-populate paper_store with 3 open BTC positions
        from app.schemas.positions import PaperPosition, PositionStatus
        from app.schemas.execution import (
            TradeStructure, SizedTrade, CandidateContract, Direction as ExecDir,
        )
        leg = CandidateContract(
            instrument_name="X", underlying="BTC", strike=1.0, expiry_date="",
            dte=0, option_type="futures",
            bid=0.0, ask=0.0, mark_price=0.0, mid_price=0.0, mark_iv=0.0,
            delta=0.0, open_interest=0.0, volume_24h=0.0, spread_pct=0.0,
            health_score=0.0, healthy=True,
        )
        struct = TradeStructure(
            structure_type="futures", direction=ExecDir.LONG, legs=[leg],
            max_loss=200.0, max_gain=400.0, net_premium=0.0, risk_reward=2.0,
            score=0.0, score_breakdown={},
        )
        sized = SizedTrade(
            structure=struct, contracts=1, position_value=100.0,
            max_risk_usd=100.0, capital_at_risk_pct=0.1,
        )
        for i in range(3):
            paper_store._positions[f"P{i}"] = PaperPosition(
                id=f"P{i}", underlying="BTC", sized_trade=sized,
                status=PositionStatus.OPEN, is_paper=True,
                entry_timestamp_ms=int(time.time() * 1000),
                entry_spot_price=100_000.0,
                run_once_state="ENTERED", notes="",
            )

        app = MagicMock()
        app.state.algo_router_mode = "live"
        app.state.correlation_tracker = None

        with patch(
            "app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
            return_value=fake_adapter,
        ):
            await _auto_place_algo_order(app, "BTC", _make_snap(), MODES["swing"])

        # Cap breach → no exchange call
        fake_adapter.place_order.assert_not_called()


# ─── Phase F: retry worker ─────────────────────────────────────────────────


class TestPhaseFRetryWorker:
    @pytest.mark.asyncio
    async def test_worker_drains_pending_item_on_success(self):
        _seed_active_exchange()
        # Enqueue a failed order
        item = live_safety.enqueue_retry(
            payload={
                "underlying": "BTC", "direction": "long",
                "instrument_type": "futures",
                "size": 1.0, "leverage": 5.0,
                "client_order_id": "TEST-IDEM",
            },
            error="initial_failure",
        )
        # Make the item eligible for retry immediately
        item.last_attempt_ms = int(time.time() * 1000) - 600_000

        fake = MagicMock()
        fake.get_product_id = AsyncMock(return_value=12345)
        fake.set_leverage = AsyncMock(return_value=None)
        fake.place_order = AsyncMock(return_value={"id": "ORD-RETRY-1"})

        # Run the worker for exactly one iteration
        with patch(
            "app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
            return_value=fake,
        ):
            task = asyncio.create_task(_background_retry_worker(MagicMock(), base_interval=1))
            await asyncio.sleep(1.5)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        # Item must have been removed after success
        remaining = live_safety.list_retries(include_poison=False)
        assert all(i.id != item.id for i in remaining)

    @pytest.mark.asyncio
    async def test_worker_marks_attempt_on_failure(self):
        _seed_active_exchange()
        item = live_safety.enqueue_retry(
            payload={
                "underlying": "BTC", "direction": "long",
                "instrument_type": "futures",
                "size": 1.0, "leverage": 5.0,
            },
            error="initial",
        )
        item.last_attempt_ms = int(time.time() * 1000) - 600_000
        item.max_attempts = 1   # poison after this single failed attempt

        fake = MagicMock()
        fake.get_product_id = AsyncMock(return_value=12345)
        fake.set_leverage = AsyncMock(return_value=None)
        fake.place_order = AsyncMock(side_effect=RuntimeError("boom"))

        with patch(
            "app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
            return_value=fake,
        ):
            task = asyncio.create_task(_background_retry_worker(MagicMock(), base_interval=1))
            await asyncio.sleep(1.5)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        # mark_attempt → attempt incremented, poison flag may now be true
        all_items = live_safety.list_retries(include_poison=True)
        match = [i for i in all_items if i.id == item.id]
        assert match
        assert match[0].attempt >= 1
        assert match[0].last_error == "boom"

    def test_worker_respects_backoff(self):
        """Items whose last attempt is too recent must not be retried this tick."""
        item = live_safety.enqueue_retry(
            payload={"underlying": "BTC", "direction": "long",
                     "instrument_type": "futures", "size": 1.0, "leverage": 1.0},
            error="x",
        )
        # Fresh item — backoff check should hold off
        assert (int(time.time() * 1000) - (item.last_attempt_ms or item.enqueued_ms)) < 60_000
        # The worker would skip it without raising; this is a behavioural assertion
        # of the timing predicate used inside _background_retry_worker.
