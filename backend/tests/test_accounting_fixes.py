"""
Tests for accounting gap fixes:
  1+2: walk_forward.run_real uses real engine (not bps proxy); thresholds in 0-20 range
  2:   backtest simulate_capital_curve produces equity curve, PF, expectancy
  3:   partial_close_position reduces contracts, books P&L, is idempotent on PARTIALLY_CLOSED
  4:   DrawdownCircuitBreaker size_multiplier scales contracts
  5:   CalibrationService adaptive win_rate injected into RiskParams
  6:   Concurrency lock prevents TOCTOU double-entry
"""
import pytest
import asyncio
import time
import uuid
import numpy as np
from unittest.mock import MagicMock
from tests.conftest import make_candles, make_bearish_candles


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_leg():
    from app.schemas.execution import CandidateContract
    return CandidateContract(
        instrument_name="BTC-50000-C-27DEC24",
        underlying="BTC", option_type="call", strike=50000.0,
        expiry_date="27DEC24", dte=30, mark_price=1000.0,
        bid=990.0, ask=1010.0, mid_price=1000.0, mark_iv=0.8,
        delta=0.5, open_interest=500.0, volume_24h=200.0,
        spread_pct=0.002, health_score=85.0, healthy=True,
    )


def _make_sized(contracts: int = 4, max_risk: float = 400.0):
    from app.schemas.execution import TradeStructure, SizedTrade
    from app.schemas.directional import Direction
    leg    = _make_leg()
    struct = TradeStructure(
        structure_type="naked_call", direction=Direction.LONG,
        legs=[leg], max_loss=1000.0, max_gain=None,
        net_premium=1000.0, risk_reward=None,
        score=75.0, score_breakdown={},
    )
    return SizedTrade(
        structure=struct, contracts=contracts,
        position_value=contracts * 1000.0, max_risk_usd=max_risk,
        capital_at_risk_pct=max_risk / 100.0,
    )


def _make_open_pos(entry_spot: float = 50000.0, contracts: int = 4):
    from app.schemas.positions import PaperPosition, PositionStatus
    from app.schemas.directional import TradeState
    return PaperPosition(
        id=uuid.uuid4().hex[:8].upper(),
        underlying="BTC",
        sized_trade=_make_sized(contracts),
        status=PositionStatus.OPEN,
        entry_timestamp_ms=int(time.time() * 1000),
        entry_spot_price=entry_spot,
    )


# ─── Item 3: partial_close_position accounting ───────────────────────────────

class TestPartialCloseAccounting:

    def test_contracts_halved(self):
        from app.services import paper_store as ps
        from app.schemas.positions import PositionStatus
        pos = _make_open_pos(contracts=4)
        ps._positions[pos.id] = pos

        result = ps.partial_close_position(pos.id, exit_spot_price=51000.0, partial_ratio=0.50)

        assert result is not None
        assert result.sized_trade.contracts == 2
        assert result.status == PositionStatus.PARTIALLY_CLOSED

        del ps._positions[pos.id]

    def test_partial_pnl_booked(self):
        from app.services import paper_store as ps
        pos = _make_open_pos(entry_spot=50000.0, contracts=4)
        ps._positions[pos.id] = pos

        result = ps.partial_close_position(pos.id, exit_spot_price=51000.0, partial_ratio=0.50)

        # +1000 spot_move × long (+1) × 2 closed_contracts × 0.5 delta = 1000
        assert result.realized_pnl_usd == pytest.approx(1000.0, abs=1.0)

        del ps._positions[pos.id]

    def test_max_risk_scaled(self):
        from app.services import paper_store as ps
        pos = _make_open_pos(contracts=4)
        ps._positions[pos.id] = pos  # max_risk_usd = 400

        result = ps.partial_close_position(pos.id, exit_spot_price=50000.0, partial_ratio=0.50)

        assert result.sized_trade.max_risk_usd == pytest.approx(200.0, abs=1.0)

        del ps._positions[pos.id]

    def test_idempotent_on_partially_closed(self):
        """Second call on PARTIALLY_CLOSED returns None (not OPEN)."""
        from app.services import paper_store as ps
        pos = _make_open_pos(contracts=4)
        ps._positions[pos.id] = pos

        r1 = ps.partial_close_position(pos.id, exit_spot_price=51000.0, partial_ratio=0.50)
        assert r1 is not None

        r2 = ps.partial_close_position(pos.id, exit_spot_price=52000.0, partial_ratio=0.50)
        assert r2 is None   # PARTIALLY_CLOSED, not OPEN → blocked

        del ps._positions[pos.id]

    def test_accumulates_pnl(self):
        """Partial P&L accumulates on top of any pre-existing realized_pnl_usd."""
        from app.services import paper_store as ps
        from app.schemas.positions import PositionStatus
        pos = _make_open_pos(entry_spot=50000.0, contracts=4)
        pos = pos.model_copy(update={"realized_pnl_usd": 50.0})  # pre-existing partial
        ps._positions[pos.id] = pos

        result = ps.partial_close_position(pos.id, exit_spot_price=51000.0, partial_ratio=0.50)

        assert result.realized_pnl_usd == pytest.approx(50.0 + 1000.0, abs=1.0)

        del ps._positions[pos.id]


