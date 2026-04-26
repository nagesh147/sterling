"""
Indicator-only historical replay engine.
No options data needed — replays regime + signal over historical candle windows.
Uses only candles already fetched; no additional API calls inside this module.
"""
import time
from typing import List

from app.schemas.market import Candle
from app.schemas.backtest import BacktestBarResult, BacktestStats, BacktestResult
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.setup_engine import evaluate_setup
from app.schemas.directional import TradeState, MacroRegime

_MIN_4H_WINDOW = 55  # need at least 55 4H bars for EMA50
_MIN_1H_WINDOW = 30  # minimum 1H bars for SuperTrend


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

    for i in range(_MIN_1H_WINDOW, len(candles_1h), sample_every_n_bars):
        current_ts = candles_1h[i].timestamp_ms

        # Slice 4H candles to only those <= current bar (no look-ahead)
        c4h_slice = [c for c in candles_4h if c.timestamp_ms <= current_ts]
        if len(c4h_slice) < _MIN_4H_WINDOW:
            continue

        c1h_slice = candles_1h[max(0, i - 200) : i + 1]

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
                state=setup.state.value,
                direction=setup.direction.value,
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


def _compute_stats(bars: List[BacktestBarResult]) -> BacktestStats:
    if not bars:
        return _zero_stats()

    s = BacktestStats(
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
    )
    return s
