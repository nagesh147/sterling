"""
Historical replay engine: indicator signals + optional Black-Scholes option P&L.
No additional API calls — runs entirely on pre-fetched candles.
"""
import time
from typing import List, Optional

from app.schemas.market import Candle
from app.schemas.backtest import BacktestBarResult, BacktestStats, BacktestResult
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.setup_engine import evaluate_setup
from app.schemas.directional import TradeState
from app.engines.backtest.bs_pricing import bs_price, atm_option_pnl_pct

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
    atm_iv: Optional[float] = None,
    option_dte: int = 30,
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

        # Include only 4H bars whose CLOSE time is <= current bar timestamp.
        # A 4H bar that OPENS at T closes at T + 4h; using <= T would include
        # a bar whose close price is 4 hours in the future (look-ahead bias).
        _4H_MS = 4 * 3_600_000
        c4h_slice = [c for c in candles_4h if c.timestamp_ms + _4H_MS <= current_ts]
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
                **_bs_fields(candles_1h, i, signal.close_1h, setup.direction.value,
                             atm_iv, option_dte),
            )
        )

    stats = _compute_stats(bars, atm_iv is not None)
    return BacktestResult(
        underlying=underlying,
        lookback_days=lookback_days,
        sample_every_n_bars=sample_every_n_bars,
        total_1h_candles=len(candles_1h),
        total_4h_candles=len(candles_4h),
        bars=bars,
        stats=stats,
        timestamp_ms=now_ms,
        atm_iv_used=atm_iv,
        option_dte_used=option_dte if atm_iv is not None else None,
    )


def _bs_fields(
    candles: List[Candle],
    idx: int,
    spot_entry: float,
    direction: str,
    atm_iv: Optional[float],
    option_dte: int,
) -> dict:
    """Compute BS entry premium and forward P&L % for ATM option at this bar."""
    if atm_iv is None or spot_entry <= 0:
        return {}
    opt_type = "call" if direction == "long" else "put"
    entry_premium = bs_price(spot_entry, spot_entry, option_dte, atm_iv, opt_type)
    if entry_premium is None:
        return {}

    def _pnl(n_bars: int) -> Optional[float]:
        to_idx = idx + n_bars
        if to_idx >= len(candles):
            return None
        spot_exit = candles[to_idx].close
        dte_exit = max(0, option_dte - round(n_bars / 24))
        return atm_option_pnl_pct(spot_entry, spot_exit, option_dte, dte_exit, atm_iv, opt_type)

    return {
        "bs_entry_premium": round(entry_premium, 4),
        "bs_fwd_pnl_4h": _pnl(4),
        "bs_fwd_pnl_12h": _pnl(12),
        "bs_fwd_pnl_24h": _pnl(24),
    }


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


def _compute_stats(bars: List[BacktestBarResult], has_bs: bool = False) -> BacktestStats:
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
        bullish_regime_bars=sum(1 for b in bars if b.macro_regime in (
            "bullish", "bull_trending", "bull_weak", "bull_ranging"
        )),
        bearish_regime_bars=sum(1 for b in bars if b.macro_regime in (
            "bearish", "bear_trending", "bear_weak", "bear_ranging"
        )),
        neutral_regime_bars=sum(1 for b in bars if b.macro_regime in (
            "neutral", "choppy"
        )),
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
        # BS stats — only populated when atm_iv was supplied
        **(_bs_stats(bars) if has_bs else {}),
    )


def _bs_stats(bars: List[BacktestBarResult]) -> dict:
    ga_pnl = [b.bs_fwd_pnl_4h for b in bars if b.green_arrow and b.bs_fwd_pnl_4h is not None]
    ra_pnl = [b.bs_fwd_pnl_4h for b in bars if b.red_arrow and b.bs_fwd_pnl_4h is not None]
    return {
        "bs_arrow_long_avg_pnl_4h": _avg(ga_pnl),
        "bs_arrow_short_avg_pnl_4h": _avg(ra_pnl),
        "bs_arrow_long_win_rate_4h": _win_rate(ga_pnl, lambda v: v > 0),
        "bs_arrow_short_win_rate_4h": _win_rate(ra_pnl, lambda v: v > 0),
    }
