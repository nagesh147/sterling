"""Tests for the honest scalping replay engine (engines.sterling_engine.backtest).

Covers the building blocks deterministically (exit simulation, sample-size
tiers, PF/expectancy) and the full orchestration via a stubbed strategy
evaluator so we can assert real fills, cost folding, and the validation
signals (sample quality / regime coverage / OOS split) without depending on
synthetic data happening to form chart patterns.
"""
from types import SimpleNamespace

import pytest

from app.schemas.market import Candle
from app.engines.sterling_engine.config import ScalpingProfile
from app.engines.sterling_engine import backtest as bt


def _mk(n: int, interval_ms: int, *, start: int = 1_700_000_000_000,
        base: float = 30_000.0, step: float = 10.0):
    """Monotonically rising candles at a fixed interval (deterministic)."""
    out = []
    for i in range(n):
        c = base + i * step
        out.append(Candle(
            timestamp_ms=start + i * interval_ms,
            open=c - step / 2, high=c + step, low=c - step, close=c,
            volume=100.0,
        ))
    return out


# ── exit simulation ─────────────────────────────────────────────────────────


def test_exit_fixed_long_take_profit():
    c = _mk(20, 60_000, base=100.0, step=1.0)  # rising → TP first
    px, k, reason = bt._exit_fixed(c, 0, True, entry=100.0, sl=95.0, tp=105.0, maxh=20)
    assert reason == "take_profit" and px == 105.0 and k > 0


def test_exit_fixed_long_stop_loss():
    # Falling series → low breaches the stop before any TP.
    c = _mk(20, 60_000, base=100.0, step=-1.0)
    px, k, reason = bt._exit_fixed(c, 0, True, entry=100.0, sl=97.0, tp=110.0, maxh=20)
    assert reason == "stop_loss" and px == 97.0


def test_exit_fixed_time_stop():
    c = _mk(10, 60_000, base=100.0, step=0.01)  # barely moves → neither SL nor TP
    px, k, reason = bt._exit_fixed(c, 0, True, entry=100.0, sl=50.0, tp=200.0, maxh=5)
    assert reason == "time" and k == 5


# ── sample-size tiers ────────────────────────────────────────────────────────


@pytest.mark.parametrize("n,label,adequate", [
    (0, "no_trades", False),
    (12, "unreliable", False),
    (50, "thin", False),
    (150, "adequate", True),
    (800, "robust", True),
])
def test_classify_sample_size(n, label, adequate):
    q = bt.classify_sample_size(n)
    assert q["label"] == label
    assert q["adequate"] is adequate
    assert q["min_reliable"] == 100


# ── PF / expectancy ──────────────────────────────────────────────────────────


def test_pf_exp_basic():
    pf, exp, n = bt._pf_exp([2.0, -1.0, 1.0])  # wins 3, losses 1 -> pf 3
    assert pf == 3.0 and n == 3 and exp == pytest.approx(2.0 / 3, abs=1e-3)


def test_pf_exp_no_losers_is_none():
    pf, _, _ = bt._pf_exp([1.0, 2.0])
    assert pf is None  # undefined, not a fake "perfect" number


# ── full orchestration with a stubbed evaluator ──────────────────────────────


def _stub_long(underlying, c_macro, c_exec, levels, cfg):
    """Always arm a long at the current close with a 1% stop / 2% target."""
    px = float(c_exec[-1].close)
    return SimpleNamespace(
        entry_ok=True, direction="long",
        entry=px, stop_loss=px * 0.99, take_profit=px * 1.02,
    )


def test_run_backtest_applies_costs_and_reports_validation(monkeypatch):
    # Shrink the warmup windows so a small synthetic series produces trades.
    monkeypatch.setattr(bt, "W_EXEC", 20)
    monkeypatch.setattr(bt, "W_MACRO", 10)
    monkeypatch.setitem(bt.EVALUATORS, "price_action", _stub_long)

    exec_c = _mk(300, 30 * 60_000, base=100.0, step=0.5)   # rising 30m series
    macro_c = _mk(120, 4 * 60 * 60_000, base=100.0, step=2.0)  # 4h series
    cfg = ScalpingProfile(
        macro_timeframe="4h", execution_timeframe="30m",
        macro_trend_ema_slow=20, macro_trend_filter=False, risk_percent=1.0,
    )

    out = bt.run_scalping_backtest(
        "BTC", macro_c, exec_c, cfg, strategies=["price_action"],
    )

    assert out.total_trades > 0
    # Costs are always positive, so net R must be below gross R for every trade.
    for t in out.trades:
        assert t.cost_r > 0
        assert t.pnl_r < t.gross_pnl_r
    # Rising series + 2% TP / 1% SL → the strategy should be net profitable.
    assert out.win_rate > 0.5
    assert out.avg_cost_r > 0
    # Equity curve has one point per trade plus the starting point.
    assert len(out.equity_curve) == out.total_trades + 1
    # Validation signals are populated.
    assert out.sample_quality["label"] in {"robust", "adequate", "thin", "unreliable"}
    assert "by_regime" in out.regime_coverage
    assert "out-of-sample" in out.oos["note"].lower()
    assert out.oos["n_is"] + out.oos["n_oos"] == out.total_trades


def test_run_backtest_insufficient_data_is_empty():
    out = bt.run_scalping_backtest(
        "BTC", _mk(5, 4 * 60 * 60_000), _mk(5, 30 * 60_000),
        ScalpingProfile(), strategies=["price_action"],
    )
    assert out.total_trades == 0
    assert out.sample_quality["label"] == "no_trades"
    assert out.max_drawdown_pct == 0.0
