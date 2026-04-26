"""
Indicator-only historical replay engine with forward-return signal quality metrics.
No options data needed — replays regime + signal over historical candle windows.
Uses only candles already fetched; no additional API calls inside this module.
"""
import time
from typing import List, Optional

from app.schemas.market import Candle
from app.schemas.backtest import BacktestBarResult, BacktestStats, BacktestResult
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.setup_engine import evaluate_setup
from app.schemas.directional import TradeState

_MIN_4H_WINDOW = 55  # need at least 55 4H bars for EMA50
_MIN_1H_WINDOW = 30  # minimum 1H bars for SuperTrend


def _fwd_return(candles: List[Candle], from_idx: int, n_bars: int) -> Optional[float]:
    """% price change from candles[from_idx] to candles[from_idx + n_bars]."""
    to_idx = from_idx + n_bars
    if to_idx >= len(candles):
        return None
    base = candles[from_idx].close
    if base == 0:
        return None
    return round((candles[to_idx].close - base) / base * 100.0, 4)


def run_backtest(
    underlying: str,
    candles_4h: List[Candle],
    candles_1h: List[Candle],
    lookback_days: int,
    sample_every_n_bars: int = 4,
) -> BacktestResult:
    now_ms = int(time.time() * 1000)
    bars: List[BacktestBarResult] = []

    if len(candles_4h) < _MIN_4H_WINDOW or len(candles_1h) < _MIN_1H_WINDOW:
        return BacktestResult(
            underlying=underlying,
            lookback_days=lookback_days,
            sample_every_n_bars=sample_every_n_bars,
            total_1h_candles=len(candles_1h),
            total_4h_candles=len(candles_4h),
            bars=[],
            stats=_zero_stats(),
            timestamp_ms=now_ms,
        )

    # Track which 1H indices are sampled so we can compute forward returns
    sampled_indices: List[int] = list(range(_MIN_1H_WINDOW, len(candles_1h), sample_every_n_bars))

    for i in sampled_indices:
        current_ts = candles_1h[i].timestamp_ms

        # Slice 4H candles to only those <= current bar (no look-ahead)
        c4h_slice = [c for c in candles_4h if c.timestamp_ms <= current_ts]
        if len(c4h_slice) < _MIN_4H_WINDOW:
            continue

        c1h_slice = candles_1h[max(0, i - 200): i + 1]

        regime = compute_regime(c4h_slice)
        signal = compute_signal(c1h_slice)
        setup = evaluate_setup(regime, signal)

        bars.append(
            BacktestBarResult(
                timestamp_ms=current_ts,
                close_1h=signal.close_1h,
                close_4h=regime.close_4h,
                macro_regime=regime.macro_regime.value,
                ema50=regime.ema50,
                signal_trend=signal.trend,
                all_green=signal.all_green,
                all_red=signal.all_red,
                green_arrow=signal.green_arrow,
                red_arrow=signal.red_arrow,
                st_trends=signal.st_trends,
                st_values=signal.st_values,
                state=setup.state.value,
                direction=setup.direction.value,
                fwd_return_4h=_fwd_return(candles_1h, i, 4),
                fwd_return_12h=_fwd_return(candles_1h, i, 12),
                fwd_return_24h=_fwd_return(candles_1h, i, 24),
            )
        )

    stats = _compute_stats(bars)
    return BacktestResult(
        underlying=underlying,
        lookback_days=lookback_days,
        sample_every_n_bars=sample_every_n_bars,
        total_1h_candles=len(candles_1h),
        total_4h_candles=len(candles_4h),
        bars=bars,
        stats=stats,
        timestamp_ms=now_ms,
    )


def _zero_stats() -> BacktestStats:
    return BacktestStats(
        total_bars_evaluated=0,
        bullish_regime_bars=0, bearish_regime_bars=0, neutral_regime_bars=0,
        bullish_signal_bars=0, bearish_signal_bars=0, neutral_signal_bars=0,
        green_arrows=0, red_arrows=0,
        confirmed_long_setups=0, confirmed_short_setups=0,
        early_long_setups=0, early_short_setups=0,
        filtered_bars=0, idle_bars=0,
    )


def _win_rate(values: List[float], winning_condition) -> Optional[float]:
    if not values:
        return None
    wins = sum(1 for v in values if winning_condition(v))
    return round(wins / len(values) * 100.0, 1)


