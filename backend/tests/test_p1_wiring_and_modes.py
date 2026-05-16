"""
End-to-end tests for the P1 wiring + mode-aware orchestrator:

 1. Cooldown.record_exit fires when a position is closed (paper_store path).
 2. orchestrator.run_once consults the cooldown and returns FILTERED while
    the window is active; resumes after expiry.
 3. orchestrator.run_once requests candles at the resolutions defined by
    each TradingModeConfig (proves the "scalp leak" fix: scalping uses
    the 5m signal_tf, not the swing 1H).
"""
import asyncio
import time
import pytest

from unittest.mock import AsyncMock, MagicMock

from app.engines.risk import cooldown
from app.engines.risk.cooldown import CooldownConfig
from app.engines.directional import orchestrator as orch
from app.schemas.directional import TradeState, Direction
from app.schemas.execution import RunOnceResponse, TradeStructure
from app.schemas.instruments import InstrumentMeta


_INST = InstrumentMeta(
    underlying="BTC",
    tick_size=0.5,
    strike_step=1000.0,
    exchange="deribit",
    exchange_currency="BTC",
    perp_symbol="BTC-PERPETUAL",
    index_name="btc_usd",
    dvol_symbol="BTC-DVOL",
)


# ─── 1. paper_store.close_position records exit in cooldown ─────────────────

class TestCloseRecordsCooldown:

    def setup_method(self) -> None:
        cooldown.clear()

    def test_close_paper_position_triggers_record_exit(self) -> None:
        """Verifies the wiring inside paper_store.close_position."""
        from app.services import paper_store
        from app.schemas.execution import (
            CandidateContract, TradeStructure, SizedTrade,
        )

        # Build a minimal trade structure (single naked-call leg)
        leg = CandidateContract(
            instrument_name="BTC-CALL-100000",
            underlying="BTC",
            strike=100_000.0,
            expiry_date="2026-12-31",
            dte=14,
            option_type="call",
            bid=98.0, ask=102.0, mark_price=100.0, mid_price=100.0,
            mark_iv=0.65, delta=0.45,
            open_interest=500.0, volume_24h=200.0,
            spread_pct=0.04, health_score=85.0, healthy=True,
        )
        struct = TradeStructure(
            structure_type="naked_call",
            direction=Direction.LONG,
            legs=[leg],
            max_loss=102.0, max_gain=None,
            net_premium=102.0, risk_reward=None,
            score=80.0, score_breakdown={},
        )
        sized = SizedTrade(
            structure=struct, contracts=1,
            position_value=102.0, max_risk_usd=102.0,
            capital_at_risk_pct=0.001,
        )

        pos = paper_store.add_position(
            underlying="BTC",
            sized_trade=sized,
            entry_spot_price=100_000.0,
            trail_mode_name="swing",
        )
        assert pos.mode == "swing"

        # Sanity: not blocked before close
        assert cooldown.is_blocked(
            "BTC", "swing", "long", now_ms=int(time.time() * 1000)
        ) is False

        # Close → should fire record_exit
        closed = paper_store.close_position(pos.id, exit_spot_price=101_000.0)
        assert closed is not None
        assert closed.status.value == "closed"

        # After close: same key blocked, different mode/direction not
        now = int(time.time() * 1000)
        assert cooldown.is_blocked("BTC", "swing", "long",   now) is True
        assert cooldown.is_blocked("BTC", "swing", "short",  now) is False
        assert cooldown.is_blocked("BTC", "scalping", "long", now) is False

        # Cleanup so other tests are isolated
        paper_store._positions.pop(pos.id, None)


# ─── 2. orchestrator.run_once respects cooldown ─────────────────────────────

