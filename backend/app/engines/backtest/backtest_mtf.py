"""
Multi-timeframe backtest engine.
Bar-by-bar strategy replay for scalping (15M/1H) and intraday (1H/4H, 4H/1D) profiles.
Pure functions — no I/O.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Any, Tuple
import numpy as np

from app.schemas.market import Candle
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.setup_engine import evaluate_setup
from app.schemas.directional import TradeState
from app.engines.indicators.atr import compute_atr
from app.engines.analytics.performance import full_report
from app.engines.backtest.costs import compute_trade_costs, next_bar_open_fill

_FEE_RT_PCT = 0.001  # 0.10% round-trip taker


@dataclass
class TFProfile:
    label: str
    signal_tf: str
    regime_tf: str
    signal_bar_ms: int
    regime_bar_ms: int
    st_configs: List[Tuple[int, float]]
    min_signal_bars: int
    min_regime_bars: int
    fwd_labels: List[str]
    fwd_bars: List[int]      # n signal bars for each forward horizon
    hold_bars: int
    # Issue 6 — exit ATR timeframe.
    # "regime" (legacy): exits scale to regime-TF ATR; "signal": exits scale to
    # signal-TF ATR — tighter stops when signal_TF << regime_TF (e.g. 1H trades
    # under 4H regime). Default preserves legacy behavior.
    exit_atr_tf: Literal["signal", "regime"] = "regime"
    # Issue 7 — payoff mode.
    # "fixed_2r" (legacy): one-shot exit at +2R / -1R / hold_bars / trend flip.
    # "chandelier_trail": 50% partial at +1R, breakeven move, then trail rest
    # with Chandelier(N=22, mult=3.0*ATR(signal_TF)). Default preserves legacy.
    payoff_mode: Literal["fixed_2r", "chandelier_trail"] = "fixed_2r"


PROFILES: Dict[str, TFProfile] = {
    "scalping_15m": TFProfile(
        label="Scalping 15M",
        signal_tf="15m", regime_tf="1H",
        signal_bar_ms=15 * 60_000,
        regime_bar_ms=60 * 60_000,
        st_configs=[(5, 2.5), (10, 1.5), (14, 1.0)],
        min_signal_bars=50, min_regime_bars=30,
        fwd_labels=["1H", "4H", "12H"],
        fwd_bars=[4, 16, 48],
        hold_bars=6,
    ),
    "intraday_1h": TFProfile(
        label="Intraday 1H",
        signal_tf="1H", regime_tf="4H",
        signal_bar_ms=60 * 60_000,
        regime_bar_ms=4 * 60 * 60_000,
        st_configs=[(7, 3.0), (14, 2.0), (21, 2.0)],
        min_signal_bars=30, min_regime_bars=55,
        fwd_labels=["4H", "12H", "24H"],
        fwd_bars=[4, 12, 24],
        hold_bars=8,
    ),
    "intraday_4h": TFProfile(
        label="Intraday 4H",
        signal_tf="4H", regime_tf="1D",
        signal_bar_ms=4 * 60 * 60_000,
        regime_bar_ms=24 * 60 * 60_000,
        st_configs=[(10, 3.0), (20, 2.0), (28, 1.5)],
        min_signal_bars=30, min_regime_bars=20,
        fwd_labels=["24H", "48H", "96H"],
        fwd_bars=[6, 12, 24],
        hold_bars=12,
    ),
}


def _fwd_return(candles: List[Candle], from_idx: int, n_bars: int) -> Optional[float]:
    to_idx = from_idx + n_bars
    if to_idx >= len(candles):
        return None
    base = candles[from_idx].close
    if base <= 0:
        return None
    return round((candles[to_idx].close - base) / base * 100.0, 4)


def _zero_result(profile: TFProfile, n_signal: int = 0, n_regime: int = 0, underlying: str = "") -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "label": profile.label,
        "signal_tf": profile.signal_tf,
        "regime_tf": profile.regime_tf,
        "underlying": underlying,
        "total_signal_bars": n_signal,
        "total_regime_bars": n_regime,
        "total_trades": 0,
        "win_rate": None,
        "sharpe": None,
        "calmar": None,
        "sortino": None,
        "profit_factor": None,
        "max_drawdown": None,
        "avg_rr": None,
        "equity_curve": [1.0, 1.0],
        "regime_breakdown": {},
    }
    for k, lbl in enumerate(profile.fwd_labels):
        result[f"fwd{k+1}_label"]          = lbl
        result[f"fwd{k+1}_long_win_rate"]  = None
        result[f"fwd{k+1}_short_win_rate"] = None
    return result


def _build_atr_series(candles: List[Candle], period: int = 14) -> np.ndarray:
    """Pre-compute ATR over the entire candle series once (Issue 15)."""
    if not candles:
        return np.array([], dtype=np.float64)
    highs = np.array([c.high for c in candles], dtype=np.float64)
    lows  = np.array([c.low  for c in candles], dtype=np.float64)
    closes = np.array([c.close for c in candles], dtype=np.float64)
    return compute_atr(highs, lows, closes, period)


def _replay_profile(
    profile: TFProfile,
    candles_signal: List[Candle],
    candles_regime: List[Candle],
    score_min: float = 0.0,
    fee_rt_pct: float = _FEE_RT_PCT,
    underlying: str = "",
    *,
    leverage: float = 1.0,
    oi: Optional[float] = None,
    funding_8h_pct: float = 0.0,
    option_spread_pct: Optional[float] = None,
    apply_slippage: bool = True,
    emit_events: bool = False,
) -> Dict[str, Any]:
    """
    Bar-by-bar trade replay for one TF profile with truthful fills and costs.

    Entry: CONFIRMED_SETUP_ACTIVE + signal_score >= score_min.
    Exit:  trend reversal | ATR-based +2R/-1R | hold_bars elapsed
           (legacy `fixed_2r`), or partial 50% at +1R + breakeven + chandelier
           trail (opt-in `chandelier_trail`).

    Fills land on the OPEN of the bar following the signal bar (no signal-bar
    close execution). Slippage, fees, perpetual funding (by actual hold time),
    and optional option half-spread are attributed via `costs.compute_trade_costs`.
    Trades record both gross and net PnL with full cost breakdown.

    When `emit_events=True`, the result includes an `events` list containing
    candidate/skip/entry/exit records in chronological order. Default output
    shape is unchanged.

    Issue 15: regime slicing was O(N) inside an O(N) loop; we now maintain a
    monotonically advancing cursor `regime_idx` and pre-compute the regime
    and signal ATR series once.
    """
    n_signal = len(candles_signal)
    n_regime = len(candles_regime)

    if n_signal < profile.min_signal_bars or n_regime < profile.min_regime_bars:
        zero = _zero_result(profile, n_signal, n_regime, underlying=underlying)
        if emit_events:
            zero["events"] = []
        return zero

    # Lazy-import to avoid circular dependency
    if emit_events:
        from app.engines.backtest.event_ledger import EventLedger
        ledger = EventLedger()
    else:
        ledger = None

    signal_bar_ms = profile.signal_bar_ms
    regime_bar_ms = profile.regime_bar_ms

    # Issue 15 — pre-compute regime and signal ATR series once.
    regime_atr_full = _build_atr_series(candles_regime, period=14)
    signal_atr_full = _build_atr_series(candles_signal, period=14)
    # For trail/chandelier: ATR(22) on signal TF.
    signal_atr22_full = _build_atr_series(candles_signal, period=22)
    # Regime timestamps for monotonic cursor.
    regime_ts = np.array(
        [c.timestamp_ms for c in candles_regime], dtype=np.int64,
    )

    use_signal_atr = profile.exit_atr_tf == "signal"
    use_trail = profile.payoff_mode == "chandelier_trail"

    trades: List[Dict[str, Any]] = []
    in_trade      = False
    entry_bar     = 0           # index of the signal bar that triggered entry
    entry_fill_bar = 0          # index of the bar where entry actually filled
    entry_dir     = 0
    entry_price   = 0.0         # clean fill price (next bar open)
    entry_atr     = 0.0
    entry_regime  = "unknown"
    entry_ts_ms   = 0
    # Trail state (only used in chandelier_trail mode)
    trail_partial_taken = False
    trail_extreme_price = 0.0       # max high (long) / min low (short) since entry
    trail_stop_price    = 0.0
    trail_remaining_ratio = 1.0     # 1.0 then 0.5 after partial

    regime_idx = 0  # cursor: number of regime bars whose close <= current ts

    for i in range(profile.min_signal_bars, n_signal - 1):
        ts = candles_signal[i].timestamp_ms

        # Issue 15 — advance the regime cursor monotonically instead of
        # re-slicing on every iteration. A regime bar at index k "closes"
        # at regime_ts[k] + regime_bar_ms.
        while regime_idx < n_regime and regime_ts[regime_idx] + regime_bar_ms <= ts:
            regime_idx += 1
        if regime_idx < profile.min_regime_bars:
            continue
        c_regime = candles_regime[:regime_idx]
        c_signal = candles_signal[max(0, i - 200): i + 1]

        regime = compute_regime(c_regime)
        signal = compute_signal(c_signal, st_configs=profile.st_configs)
        setup  = evaluate_setup(regime, signal)

        # ── Exit logic ─────────────────────────────────────────────────────────
        just_exited = False
        if in_trade:
            cur_close = candles_signal[i].close
            cur_high  = candles_signal[i].high
            cur_low   = candles_signal[i].low
            held = i - entry_bar
            gain_abs = entry_dir * (cur_close - entry_price)

            # Trail/chandelier path is computed alongside legacy exits so
            # both modes follow the same hold-bars / trend-reversal guards.
            if use_trail and entry_atr > 0 and entry_price > 0:
                # Update extreme since entry
                if entry_dir == 1:
                    if cur_high > trail_extreme_price:
                        trail_extreme_price = cur_high
                else:
                    if cur_low < trail_extreme_price or trail_extreme_price == 0.0:
                        trail_extreme_price = cur_low

                # Partial-take at +1R
                if (not trail_partial_taken) and gain_abs >= entry_atr:
                    fill = next_bar_open_fill(candles_signal, i)
                    if fill is not None:
                        partial_px, partial_fill_bar = fill
                        partial_ts_ms = candles_signal[partial_fill_bar].timestamp_ms
                        partial_hold_hours = max(
                            0.0, (partial_ts_ms - entry_ts_ms) / 3_600_000.0
                        )
                        partial_breakdown = compute_trade_costs(
                            direction=entry_dir,
                            entry_price=entry_price,
                            exit_price=partial_px,
                            leverage=leverage,
                            oi=oi,
                            fee_rt_pct=fee_rt_pct * 0.5,  # half RT for partial
                            hold_hours=partial_hold_hours,
                            funding_8h_pct=funding_8h_pct,
                            option_spread_pct=option_spread_pct,
                            apply_slippage=apply_slippage,
                            forced_end=False,
                        )
                        # Book the partial as a synthetic half-trade.
                        partial_trade = {
                            "pnl_pct":         partial_breakdown.net_pnl_pct * 0.5,
                            "gross_pnl_pct":   partial_breakdown.gross_pnl_pct * 0.5,
                            "net_pnl_pct":     partial_breakdown.net_pnl_pct * 0.5,
                            "cost_pct":        partial_breakdown.total_cost_pct * 0.5,
                            "slippage_pct":    partial_breakdown.slippage_pct,
                            "fee_pct":         partial_breakdown.fee_pct,
                            "funding_pct":     partial_breakdown.funding_pct,
                            "option_spread_pct": partial_breakdown.option_spread_pct,
                            "entry_price":     partial_breakdown.effective_entry_price,
                            "exit_price":      partial_breakdown.effective_exit_price,
                            "hold_hours":      partial_breakdown.hold_hours,
                            "regime":          entry_regime,
                            "entry_bar":       entry_bar,
                            "exit_bar":        partial_fill_bar,
                            "entry_ts_ms":     entry_ts_ms,
                            "exit_ts_ms":      partial_ts_ms,
                            "direction":       "long" if entry_dir == 1 else "short",
                            "forced_end":      False,
                            "partial":         True,
                            "asset":           underlying,
                            "profile":         profile.label,
                            "track":           "directional",
                        }
                        trades.append(partial_trade)
                        if ledger is not None:
                            ledger.record_exit(partial_trade)
                            ledger.record_trade(partial_trade)
                        trail_partial_taken = True
                        trail_remaining_ratio = 0.5
                        # Move stop to breakeven
                        trail_stop_price = entry_price

                # Chandelier trail on remaining position
                idx22 = i if i < len(signal_atr22_full) else len(signal_atr22_full) - 1
                atr22 = float(signal_atr22_full[idx22]) if (
                    idx22 >= 0 and not np.isnan(signal_atr22_full[idx22])
                ) else entry_atr
                if atr22 <= 0:
                    atr22 = entry_atr
                proposed = (
                    trail_extreme_price - 3.0 * atr22 if entry_dir == 1
                    else trail_extreme_price + 3.0 * atr22
                )
                if trail_partial_taken:
                    # After breakeven move, trail can only tighten the stop
                    if entry_dir == 1:
                        trail_stop_price = max(trail_stop_price, proposed)
                    else:
                        trail_stop_price = (
                            min(trail_stop_price, proposed) if trail_stop_price > 0
                            else proposed
                        )

                # Exit on stop hit
                if trail_partial_taken:
                    if entry_dir == 1 and cur_low <= trail_stop_price:
                        exit_now = True
                    elif entry_dir == -1 and cur_high >= trail_stop_price:
                        exit_now = True
                    else:
                        exit_now = False
                else:
                    # Pre-partial: only the original -1R stop applies
                    exit_now = gain_abs <= -entry_atr

                if not exit_now:
                    exit_now = held >= profile.hold_bars
                if not exit_now:
                    if entry_dir == 1 and signal.trend == -1:
                        exit_now = True
                    elif entry_dir == -1 and signal.trend == 1:
                        exit_now = True
            else:
                exit_now = held >= profile.hold_bars
                if not exit_now and entry_atr > 0 and entry_price > 0:
                    exit_now = gain_abs >= 2 * entry_atr or gain_abs <= -entry_atr
                if not exit_now:
                    if entry_dir == 1 and signal.trend == -1:
                        exit_now = True
                    elif entry_dir == -1 and signal.trend == 1:
                        exit_now = True

            if exit_now:
                # Exit fills at next bar open (no signal-bar close execution)
                fill = next_bar_open_fill(candles_signal, i)
                if fill is None:
                    # No future bar — defer to forced end-of-data handler below
                    pass
                else:
                    exit_px, exit_fill_bar = fill
                    exit_ts_ms = candles_signal[exit_fill_bar].timestamp_ms
                    hold_hours = max(
                        0.0, (exit_ts_ms - entry_ts_ms) / 3_600_000.0
                    )
                    rem_fee = fee_rt_pct * trail_remaining_ratio
                    breakdown = compute_trade_costs(
                        direction=entry_dir,
                        entry_price=entry_price,
                        exit_price=exit_px,
                        leverage=leverage,
                        oi=oi,
                        fee_rt_pct=rem_fee,
                        hold_hours=hold_hours,
                        funding_8h_pct=funding_8h_pct,
                        option_spread_pct=option_spread_pct,
                        apply_slippage=apply_slippage,
                        forced_end=False,
                    )
                    trade = {
                        "pnl_pct":         breakdown.net_pnl_pct * trail_remaining_ratio,
                        "gross_pnl_pct":   breakdown.gross_pnl_pct * trail_remaining_ratio,
                        "net_pnl_pct":     breakdown.net_pnl_pct * trail_remaining_ratio,
                        "cost_pct":        breakdown.total_cost_pct * trail_remaining_ratio,
                        "slippage_pct":    breakdown.slippage_pct,
                        "fee_pct":         breakdown.fee_pct,
                        "funding_pct":     breakdown.funding_pct,
                        "option_spread_pct": breakdown.option_spread_pct,
                        "entry_price":     breakdown.effective_entry_price,
                        "exit_price":      breakdown.effective_exit_price,
                        "hold_hours":      breakdown.hold_hours,
                        "regime":          entry_regime,
                        "entry_bar":       entry_bar,
                        "exit_bar":        exit_fill_bar,
                        "entry_ts_ms":     entry_ts_ms,
                        "exit_ts_ms":      exit_ts_ms,
                        "direction":       "long" if entry_dir == 1 else "short",
                        "forced_end":      False,
                        "partial":         False,
                        "asset":           underlying,
                        "profile":         profile.label,
                        "track":           "directional",
                    }
                    trades.append(trade)
                    if ledger is not None:
                        ledger.record_exit(trade)
                        ledger.record_trade(trade)
                    in_trade    = False
                    just_exited = True
                    trail_partial_taken = False
                    trail_remaining_ratio = 1.0
                    trail_extreme_price = 0.0
                    trail_stop_price = 0.0

        # ── Entry logic ────────────────────────────────────────────────────────
        if not in_trade and not just_exited:
            sig_score = float(getattr(signal, "signal_score", 0.0) or 0.0)
            qualifies = (
                setup.state == TradeState.CONFIRMED_SETUP_ACTIVE
                and sig_score >= score_min
                and signal.trend != 0
            )
            if qualifies:
                fill = next_bar_open_fill(candles_signal, i)
                if fill is None:
                    # Signal on the last evaluable bar with no future open —
                    # explicitly skip to avoid last-bar lookahead.
                    if ledger is not None:
                        ledger.record_skip(
                            bar_idx=i, ts_ms=ts, asset=underlying,
                            profile=profile.label, track="directional",
                            reason="no_future_bar_for_entry_fill",
                        )
                    continue
                entry_px, entry_fill_bar = fill
                in_trade       = True
                entry_bar      = i
                entry_dir      = signal.trend
                entry_price    = entry_px
                entry_ts_ms    = candles_signal[entry_fill_bar].timestamp_ms
                entry_regime   = regime.macro_regime.value
                # Issue 6 — ATR source flag-controlled.
                if use_signal_atr:
                    arr = signal_atr_full
                    # We use signal-bar i, but ATR is undefined at the very
                    # first 14 bars; we already pass min_signal_bars >= 30.
                    idx = i if i < len(arr) else len(arr) - 1
                    v = float(arr[idx]) if (idx >= 0 and not np.isnan(arr[idx])) else 0.0
                else:
                    arr = regime_atr_full
                    idx = regime_idx - 1
                    v = float(arr[idx]) if (
                        0 <= idx < len(arr) and not np.isnan(arr[idx])
                    ) else 0.0
                entry_atr = v if v > 0 else entry_price * 0.02
                # Reset trail state on entry
                trail_partial_taken = False
                trail_remaining_ratio = 1.0
                trail_extreme_price = entry_price
                trail_stop_price = 0.0
                if ledger is not None:
                    ledger.record_entry({
                        "bar_idx":   entry_fill_bar,
                        "signal_bar_idx": i,
                        "ts_ms":     entry_ts_ms,
                        "asset":     underlying,
                        "profile":   profile.label,
                        "track":     "directional",
                        "direction": "long" if entry_dir == 1 else "short",
                        "entry_price": entry_price,
                        "regime":    entry_regime,
                        "sig_score": sig_score,
                    })
            elif ledger is not None and setup.state != TradeState.CONFIRMED_SETUP_ACTIVE:
                ledger.record_skip(
                    bar_idx=i, ts_ms=ts, asset=underlying,
                    profile=profile.label, track="directional",
                    reason=f"setup_state={setup.state.value}",
                )

    # Close any open trade at end of data (no future bar — fill at last close,
    # forced end-of-data, explicitly marked).
    if in_trade:
        last_i  = n_signal - 1
        exit_px = candles_signal[last_i].close
        exit_ts_ms = candles_signal[last_i].timestamp_ms
        hold_hours = max(0.0, (exit_ts_ms - entry_ts_ms) / 3_600_000.0)
        rem_fee = fee_rt_pct * trail_remaining_ratio
        breakdown = compute_trade_costs(
            direction=entry_dir,
            entry_price=entry_price,
            exit_price=exit_px,
            leverage=leverage,
            oi=oi,
            fee_rt_pct=rem_fee,
            hold_hours=hold_hours,
            funding_8h_pct=funding_8h_pct,
            option_spread_pct=option_spread_pct,
            apply_slippage=apply_slippage,
            forced_end=True,
        )
        trade = {
            "pnl_pct":         breakdown.net_pnl_pct * trail_remaining_ratio,
            "gross_pnl_pct":   breakdown.gross_pnl_pct * trail_remaining_ratio,
            "net_pnl_pct":     breakdown.net_pnl_pct * trail_remaining_ratio,
            "cost_pct":        breakdown.total_cost_pct * trail_remaining_ratio,
            "slippage_pct":    breakdown.slippage_pct,
            "fee_pct":         breakdown.fee_pct,
            "funding_pct":     breakdown.funding_pct,
            "option_spread_pct": breakdown.option_spread_pct,
            "entry_price":     breakdown.effective_entry_price,
            "exit_price":      breakdown.effective_exit_price,
            "hold_hours":      breakdown.hold_hours,
            "regime":          entry_regime,
            "entry_bar":       entry_bar,
            "exit_bar":        last_i,
            "entry_ts_ms":     entry_ts_ms,
            "exit_ts_ms":      exit_ts_ms,
            "direction":       "long" if entry_dir == 1 else "short",
            "forced_end":      True,
            "partial":         False,
            "asset":           underlying,
            "profile":         profile.label,
            "track":           "directional",
        }
        trades.append(trade)
        if ledger is not None:
            ledger.record_exit(trade)
            ledger.record_trade(trade)

    # ── Forward-return win rates per horizon (arrow-based) ────────────────────
    # Pass 1: compute signals once per bar. Regime cursor advances monotonically.
    _bar_signals: Dict[int, Any] = {}
    fwd_regime_idx = 0
    for j in range(profile.min_signal_bars, n_signal):
        ts_j = candles_signal[j].timestamp_ms
        while (fwd_regime_idx < n_regime
               and regime_ts[fwd_regime_idx] + regime_bar_ms <= ts_j):
            fwd_regime_idx += 1
        if fwd_regime_idx < profile.min_regime_bars:
            continue
        c_sig_j = candles_signal[max(0, j - 200): j + 1]
        try:
            _bar_signals[j] = compute_signal(c_sig_j, st_configs=profile.st_configs)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "compute_signal failed at bar %d: %s", j, exc
            )
            continue

    # Pass 2: collect forward returns per horizon (reuses precomputed signals)
    fwd_win_rates: List[Tuple[str, Optional[float], Optional[float]]] = []
    for n_bars, lbl in zip(profile.fwd_bars, profile.fwd_labels):
        long_rets: List[float]  = []
        short_rets: List[float] = []
        for j, sig_j in _bar_signals.items():
            fwd = _fwd_return(candles_signal, j, n_bars)
            if fwd is None:
                continue
            if sig_j.green_arrow:
                long_rets.append(fwd)
            elif sig_j.red_arrow:
                short_rets.append(fwd)
        long_wr = (
            round(sum(1 for r in long_rets  if r > 0) / len(long_rets)  * 100, 1)
            if long_rets else None
        )
        short_wr = (
            round(sum(1 for r in short_rets if r < 0) / len(short_rets) * 100, 1)
            if short_rets else None
        )
        fwd_win_rates.append((lbl, long_wr, short_wr))

    # ── Build result dict ─────────────────────────────────────────────────────
    if not trades:
        result = _zero_result(profile, n_signal, n_regime, underlying=underlying)
        for k, (lbl, lwr, swr) in enumerate(fwd_win_rates):
            result[f"fwd{k+1}_label"]          = lbl
            result[f"fwd{k+1}_long_win_rate"]  = lwr
            result[f"fwd{k+1}_short_win_rate"] = swr
        if emit_events and ledger is not None:
            result["events"] = ledger.events_as_dicts()
        return result

    pnls = [t["pnl_pct"] for t in trades]
    curve = np.ones(len(pnls) + 1, dtype=np.float64)
    for idx, p in enumerate(pnls):
        curve[idx + 1] = curve[idx] * (1.0 + p)

    # Per-bar (signal-bar) timestamps for honest Sharpe — performance.full_report
    # uses these to compute calendar-time daily returns when available.
    rpt = full_report(curve, trades, signal_bar_ms=signal_bar_ms)

    gross_total = float(sum(t.get("gross_pnl_pct", t["pnl_pct"]) for t in trades))
    cost_total  = float(sum(t.get("cost_pct", 0.0) for t in trades))
    net_total   = float(sum(t["pnl_pct"] for t in trades))

    result: Dict[str, Any] = {
        "label":             profile.label,
        "signal_tf":         profile.signal_tf,
        "regime_tf":         profile.regime_tf,
        "underlying":        underlying,
        "total_signal_bars": n_signal,
        "total_regime_bars": n_regime,
        "total_trades":      len(trades),
        "win_rate":          round(rpt.win_rate * 100, 1),
        "sharpe":            round(rpt.sharpe, 3),
        "calmar":            round(rpt.calmar, 3),
        "sortino":           round(rpt.sortino, 3),
        "profit_factor":     (None if rpt.profit_factor is None
                              else (float("inf") if rpt.profit_factor == float("inf")
                                    else round(rpt.profit_factor, 3))),
        "max_drawdown":      round(rpt.max_drawdown * 100, 2),
        "avg_rr":            round(rpt.avg_rr, 3),
        "equity_curve":      [round(v, 6) for v in curve.tolist()],
        "regime_breakdown":  rpt.regime_breakdown,
        "gross_pnl_pct_sum": round(gross_total, 6),
        "cost_pct_sum":      round(cost_total, 6),
        "net_pnl_pct_sum":   round(net_total, 6),
    }
    for k, (lbl, lwr, swr) in enumerate(fwd_win_rates):
        result[f"fwd{k+1}_label"]          = lbl
        result[f"fwd{k+1}_long_win_rate"]  = lwr
        result[f"fwd{k+1}_short_win_rate"] = swr
    if emit_events and ledger is not None:
        result["events"] = ledger.events_as_dicts()
    return result


def run_mtf_backtest(
    underlying: str,
    candles_15m: List[Candle],
    candles_1h:  List[Candle],
    candles_4h:  List[Candle],
    c_1d:        Optional[List[Candle]] = None,
    profiles:    Optional[List[str]]    = None,
    score_min:   float = 0.0,
    *,
    leverage: float = 1.0,
    oi: Optional[float] = None,
    funding_8h_pct: float = 0.0,
    option_spread_pct: Optional[float] = None,
    apply_slippage: bool = True,
    emit_events: bool = False,
    exit_atr_tf: Optional[Literal["signal", "regime"]] = None,
    payoff_mode: Optional[Literal["fixed_2r", "chandelier_trail"]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Run all (or selected) TF profiles and return a comparison dict.
    Keys: profile key -> result dict (metrics + equity_curve).

    New cost parameters (Phase 1) thread through to `_replay_profile`:
      - leverage, oi      : drive tiered slippage model
      - funding_8h_pct    : signed funding rate; cost = direction * rate * hold/8
      - option_spread_pct : optional round-trip bid/ask half-spread cost (None=ignore)
      - apply_slippage    : disable to inspect zero-slippage variants
      - emit_events       : opt-in research event ledger (default off → unchanged shape)
      - exit_atr_tf       : Issue 6 — when set, overrides the per-profile default
                            ("regime" preserves legacy; "signal" tightens stops to
                            the entry timeframe).
      - payoff_mode       : Issue 7 — when set, overrides the per-profile default
                            ("fixed_2r" preserves legacy 2R/-1R; "chandelier_trail"
                            takes 50% at +1R, breakeven, then trails the remainder).
    """
    _candle_map: Dict[str, Tuple[List[Candle], List[Candle]]] = {
        "scalping_15m": (candles_15m, candles_1h),
        "intraday_1h":  (candles_1h,  candles_4h),
        "intraday_4h":  (candles_4h,  c_1d or []),
    }
    run_keys = profiles if profiles is not None else list(PROFILES.keys())
    results: Dict[str, Dict[str, Any]] = {}

    for key in run_keys:
        if key not in PROFILES:
            continue
        profile = PROFILES[key]
        # Apply caller-side overrides without mutating the module-level singleton.
        overrides: Dict[str, Any] = {}
        if exit_atr_tf is not None:
            overrides["exit_atr_tf"] = exit_atr_tf
        if payoff_mode is not None:
            overrides["payoff_mode"] = payoff_mode
        if overrides:
            from dataclasses import replace as _dc_replace
            profile = _dc_replace(profile, **overrides)
        sig_candles, reg_candles = _candle_map.get(key, ([], []))
        results[key] = _replay_profile(
            profile, sig_candles, reg_candles,
            score_min=score_min, underlying=underlying,
            leverage=leverage, oi=oi,
            funding_8h_pct=funding_8h_pct,
            option_spread_pct=option_spread_pct,
            apply_slippage=apply_slippage,
            emit_events=emit_events,
        )

    return results