def _avg(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _compute_stats(bars: List[BacktestBarResult]) -> BacktestStats:
    if not bars:
        return _zero_stats()

    # Collect forward returns by category
    green_arrow_4h = [b.fwd_return_4h for b in bars if b.green_arrow and b.fwd_return_4h is not None]
    red_arrow_4h   = [b.fwd_return_4h for b in bars if b.red_arrow and b.fwd_return_4h is not None]
    green_arrow_12h = [b.fwd_return_12h for b in bars if b.green_arrow and b.fwd_return_12h is not None]
    red_arrow_12h   = [b.fwd_return_12h for b in bars if b.red_arrow and b.fwd_return_12h is not None]

    conf_long_4h  = [b.fwd_return_4h for b in bars
                     if b.state == TradeState.CONFIRMED_SETUP_ACTIVE and b.direction == "long"
                     and b.fwd_return_4h is not None]
    conf_short_4h = [b.fwd_return_4h for b in bars
                     if b.state == TradeState.CONFIRMED_SETUP_ACTIVE and b.direction == "short"
                     and b.fwd_return_4h is not None]
    conf_long_12h  = [b.fwd_return_12h for b in bars
                      if b.state == TradeState.CONFIRMED_SETUP_ACTIVE and b.direction == "long"
                      and b.fwd_return_12h is not None]
    conf_short_12h = [b.fwd_return_12h for b in bars
                      if b.state == TradeState.CONFIRMED_SETUP_ACTIVE and b.direction == "short"
                      and b.fwd_return_12h is not None]

    all_green_4h = [b.fwd_return_4h for b in bars if b.all_green and b.fwd_return_4h is not None]
    all_red_4h   = [b.fwd_return_4h for b in bars if b.all_red and b.fwd_return_4h is not None]

    return BacktestStats(
        total_bars_evaluated=len(bars),
        bullish_regime_bars=sum(1 for b in bars if b.macro_regime == "bullish"),
        bearish_regime_bars=sum(1 for b in bars if b.macro_regime == "bearish"),
        neutral_regime_bars=sum(1 for b in bars if b.macro_regime == "neutral"),
        bullish_signal_bars=sum(1 for b in bars if b.signal_trend == 1),
        bearish_signal_bars=sum(1 for b in bars if b.signal_trend == -1),
        neutral_signal_bars=sum(1 for b in bars if b.signal_trend == 0),
        green_arrows=sum(1 for b in bars if b.green_arrow),
        red_arrows=sum(1 for b in bars if b.red_arrow),
        confirmed_long_setups=sum(
            1 for b in bars if b.state == TradeState.CONFIRMED_SETUP_ACTIVE and b.direction == "long"
        ),
        confirmed_short_setups=sum(
            1 for b in bars if b.state == TradeState.CONFIRMED_SETUP_ACTIVE and b.direction == "short"
        ),
        early_long_setups=sum(
            1 for b in bars if b.state == TradeState.EARLY_SETUP_ACTIVE and b.direction == "long"
        ),
        early_short_setups=sum(
            1 for b in bars if b.state == TradeState.EARLY_SETUP_ACTIVE and b.direction == "short"
        ),
        filtered_bars=sum(1 for b in bars if b.state == TradeState.FILTERED),
        idle_bars=sum(1 for b in bars if b.state == TradeState.IDLE),
        # Signal quality
        arrow_long_win_rate_4h=_win_rate(green_arrow_4h, lambda v: v > 0),
        arrow_short_win_rate_4h=_win_rate(red_arrow_4h, lambda v: v < 0),
        setup_long_avg_return_4h=_avg(conf_long_4h),
        setup_short_avg_return_4h=_avg([abs(v) for v in conf_short_4h]),  # abs because short gains = negative return
        signal_accuracy_long_4h=_win_rate(all_green_4h, lambda v: v > 0),
        signal_accuracy_short_4h=_win_rate(all_red_4h, lambda v: v < 0),
        arrow_long_win_rate_12h=_win_rate(green_arrow_12h, lambda v: v > 0),
        arrow_short_win_rate_12h=_win_rate(red_arrow_12h, lambda v: v < 0),
        setup_long_avg_return_12h=_avg(conf_long_12h),
        setup_short_avg_return_12h=_avg([abs(v) for v in conf_short_12h]),
    )