class TestOrchestratorCooldownGate:

    def setup_method(self) -> None:
        cooldown.clear()

    def _bullish_adapter(self) -> MagicMock:
        """Minimal mocked adapter feeding bullish-trending OHLCs."""
        from tests.conftest import make_candles
        adapter = MagicMock()
        adapter.get_candles = AsyncMock(return_value=make_candles(200, base=30000.0, trend=80.0))
        adapter.get_index_price = AsyncMock(return_value=32000.0)
        adapter.get_dvol = AsyncMock(return_value=None)
        adapter.get_dvol_history = AsyncMock(return_value=[])
        adapter.get_option_chain = AsyncMock(return_value=[])
        return adapter

    def test_run_once_filtered_while_cooldown_active(self) -> None:
        """A recent same-(underlying, mode, direction) exit must block re-entry."""
        adapter = self._bullish_adapter()
        # Pre-record a long exit one minute ago in swing mode
        cooldown.record_exit(
            "BTC", "swing", "long",
            exit_ts_ms=int(time.time() * 1000) - 60_000,
        )

        result = asyncio.run(orch.run_once(_INST, adapter, mode="swing"))

        assert result.recommendation == "no_trade"
        # Should be filtered specifically because of cooldown — message contains "Cooldown"
        # iff the underlying signal would otherwise have produced a non-IDLE direction.
        # With bullish 200-bar trend the signal direction is long, so cooldown wins.
        if result.direction == Direction.LONG:
            assert "Cooldown" in result.reason
            assert result.state == TradeState.FILTERED

    def test_run_once_unblocked_after_window_expiry(self) -> None:
        """After the cooldown window passes, orchestrator runs normally again."""
        adapter = self._bullish_adapter()
        # Exit was 5 hours ago (swing window is 4h)
        five_hours_ms = 5 * 60 * 60 * 1000
        cooldown.record_exit(
            "BTC", "swing", "long",
            exit_ts_ms=int(time.time() * 1000) - five_hours_ms,
        )

        result = asyncio.run(orch.run_once(_INST, adapter, mode="swing"))
        # Cooldown is no longer the gate — reason must NOT contain "Cooldown"
        assert "Cooldown" not in result.reason


# ─── 3. orchestrator.run_once routes candle resolutions per mode ────────────

class TestOrchestratorModeRouting:

    def setup_method(self) -> None:
        cooldown.clear()

    def _adapter_recording_resolutions(self):
        """Return adapter + a list that captures every resolution requested."""
        from tests.conftest import make_candles
        captured: list[str] = []

        async def _candles(instrument, resolution, limit):
            captured.append(resolution)
            return make_candles(200, base=30000.0, trend=80.0)

        adapter = MagicMock()
        adapter.get_candles = AsyncMock(side_effect=_candles)
        adapter.get_index_price = AsyncMock(return_value=32000.0)
        adapter.get_dvol = AsyncMock(return_value=None)
        adapter.get_dvol_history = AsyncMock(return_value=[])
        adapter.get_option_chain = AsyncMock(return_value=[])
        return adapter, captured

    def test_swing_mode_uses_4H_1H_15m(self) -> None:
        adapter, captured = self._adapter_recording_resolutions()
        asyncio.run(orch.run_once(_INST, adapter, mode="swing"))
        assert captured[0] == "4H"
        assert captured[1] == "1H"
        assert captured[2] == "15m"

    def test_scalping_mode_uses_15m_5m_1m(self) -> None:
        adapter, captured = self._adapter_recording_resolutions()
        asyncio.run(orch.run_once(_INST, adapter, mode="scalping"))
        assert captured[0] == "15m"
        assert captured[1] == "5m"
        assert captured[2] == "1m"

    def test_intraday_mode_uses_1H_15m_5m(self) -> None:
        adapter, captured = self._adapter_recording_resolutions()
        asyncio.run(orch.run_once(_INST, adapter, mode="intraday"))
        assert captured[0] == "1H"
        assert captured[1] == "15m"
        assert captured[2] == "5m"

    def test_positional_mode_uses_D_4H_1H(self) -> None:
        adapter, captured = self._adapter_recording_resolutions()
        asyncio.run(orch.run_once(_INST, adapter, mode="positional"))
        assert captured[0] == "D"
        assert captured[1] == "4H"
        assert captured[2] == "1H"

    def test_unknown_mode_falls_back_to_swing(self) -> None:
        adapter, captured = self._adapter_recording_resolutions()
        asyncio.run(orch.run_once(_INST, adapter, mode="hyperdrive"))
        # Unknown mode → MODES.get falls back to DEFAULT_MODE ("swing")
        assert captured[0] == "4H"
        assert captured[1] == "1H"

    def test_default_mode_is_swing(self) -> None:
        """No mode kwarg → must use swing timeframes (back-compat)."""
        adapter, captured = self._adapter_recording_resolutions()
        asyncio.run(orch.run_once(_INST, adapter))
        assert captured[0] == "4H"
        assert captured[1] == "1H"
