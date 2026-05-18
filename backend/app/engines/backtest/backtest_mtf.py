"""
Multi-timeframe backtest engine.
Bar-by-bar strategy replay for scalping (15M/1H) and intraday (1H/4H, 4H/1D) profiles.
Pure functions — no I/O.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
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
    Exit:  trend reversal | ATR-based +2R/-1R | hold_bars elapsed.

    Fills land on the OPEN of the bar following the signal bar (no signal-bar
    close execution). Slippage, fees, perpetual funding (by actual hold time),
    and optional option half-spread are attributed via `costs.compute_trade_costs`.
    Trades record both gross and net PnL with full cost breakdown.

    When `emit_events=True`, the result includes an `events` list containing
    candidate/skip/entry/exit records in chronological order. Default output
    shape is unchanged.
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
    trades: List[Dict[str, Any]] = []
    in_trade      = False
    entry_bar     = 0           # index of the signal bar that triggered entry
    entry_fill_bar = 0          # index of the bar where entry actually filled
    entry_dir     = 0
    entry_price   = 0.0         # clean fill price (next bar open)
    entry_atr     = 0.0
    entry_regime  = "unknown"
    entry_ts_ms   = 0

    for i in range(profile.min_signal_bars, n_signal - 1):
        ts = candles_signal[i].timestamp_ms

        # Regime slice: bars whose close time is <= current signal bar ts
        c_regime = [c for c in candles_regime if c.timestamp_ms + regime_bar_ms <= ts]
        if len(c_regime) < profile.min_regime_bars:
            continue
        c_signal = candles_signal[max(0, i - 200): i + 1]

        regime = compute_regime(c_regime)
        signal = compute_signal(c_signal, st_configs=profile.st_configs)
        setup  = evaluate_setup(regime, signal)

        # ── Exit logic ─────────────────────────────────────────────────────────
        just_exited = False
        if in_trade:
            cur_close = candles_signal[i].close
            held = i - entry_bar

            exit_now = held >= profile.hold_bars
            if not exit_now and entry_atr > 0 and entry_price > 0:
                gain_abs = entry_dir * (cur_close - entry_price)
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
                    breakdown = compute_trade_costs(
                        direction=entry_dir,
                        entry_price=entry_price,
                        exit_price=exit_px,
                        leverage=leverage,
                        oi=oi,
                        fee_rt_pct=fee_rt_pct,
                        hold_hours=hold_hours,
                        funding_8h_pct=funding_8h_pct,
                        option_spread_pct=option_spread_pct,
                        apply_slippage=apply_slippage,
                        forced_end=False,
                    )
                    trade = {
                        "pnl_pct":         breakdown.net_pnl_pct,
                        "gross_pnl_pct":   breakdown.gross_pnl_pct,
                        "net_pnl_pct":     breakdown.net_pnl_pct,
                        "cost_pct":        breakdown.total_cost_pct,
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
                # ATR from recent regime bars for R-multiple exits
                h_arr = np.array([c.high  for c in c_regime[-20:]], dtype=np.float64)
                l_arr = np.array([c.low   for c in c_regime[-20:]], dtype=np.float64)
                c_arr = np.array([c.close for c in c_regime[-20:]], dtype=np.float64)
                atr_arr  = compute_atr(h_arr, l_arr, c_arr, 14)
                v = float(atr_arr[-1]) if len(atr_arr) > 0 and not np.isnan(atr_arr[-1]) else 0.0
                entry_atr = v if v > 0 else entry_price * 0.02
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
        breakdown = compute_trade_costs(
            direction=entry_dir,
            entry_price=entry_price,
            exit_price=exit_px,
            leverage=leverage,
            oi=oi,
            fee_rt_pct=fee_rt_pct,
            hold_hours=hold_hours,
            funding_8h_pct=funding_8h_pct,
            option_spread_pct=option_spread_pct,
            apply_slippage=apply_slippage,
            forced_end=True,
        )
        trade = {
            "pnl_pct":         breakdown.net_pnl_pct,
            "gross_pnl_pct":   breakdown.gross_pnl_pct,
            "net_pnl_pct":     breakdown.net_pnl_pct,
            "cost_pct":        breakdown.total_cost_pct,
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
            "asset":           underlying,
            "profile":         profile.label,
            "track":           "directional",
        }
        trades.append(trade)
        if ledger is not None:
            ledger.record_exit(trade)
            ledger.record_trade(trade)

    # ── Forward-return win rates per horizon (arrow-based) ────────────────────
    # Pass 1: compute signals and regime slices once per bar
    _bar_signals: Dict[int, Any] = {}
    for j in range(profile.min_signal_bars, n_signal):
        ts_j    = candles_signal[j].timestamp_ms
        c_reg_j = [c for c in candles_regime
                   if c.timestamp_ms + regime_bar_ms <= ts_j]
        if len(c_reg_j) < profile.min_regime_bars:
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
