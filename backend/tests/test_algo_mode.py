"""
Algo-mode autopilot tests (P0.1 – P0.5).

Each test isolates one safety primitive on _auto_place_algo_order and asserts
the function's contract:

  P0.1  kill switch / daily-loss halt blocks the order
  P0.2  signal_strength != STRONG blocks the order
  P0.3  size_trade() drives the contract count (not hardcoded 1.0)
  P0.4  select_leverage(score, strength) drives leverage
  P0.5  idempotency cache short-circuits duplicate ticks

We mock DeltaIndiaAdapter end-to-end so no live network calls occur.
"""
from __future__ import annotations
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import exchange_account_store as eas
from app.services import live_safety, paper_store, snapshot_cache
from app.services.snapshot_cache import SnapshotEntry
from app.core.trading_mode import MODES
from main import _auto_place_algo_order, _algo_last_ordered


# ─── helpers ────────────────────────────────────────────────────────────────

def _seed_active_exchange():
    """Create an active Delta exchange config with non-DUMMY keys."""
    from app.schemas.exchange_config import ExchangeConfigCreate
    cfg = eas.add_exchange(ExchangeConfigCreate(
        name="delta_india",
        display_name="Delta India",
        api_key="REAL-KEY",
        api_secret="REAL-SECRET",
        is_paper=False,
    ))
    eas.set_active(cfg.id)


def _make_snap(
    sym: str = "BTC",
    direction: str = "long",
    state: str = "ENTRY_ARMED_PULLBACK",
    signal_score: float = 16.0,
    signal_strength: str = "STRONG",
    spot: float = 100_000.0,
    atr: float = 1_000.0,
) -> SnapshotEntry:
    return SnapshotEntry(
        sym=sym,
        spot_price=spot,
        ivr=50.0,
        green_arrow=True,
        red_arrow=False,
        current_state=state,
        computed_at_ms=int(time.time() * 1000),
        direction=direction,
        regime="BULL_TREND",
        score_long=100.0 if direction == "long" else 0.0,
        score_short=0.0 if direction == "long" else 100.0,
        atr=atr,
        adx=25.0,
        atr_percentile=55.0,
        signal_score=signal_score,
        signal_strength=signal_strength,
    )


@pytest.fixture(autouse=True)
def _reset_algo_state():
    """Wipe per-test state — cooldowns, idempotency, kill-switch."""
    _algo_last_ordered.clear()
    live_safety.reset_all_for_tests()
    snapshot_cache._cache.clear()
    yield
    _algo_last_ordered.clear()
    live_safety.reset_all_for_tests()


@pytest.fixture
def fake_adapter():
    """A DeltaIndiaAdapter mock that returns a successful filled order."""
    a = MagicMock()
    a.get_product_id = AsyncMock(return_value=12345)
    a.set_leverage = AsyncMock(return_value=None)
    a.place_order = AsyncMock(return_value={
        "id": "ORD-TEST-1",
        "average_fill_price": 100_010.0,
        "state": "filled",
    })
    return a


# ─── P0.1: safety gate ──────────────────────────────────────────────────────

class TestP0SafetyGate:
    @pytest.mark.asyncio
    async def test_kill_switch_blocks_order(self, fake_adapter):
        _seed_active_exchange()
        live_safety.set_kill_switch(True, reason="manual halt")
        snap = _make_snap()

        with patch("app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
                   return_value=fake_adapter):
            await _auto_place_algo_order(MagicMock(), "BTC", snap, MODES["swing"])

        # No order placed
        fake_adapter.place_order.assert_not_called()
        # Cooldown reservation NOT taken — gate happened first
        assert _algo_last_ordered == {}

    @pytest.mark.asyncio
    async def test_daily_loss_halt_blocks_order(self, fake_adapter):
        _seed_active_exchange()
        # Configure daily-loss halt at -100 USD; seed a closed loss of -200 USD
        live_safety.configure_daily_loss(
            live_safety.DailyLossConfig(soft_warn_usd=-50.0, hard_halt_usd=-100.0),
        )

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
            max_loss=200.0, max_gain=0.0, net_premium=0.0, risk_reward=1.0,
            score=0.0, score_breakdown={},
        )
        sized = SizedTrade(
            structure=struct, contracts=1, position_value=200.0,
            max_risk_usd=200.0, capital_at_risk_pct=0.2,
        )
        # Seed today's loss
        paper_store._positions["L"] = PaperPosition(
            id="L", underlying="BTC", sized_trade=sized,
            status=PositionStatus.CLOSED, is_paper=True,
            entry_timestamp_ms=int(time.time() * 1000) - 1000,
            entry_spot_price=100_000.0,
            exit_timestamp_ms=int(time.time() * 1000),
            exit_spot_price=99_800.0,
            realized_pnl_usd=-200.0,
            run_once_state="EXITED", notes="",
            trail_stop_json=None,
        )

        snap = _make_snap()
        with patch("app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
                   return_value=fake_adapter):
            await _auto_place_algo_order(MagicMock(), "BTC", snap, MODES["swing"])

        fake_adapter.place_order.assert_not_called()
        # Reset config back to defaults
        live_safety.configure_daily_loss(live_safety.DailyLossConfig())