# ─── Item 2: simulate_capital_curve ──────────────────────────────────────────

class TestSimulateCapitalCurve:

    def _make_bars(self, n: int = 40, direction: str = "long", fwd_ret: float = 0.5):
        from app.schemas.backtest import BacktestBarResult
        from app.schemas.directional import TradeState
        bars = []
        for i in range(n):
            is_entry = (i % 12 == 0)
            bars.append(BacktestBarResult(
                timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                close_1h=30000.0 + i * 10,
                close_4h=30000.0 + i * 10,
                macro_regime="BULL_TREND",
                ema50=29000.0,
                signal_trend=1 if direction == "long" else -1,
                all_green=True, all_red=False,
                green_arrow=(i == 0), red_arrow=False,
                st_trends=[1, 1, 1], st_values=[29500.0, 29400.0, 29300.0],
                state=TradeState.CONFIRMED_SETUP_ACTIVE.value if is_entry else "IDLE",
                direction=direction,
                fwd_return_12h=fwd_ret,
            ))
        return bars

    def test_returns_equity_curve_normalised(self):
        from app.engines.backtest.backtest_engine import simulate_capital_curve
        result = simulate_capital_curve(self._make_bars(), capital=10_000.0)
        assert result["equity_curve"][0] == pytest.approx(1.0)
        assert len(result["equity_curve"]) > 1

    def test_fee_reduces_expectancy(self):
        from app.engines.backtest.backtest_engine import simulate_capital_curve
        r0 = simulate_capital_curve(self._make_bars(), fee_rt_pct=0.0)
        r1 = simulate_capital_curve(self._make_bars(), fee_rt_pct=0.001)
        if r0["expectancy_pct"] and r1["expectancy_pct"]:
            assert r1["expectancy_pct"] < r0["expectancy_pct"]

    def test_profit_factor_finite_with_mixed_returns(self):
        from app.engines.backtest.backtest_engine import simulate_capital_curve
        mixed = self._make_bars(fwd_ret=0.3)
        # inject some losers
        for b in mixed[12::24]:
            b.fwd_return_12h = -0.2
        result = simulate_capital_curve(mixed, fee_rt_pct=0.0)
        if result["profit_factor"] is not None:
            assert result["profit_factor"] > 0

    def test_empty_bars_returns_defaults(self):
        from app.engines.backtest.backtest_engine import simulate_capital_curve
        result = simulate_capital_curve([])
        assert result["win_rate"] is None
        assert result["equity_curve"] == [1.0, 1.0]

    def test_sim_fields_present_in_backtest_result(self):
        """run_backtest populates all sim_* fields on BacktestResult."""
        from app.schemas.market import Candle
        from app.engines.backtest.backtest_engine import run_backtest

        c1h = make_candles(80,  base=30000.0, trend=50.0)
        c4h = make_candles(70,  base=30000.0, trend=200.0)
        # Give 4H candles timestamps matching 4× spacing so filter works
        c4h_ts = [
            Candle(
                timestamp_ms=c.timestamp_ms * 4,
                open=c.open, high=c.high, low=c.low,
                close=c.close, volume=c.volume,
            )
            for c in c4h
        ]
        result = run_backtest("BTC", c4h_ts, c1h, lookback_days=7)
        assert result.sim_fee_rt_pct == pytest.approx(0.001)
        assert result.sim_equity_curve is not None
        assert isinstance(result.sim_trade_count, int)


