import pytest
from tests.conftest import make_candles
from app.engines.directional.signal_engine import compute_signal

def test_compute_signal_accepts_custom_st_configs():
    """compute_signal must accept st_configs param without error."""
    candles = make_candles(60, base=30000.0, trend=10.0)
    scalping_configs = [(5, 2.5), (10, 1.5), (14, 1.0)]
    result = compute_signal(candles, st_configs=scalping_configs)
    assert result.signal_score >= 0.0
    assert result.signal_score <= 20.0

def test_compute_signal_accepts_custom_st_threshold():
    """st_threshold=2 requires fewer ST agreements than st_threshold=3."""
    # Use enough candles for a stable supertrend
    candles = make_candles(80, base=30000.0, trend=10.0)
    # Both should run without error and return valid scores
    result_strict  = compute_signal(candles, st_threshold=3)
    result_relaxed = compute_signal(candles, st_threshold=2)
    assert 0.0 <= result_strict.signal_score  <= 20.0
    assert 0.0 <= result_relaxed.signal_score <= 20.0
    # If strict is all_green, relaxed must also be (lower threshold = more inclusive)
    if result_strict.all_green:
        assert result_relaxed.all_green

def test_compute_signal_default_unchanged():
    """Default call (no new params) returns same result as before."""
    candles = make_candles(60, base=30000.0, trend=10.0)
    r1 = compute_signal(candles)
    r2 = compute_signal(candles, st_configs=None, st_threshold=3)
    assert r1.signal_score == r2.signal_score
    assert r1.trend == r2.trend


# ── MTF engine tests ──────────────────────────────────────────────────────────

import time as _time
from app.schemas.market import Candle as _Candle

def _make_candles_ms(n, base, trend, bar_ms):
    """Make candles with realistic timestamps spaced bar_ms apart."""
    now_ms = int(_time.time() * 1000)
    candles = []
    for i in range(n):
        ts = now_ms - (n - i) * bar_ms
        price = base + trend * i + (i % 3) * 0.5
        candles.append(_Candle(
            timestamp_ms=ts, open=price, high=price * 1.001,
            low=price * 0.999, close=price, volume=100.0 + i,
        ))
    return candles


def test_run_mtf_backtest_scalping_returns_result():
    """run_mtf_backtest must return a dict with scalping_15m key."""
    from app.engines.backtest.backtest_mtf import run_mtf_backtest
    c_15m = _make_candles_ms(200, 30000, 5, 15 * 60_000)
    c_1h  = _make_candles_ms(120, 30000, 5, 60 * 60_000)
    c_4h  = _make_candles_ms(80,  30000, 5, 4 * 60 * 60_000)
    result = run_mtf_backtest("BTC", c_15m, c_1h, c_4h, profiles=["scalping_15m"])
    assert "scalping_15m" in result
    r = result["scalping_15m"]
    assert "label" in r
    assert "sharpe" in r
    assert "win_rate" in r
    assert "total_trades" in r
    assert "equity_curve" in r


def test_run_mtf_backtest_intraday_1h_returns_result():
    """intraday_1h profile must return same shape as scalping."""
    from app.engines.backtest.backtest_mtf import run_mtf_backtest
    c_15m = _make_candles_ms(200, 30000, 5, 15 * 60_000)
    c_1h  = _make_candles_ms(120, 30000, 5, 60 * 60_000)
    c_4h  = _make_candles_ms(80,  30000, 5, 4 * 60 * 60_000)
    result = run_mtf_backtest("BTC", c_15m, c_1h, c_4h, profiles=["intraday_1h"])
    assert "intraday_1h" in result
    r = result["intraday_1h"]
    for key in ("label", "sharpe", "win_rate", "total_trades", "equity_curve",
                "profit_factor", "max_drawdown", "fwd1_label", "fwd1_long_win_rate"):
        assert key in r, f"missing key: {key}"


def test_run_mtf_backtest_all_profiles():
    """Running all 3 profiles returns all 3 keys."""
    from app.engines.backtest.backtest_mtf import run_mtf_backtest
    c_15m = _make_candles_ms(300, 30000, 5, 15 * 60_000)
    c_1h  = _make_candles_ms(150, 30000, 5, 60 * 60_000)
    c_4h  = _make_candles_ms(100, 30000, 5, 4 * 60 * 60_000)
    c_1d  = _make_candles_ms(40,  30000, 5, 24 * 60 * 60_000)
    result = run_mtf_backtest("BTC", c_15m, c_1h, c_4h, c_1d=c_1d)
    for key in ("scalping_15m", "intraday_1h", "intraday_4h"):
        assert key in result


def test_run_mtf_empty_candles_returns_gracefully():
    """Empty candle lists must not raise — return zero-trade result."""
    from app.engines.backtest.backtest_mtf import run_mtf_backtest
    result = run_mtf_backtest("BTC", [], [], [], profiles=["scalping_15m"])
    assert result["scalping_15m"]["total_trades"] == 0


# ── Schema test ───────────────────────────────────────────────────────────────

def test_mtf_endpoint_schema():
    """MTFBacktestRequest and MTFBacktestResult must be importable and valid."""
    from app.schemas.backtest import MTFBacktestRequest, MTFBacktestResult
    req = MTFBacktestRequest(underlying="BTC", lookback_days=30)
    assert req.underlying == "BTC"
    assert "scalping_15m" in req.profiles
    assert "intraday_1h" in req.profiles
    # MTFBacktestResult is instantiable
    result = MTFBacktestResult(
        underlying="BTC",
        profiles={"scalping_15m": {"total_trades": 0}},
        timestamp_ms=0,
    )
    assert result.recommended is None
