import pytest
from tests.conftest import make_candles
from app.engines.directional.signal_engine import compute_signal, _rsi_ok_long, _rsi_ok_short
from app.engines.backtest.backtest_engine import simulate_capital_curve
from app.schemas.backtest import BacktestBarResult


# ── RSI helper tests ──────────────────────────────────────────────────────────

def test_rsi_ok_long_bounds():
    assert _rsi_ok_long(42.1) is True
    assert _rsi_ok_long(42.0) is False   # lower boundary exclusive
    assert _rsi_ok_long(69.9) is True
    assert _rsi_ok_long(70.0) is False   # upper boundary exclusive


def test_rsi_ok_short_bounds():
    assert _rsi_ok_short(30.1) is True
    assert _rsi_ok_short(30.0) is False   # lower boundary exclusive
    assert _rsi_ok_short(56.9) is True
    assert _rsi_ok_short(57.0) is False   # upper boundary exclusive


# ── bars_since_flip field ─────────────────────────────────────────────────────

def test_signal_result_has_bars_since_flip():
    candles = make_candles(80, base=30000.0, trend=10.0)
    result = compute_signal(candles)
    assert hasattr(result, 'bars_since_flip')
    assert isinstance(result.bars_since_flip, int)
    assert result.bars_since_flip >= 0


def test_bars_since_flip_zero_on_short_series():
    """Series too short returns bars_since_flip=0."""
    candles = make_candles(10, base=30000.0, trend=10.0)
    result = compute_signal(candles)
    assert result.bars_since_flip == 0


def test_signal_score_in_valid_range_after_changes():
    """signal_score must remain in [0, 20] after RSI + staleness changes."""
    for trend_factor in [0.0, 10.0, -10.0, 50.0]:
        candles = make_candles(80, base=30000.0, trend=trend_factor)
        result = compute_signal(candles)
        assert 0.0 <= result.signal_score <= 20.0, f"trend={trend_factor}: score={result.signal_score}"


# ── fwd_horizon param ─────────────────────────────────────────────────────────

def _make_bar(fwd4=1.0, fwd12=-1.0, fwd24=0.5):
    return BacktestBarResult(
        timestamp_ms=1_700_000_000_000, close_1h=30000.0, close_4h=30000.0,
        macro_regime='BULL_TREND', ema50=29000.0, signal_trend=1,
        all_green=True, all_red=False, green_arrow=True, red_arrow=False,
        st_trends=[1,1,1], st_values=[29900.0,29800.0,29700.0],
        state='CONFIRMED_SETUP_ACTIVE', direction='long',
        fwd_return_4h=fwd4, fwd_return_12h=fwd12, fwd_return_24h=fwd24,
        signal_score=16.0,
    )


def test_fwd_horizon_4h_uses_4h_return():
    """fwd_horizon='4h' uses fwd_return_4h; '12h' uses fwd_return_12h."""
    # bar has fwd4=+2% (win), fwd12=-2% (loss)
    bars = [_make_bar(fwd4=2.0, fwd12=-2.0), _make_bar(fwd4=2.0, fwd12=-2.0)]
    sim4  = simulate_capital_curve(bars, capital=10_000, hold_bars=1, fwd_horizon='4h')
    sim12 = simulate_capital_curve(bars, capital=10_000, hold_bars=1, fwd_horizon='12h')
    # 4h sim takes the +2% → should win; 12h sim takes the -2% → should lose
    if sim4['trades'] and sim12['trades']:
        assert sim4['trades'][0]['pnl_pct'] > sim12['trades'][0]['pnl_pct']


def test_fwd_horizon_default_is_12h():
    """Calling without fwd_horizon must use fwd_return_12h (backward compat)."""
    bars = [_make_bar(fwd4=99.0, fwd12=1.5), _make_bar(fwd4=99.0, fwd12=1.5)]
    default = simulate_capital_curve(bars, capital=10_000, hold_bars=1)
    explicit = simulate_capital_curve(bars, capital=10_000, hold_bars=1, fwd_horizon='12h')
    if default['trades'] and explicit['trades']:
        assert abs(default['trades'][0]['pnl_pct'] - explicit['trades'][0]['pnl_pct']) < 1e-9