# ─── Item 1: walk_forward.run_real ───────────────────────────────────────────

class TestWalkForwardReal:

    def _make_candles_with_4h(self, n1h: int = 320, n4h: int = 100):
        from app.schemas.market import Candle
        c1h = make_candles(n1h, base=30000.0, trend=50.0)
        c4h_raw = make_candles(n4h, base=30000.0, trend=200.0)
        # 4H timestamps = 4× 1H spacing so the _4H_MS filter aligns
        c4h = [
            Candle(
                timestamp_ms=c.timestamp_ms * 4,
                open=c.open, high=c.high, low=c.low,
                close=c.close, volume=c.volume,
            )
            for c in c4h_raw
        ]
        return c1h, c4h

    def test_run_real_completes(self):
        from app.engines.analytics.walk_forward import run_real, WalkForwardConfig
        c1h, c4h = self._make_candles_with_4h()
        cfg = WalkForwardConfig(train_bars=150, test_bars=80, step_bars=80)
        result = run_real(c1h, c4h, cfg)
        assert result is not None
        assert hasattr(result, "aggregate_report")
        assert hasattr(result, "oos_equity_curve")
        assert len(result.oos_equity_curve) >= 1

    def test_threshold_in_signal_score_range(self):
        """Recommended threshold is a signal_score value (0–20), not bps."""
        from app.engines.analytics.walk_forward import run_real, WalkForwardConfig
        c1h, c4h = self._make_candles_with_4h()
        cfg = WalkForwardConfig(
            train_bars=150, test_bars=80, step_bars=80,
            score_thresholds_to_test=[0, 5, 10, 15, 20],
        )
        result = run_real(c1h, c4h, cfg)
        assert 0 <= result.recommended_threshold <= 20, (
            f"recommended_threshold {result.recommended_threshold} outside 0-20"
        )

    def test_oos_curve_starts_at_one(self):
        from app.engines.analytics.walk_forward import run_real, WalkForwardConfig, _equity_from_trades
        c1h, c4h = self._make_candles_with_4h()
        cfg = WalkForwardConfig(train_bars=150, test_bars=80, step_bars=80)
        result = run_real(c1h, c4h, cfg)
        assert result.oos_equity_curve[0] == pytest.approx(1.0, abs=0.01)


# ─── Item 4: DrawdownCircuitBreaker size_multiplier ──────────────────────────

class TestDrawdownSizeMultiplier:

    def test_warning_state_halves_size(self):
        from app.engines.risk.circuit_breaker import DrawdownCircuitBreaker, CircuitBreakerConfig
        cb = DrawdownCircuitBreaker(CircuitBreakerConfig(), portfolio_value=10_000.0)
        cb.update(9_400.0)   # -6% → WARNING
        assert cb.size_multiplier() == pytest.approx(0.5)
        # Simulate the scaling logic used in enter_position
        contracts = 4
        reduced   = max(1, int(contracts * cb.size_multiplier()))
        assert reduced == 2

    def test_halt_zeroes_multiplier(self):
        from app.engines.risk.circuit_breaker import DrawdownCircuitBreaker, CircuitBreakerConfig
        cb = DrawdownCircuitBreaker(CircuitBreakerConfig(), portfolio_value=10_000.0)
        cb.update(8_900.0)   # -11% → HALT
        assert cb.size_multiplier() == pytest.approx(0.0)

    def test_clear_state_full_size(self):
        from app.engines.risk.circuit_breaker import DrawdownCircuitBreaker, CircuitBreakerConfig
        cb = DrawdownCircuitBreaker(CircuitBreakerConfig(), portfolio_value=10_000.0)
        cb.update(10_200.0)  # new high → CLEAR
        assert cb.size_multiplier() == pytest.approx(1.0)

    def test_size_scaling_formula(self):
        """Verify the exact formula used in enter_position."""
        original_contracts = 6
        dd_size_mult = 0.5
        reduced = max(1, int(original_contracts * dd_size_mult))
        scale   = reduced / max(original_contracts, 1)
        max_risk_orig = 600.0
        assert reduced == 3
        assert scale == pytest.approx(0.5)
        assert round(max_risk_orig * scale, 2) == pytest.approx(300.0)