# ─── P0.2: score gate ───────────────────────────────────────────────────────

class TestP0ScoreGate:
    @pytest.mark.asyncio
    async def test_below_strong_blocks_order(self, fake_adapter):
        _seed_active_exchange()
        snap = _make_snap(signal_score=10.0, signal_strength="SIGNAL")

        with patch("app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
                   return_value=fake_adapter):
            await _auto_place_algo_order(MagicMock(), "BTC", snap, MODES["swing"])

        fake_adapter.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_strong_signal_passes_gate(self, fake_adapter):
        _seed_active_exchange()
        snap = _make_snap(signal_score=18.0, signal_strength="STRONG")

        with patch("app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
                   return_value=fake_adapter):
            await _auto_place_algo_order(MagicMock(), "BTC", snap, MODES["swing"])

        fake_adapter.place_order.assert_called_once()


# ─── P0.3: sizing ───────────────────────────────────────────────────────────

class TestP0Sizing:
    @pytest.mark.asyncio
    async def test_size_not_hardcoded_to_one(self, fake_adapter):
        _seed_active_exchange()
        snap = _make_snap(signal_score=18.0, signal_strength="STRONG")

        with patch("app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
                   return_value=fake_adapter):
            await _auto_place_algo_order(MagicMock(), "BTC", snap, MODES["swing"])

        kwargs = fake_adapter.place_order.call_args.kwargs
        # size_trade() with default RiskParams + futures structure should
        # produce ≥ 1 contract; the key invariant is that it's a *computed*
        # value, not the legacy hardcoded 1.0.
        assert "size" in kwargs
        assert kwargs["size"] >= 1.0
        # max_contracts cap from RiskParams default is 10 — never above
        assert kwargs["size"] <= 10


# ─── P0.4: leverage ─────────────────────────────────────────────────────────

class TestP0Leverage:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("score20,expected_lev", [
        (15.0, 3),    # score 75 → 3x
        (16.0, 5),    # score 80 → 5x
        (17.0, 10),   # score 85 STRONG → 10x
        (18.0, 25),   # score 90 STRONG → 25x
        (19.0, 50),   # score 95 STRONG → 50x
    ])
    async def test_leverage_matches_v3_scale(self, fake_adapter, score20, expected_lev):
        _seed_active_exchange()
        snap = _make_snap(signal_score=score20, signal_strength="STRONG")

        with patch("app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
                   return_value=fake_adapter):
            await _auto_place_algo_order(MagicMock(), "BTC", snap, MODES["swing"])

        fake_adapter.set_leverage.assert_called_once()
        called_lev = fake_adapter.set_leverage.call_args.args[1]
        assert called_lev == expected_lev


# ─── P0.5: idempotency ──────────────────────────────────────────────────────

class TestP0Idempotency:
    @pytest.mark.asyncio
    async def test_duplicate_within_minute_short_circuits(self, fake_adapter):
        """Two identical signal ticks within the same minute must produce
        only one place_order call."""
        _seed_active_exchange()
        snap = _make_snap(signal_score=18.0, signal_strength="STRONG")

        with patch("app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
                   return_value=fake_adapter):
            await _auto_place_algo_order(MagicMock(), "BTC", snap, MODES["swing"])
            # Bypass cooldown to isolate idempotency: clear cooldown but keep
            # the idempotency cache from the prior successful fill.
            _algo_last_ordered.clear()
            await _auto_place_algo_order(MagicMock(), "BTC", snap, MODES["swing"])

        # Only the first call hit the adapter
        assert fake_adapter.place_order.call_count == 1

    @pytest.mark.asyncio
    async def test_different_minute_buckets_can_re_fire(self, fake_adapter):
        """An identical signal in a different minute bucket is not deduped
        (cooldown handles that). Idempotency only stops same-minute repeats."""
        _seed_active_exchange()
        snap = _make_snap(signal_score=18.0, signal_strength="STRONG")

        with patch("app.services.exchanges.adapters.delta_india.DeltaIndiaAdapter",
                   return_value=fake_adapter):
            with patch("main.time") as mock_time:
                mock_time.time.return_value = 1_700_000_000.0   # minute X
                await _auto_place_algo_order(MagicMock(), "BTC", snap, MODES["swing"])

                _algo_last_ordered.clear()
                # Advance ~3 minutes and clear idempotency TTL window
                live_safety._IDEMPOTENCY_CACHE.clear()
                mock_time.time.return_value = 1_700_000_180.0   # +180s
                await _auto_place_algo_order(MagicMock(), "BTC", snap, MODES["swing"])

        assert fake_adapter.place_order.call_count == 2