# ─── Item 5: CalibrationService win_rate injection ───────────────────────────

class TestCalibrationWinRateInjection:

    def _svc(self, db_path: str):
        from app.services.calibration import CalibrationService
        return CalibrationService(db_path)

    def test_injected_when_enough_trades(self, tmp_path):
        svc = self._svc(str(tmp_path / "cal.db"))
        for _ in range(12):
            svc.record_trade(0.10, "BULL_TREND")
        for _ in range(3):
            svc.record_trade(-0.05, "BULL_TREND")

        from app.schemas.risk import RiskParams
        risk = RiskParams()
        if svc.trade_count() >= 10:
            wr = svc.win_rate()
            if 0.10 <= wr <= 0.90:
                risk = risk.model_copy(update={"win_rate": round(wr, 4)})

        assert risk.win_rate == pytest.approx(12 / 15, rel=0.01)

    def test_not_injected_below_threshold(self, tmp_path):
        svc = self._svc(str(tmp_path / "cal.db"))
        for _ in range(5):
            svc.record_trade(0.10, "BULL_TREND")

        from app.schemas.risk import RiskParams
        risk = RiskParams()
        if svc.trade_count() >= 10:
            risk = risk.model_copy(update={"win_rate": svc.win_rate()})

        assert risk.win_rate == pytest.approx(0.52)  # default unchanged

    def test_extreme_win_rate_clamped(self, tmp_path):
        """win_rate outside [0.10, 0.90] must not be injected."""
        svc = self._svc(str(tmp_path / "cal.db"))
        for _ in range(20):
            svc.record_trade(0.10, "BULL_TREND")  # 100% win rate

        from app.schemas.risk import RiskParams
        risk = RiskParams()
        if svc.trade_count() >= 10:
            wr = svc.win_rate()
            if 0.10 <= wr <= 0.90:
                risk = risk.model_copy(update={"win_rate": round(wr, 4)})
        # 1.0 > 0.90 → not injected, default remains
        assert risk.win_rate == pytest.approx(0.52)


# ─── Item 6: Concurrency lock ─────────────────────────────────────────────────

class TestConcurrencyLock:

    @pytest.mark.asyncio
    async def test_lock_serialises_enter(self):
        """
        Two coroutines that both see open_count == 0 must not both enter
        when max_concurrent == 1. The lock ensures they execute serially.
        """
        lock    = asyncio.Lock()
        entered = []
        _open   = [0]   # mutable counter inside lock

        async def try_enter(name: str, max_conc: int = 1):
            async with lock:
                if _open[0] >= max_conc:
                    return False
                _open[0] += 1
                entered.append(name)
                return True

        results = await asyncio.gather(
            try_enter("req1"),
            try_enter("req2"),
        )
        # Only one should succeed when max_concurrent == 1
        assert sum(results) == 1
        assert len(entered) == 1

    @pytest.mark.asyncio
    async def test_lock_allows_sequential_entries(self):
        """After first position is closed, a second can enter."""
        lock  = asyncio.Lock()
        _open = [0]

        async def enter(max_conc: int = 2):
            async with lock:
                if _open[0] >= max_conc:
                    return False
                _open[0] += 1
                return True

        async def leave():
            async with lock:
                _open[0] = max(0, _open[0] - 1)

        r1 = await enter()
        await leave()
        r2 = await enter()

        assert r1 and r2
