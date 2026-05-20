"""
Rolling walk-forward backtesting engine.
Pure functions, no I/O. Results persisted by API layer.

run()      — legacy bps-proxy (backward compat for existing tests)
run_real() — real engine replay using actual regime/signal/setup pipeline
"""
import numpy as np
import bisect
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from app.engines.analytics.performance import (
    PerformanceReport, full_report, deflated_sharpe,
)

_FEE_RT_PCT = 0.001   # 0.10% round-trip (taker on both legs)
_MIN_1H     = 30
_MIN_4H     = 55
_4H_MS      = 4 * 3_600_000

# Issue 9 — deflated-Sharpe p-value threshold above which a window's selected
# threshold is treated as a real edge. Below this, the window is "no_edge".
_DEFLATED_P_GATE = 0.95


@dataclass
class WalkForwardConfig:
    train_bars: int = 180
    test_bars:  int = 60
    step_bars:  int = 30
    score_thresholds_to_test: list = field(default_factory=lambda: [0, 3, 5, 8, 10, 12, 15])
    underlying: str = "BTC"
    # Tier S #4 — deflated-Sharpe gate is now ALWAYS-ON by default. Threshold
    # selection requires deflated_sharpe ≥ deflated_p_gate (default 0.95) on
    # the train window. Windows that don't clear the gate are flagged
    # `no_edge=True` and contribute zero trades to the OOS aggregate.
    # Legacy callers that want the pre-Tier-S behaviour must set this to False
    # explicitly.
    require_deflated_significance: bool = True
    deflated_p_gate: float = _DEFLATED_P_GATE


@dataclass
class WalkForwardWindow:
    window_idx:      int
    train_start:     int
    test_start:      int
    test_end:        int
    report:          PerformanceReport
    best_threshold:  Optional[float]
    equity_curve:    list
    # Issue 9 — additive fields for the deflated-Sharpe gate.
    train_sharpe:    Optional[float] = None
    deflated_p:      Optional[float] = None
    no_edge:         bool = False


@dataclass
class WalkForwardResult:
    windows:               list
    aggregate_report:      PerformanceReport
    recommended_threshold: Optional[float]
    regime_sharpes:        dict
    oos_equity_curve:      list
    # Issue 9 — count of windows that cleared the deflated_sharpe gate.
    windows_with_edge:     int = 0
    deflated_p_per_window: list = field(default_factory=list)


# ── Legacy proxy (kept for backward-compat tests) ──────────────────────────

def _synthetic_trades(candles: list, score_threshold: float, hold_bars: int = 4) -> list:
    """
    Bps-momentum proxy. Kept for backward compatibility with existing tests.
    score_threshold is treated as bps (not signal_score 0-20).
    Use _engine_replay_trades for real strategy validation.
    """
    trades = []
    if len(candles) < hold_bars + 2:
        return trades
    for i in range(1, len(candles) - hold_bars):
        c    = candles[i]
        prev = candles[i - 1]
        close      = c.get('close', 1.0)
        prev_close = prev.get('close', 1.0)
        if prev_close <= 0:
            continue
        momentum_score = abs((close - prev_close) / prev_close) * 10000
        if momentum_score < score_threshold:
            continue
        direction  = 1 if close > prev_close else -1
        exit_close = candles[i + hold_bars].get('close', close)
        pnl_pct    = direction * (exit_close - close) / close
        trades.append({
            'pnl_pct': pnl_pct,
            'regime':  c.get('regime', 'unknown'),
            'entry_bar': i,
            'exit_bar':  i + hold_bars,
        })
    return trades


def _equity_from_trades(trades: list) -> np.ndarray:
    curve = [1.0]
    for t in trades:
        curve.append(curve[-1] * (1 + t['pnl_pct']))
    return np.array(curve) if len(curve) > 1 else np.array([1.0, 1.0])


def run(candles: list, config: WalkForwardConfig) -> WalkForwardResult:
    """Legacy walk-forward using bps-momentum proxy. Use run_real() instead."""
    windows        = []
    oos_trades_all = []
    total          = len(candles)
    idx = win_idx  = 0

    while idx + config.train_bars + config.test_bars <= total:
        train_end     = idx + config.train_bars
        test_end      = train_end + config.test_bars
        train_candles = candles[idx:train_end]
        test_candles  = candles[train_end:test_end]

        best_thr    = config.score_thresholds_to_test[0]
        best_sharpe = -999.0
        for thr in config.score_thresholds_to_test:
            tr_trades = _synthetic_trades(train_candles, thr)
            if not tr_trades:
                continue
            ec = _equity_from_trades(tr_trades)
            from app.engines.analytics.performance import sharpe as _sharpe
            s = _sharpe(ec)
            if s > best_sharpe:
                best_sharpe = s
                best_thr    = thr

        test_trades = _synthetic_trades(test_candles, best_thr)
        oos_trades_all.extend(test_trades)

        if test_trades:
            ec  = _equity_from_trades(test_trades)
            rpt = full_report(ec, test_trades)
        else:
            rpt = PerformanceReport(0,0,0,0,0,0,0,0,{})
            ec  = [1.0]

        windows.append(WalkForwardWindow(
            window_idx=win_idx,
            train_start=idx, test_start=train_end, test_end=test_end,
            report=rpt, best_threshold=best_thr,
            equity_curve=list(_equity_from_trades(test_trades)) if test_trades else [1.0],
        ))
        idx     += config.step_bars
        win_idx += 1

    oos_ec = _equity_from_trades(oos_trades_all) if oos_trades_all else np.array([1.0, 1.0])
    agg    = full_report(oos_ec, oos_trades_all) if oos_trades_all else PerformanceReport(0,0,0,0,0,0,0,0,{})
    thresholds = [w.best_threshold for w in windows]
    rec_thr    = float(np.median(thresholds)) if thresholds else config.score_thresholds_to_test[0]
    regime_sharpes = {}
    if agg.regime_breakdown:
        for regime, stats in agg.regime_breakdown.items():
            regime_sharpes[regime] = stats.get('sharpe_proxy', 0.0)

    return WalkForwardResult(
        windows=windows, aggregate_report=agg,
        recommended_threshold=rec_thr, regime_sharpes=regime_sharpes,
        oos_equity_curve=list(oos_ec),
    )


# ── Real engine replay ──────────────────────────────────────────────────────

def _engine_replay_trades(
    candles_1h: list,
    candles_4h: list,
    score_min:   float = 0.0,
    fee_rt_pct:  float = _FEE_RT_PCT,
    hold_bars:   int   = 8,
) -> list:
    """
    Bar-by-bar replay using the real regime/signal/setup engines.
    Entry: CONFIRMED_SETUP_ACTIVE + signal_score >= score_min.
    Exit:  signal thesis reversal | hold_bars elapsed | +2R gain | -1R loss.
    fee_rt_pct applied per trade (round-trip).
    Returns list of {pnl_pct, regime, entry_bar, exit_bar, direction}.
    """
    from app.engines.directional.regime_engine import compute_regime
    from app.engines.directional.signal_engine import compute_signal
    from app.engines.directional.setup_engine  import evaluate_setup
    from app.schemas.directional import TradeState
    from app.engines.indicators.atr import compute_atr

    trades        = []
    in_trade      = False
    entry_bar = entry_direction = 0
    entry_close   = entry_atr = 0.0
    entry_regime  = "unknown"

    c4h_ts = [c.timestamp_ms for c in candles_4h]
    for i in range(_MIN_1H, len(candles_1h) - 1):
        ts  = candles_1h[i].timestamp_ms
        idx_4h = bisect.bisect_right(c4h_ts, ts - _4H_MS)
        c4h = candles_4h[:idx_4h]
        if len(c4h) < _MIN_4H:
            continue
        c1h = candles_1h[max(0, i - 200): i + 1]

        regime = compute_regime(c4h)
        signal = compute_signal(c1h)
        setup  = evaluate_setup(regime, signal)

        if in_trade:
            cur  = candles_1h[i].close
            held = i - entry_bar
            raw  = entry_direction * (cur - entry_close) / entry_close if entry_close > 0 else 0.0

            exit_now = held >= hold_bars
            if not exit_now and entry_atr > 0 and entry_close > 0:
                gain_abs = entry_direction * (cur - entry_close)
                exit_now = gain_abs >= 2 * entry_atr or gain_abs <= -entry_atr
            if not exit_now:
                if entry_direction == 1 and signal.trend == -1:
                    exit_now = True
                elif entry_direction == -1 and signal.trend == 1:
                    exit_now = True

            if exit_now:
                trades.append({
                    "pnl_pct":   raw - fee_rt_pct,
                    "regime":    entry_regime,
                    "entry_bar": entry_bar,
                    "exit_bar":  i,
                    "direction": "long" if entry_direction == 1 else "short",
                })
                in_trade = False

        if not in_trade:
            sig_score = float(getattr(signal, "signal_score", 0.0) or 0.0)
            if (
                setup.state == TradeState.CONFIRMED_SETUP_ACTIVE
                and sig_score >= score_min
                and signal.trend != 0
            ):
                in_trade        = True
                entry_bar       = i
                entry_direction = signal.trend
                entry_close     = candles_1h[i].close
                entry_regime    = regime.macro_regime.value
                h4 = np.array([c.high  for c in c4h[-20:]], dtype=np.float64)
                l4 = np.array([c.low   for c in c4h[-20:]], dtype=np.float64)
                c4 = np.array([c.close for c in c4h[-20:]], dtype=np.float64)
                atr_arr   = compute_atr(h4, l4, c4, 14)
                v         = float(atr_arr[-1]) if len(atr_arr) > 0 and not np.isnan(atr_arr[-1]) else 0.0
                entry_atr = v if v > 0 else entry_close * 0.02

    if in_trade:
        i   = len(candles_1h) - 1
        cur = candles_1h[i].close
        raw = entry_direction * (cur - entry_close) / entry_close if entry_close > 0 else 0.0
        trades.append({
            "pnl_pct":   raw - fee_rt_pct,
            "regime":    entry_regime,
            "entry_bar": entry_bar,
            "exit_bar":  i,
            "direction": "long" if entry_direction == 1 else "short",
        })
    return trades


def run_real(
    candles_1h: list,
    candles_4h: list,
    config:     WalkForwardConfig,
    fee_rt_pct: float = _FEE_RT_PCT,
) -> WalkForwardResult:
    """
    Walk-forward using real engine replay.
    score_thresholds_to_test are signal_score values (0–20 scale).
    Threshold selected on train window only; OOS equity evaluated on test window.

    Issue 9: when `config.require_deflated_significance` is True, the per-window
    train Sharpe must clear a deflated-Sharpe probability ≥ `config.deflated_p_gate`
    given the number of thresholds searched and the number of train trades.
    Windows that don't clear are flagged `no_edge=True` and their recommended
    threshold is None — they do NOT contribute trades to the OOS aggregate.
    """
    from app.engines.analytics.performance import sharpe as _sharpe

    windows        = []
    oos_trades_all = []
    total          = len(candles_1h)
    idx = win_idx  = 0
    step           = max(config.step_bars, 1)
    n_thresholds   = max(1, len(config.score_thresholds_to_test))

    while idx + config.train_bars + config.test_bars <= total:
        train_end = idx + config.train_bars
        test_end  = min(train_end + config.test_bars, total)

        tr_1h = candles_1h[idx:train_end]
        ts_1h = candles_1h[train_end:test_end]

        c4h_ts = [c.timestamp_ms for c in candles_4h]
        tr_cutoff = tr_1h[-1].timestamp_ms if tr_1h else 0
        ts_cutoff = ts_1h[-1].timestamp_ms if ts_1h else 0
        idx_tr = bisect.bisect_right(c4h_ts, tr_cutoff - _4H_MS)
        tr_4h = candles_4h[:idx_tr]
        idx_ts = bisect.bisect_right(c4h_ts, ts_cutoff - _4H_MS)
        ts_4h = candles_4h[:idx_ts]

        best_thr        = config.score_thresholds_to_test[0]
        best_sharpe     = -999.0
        best_train_n    = 0
        for thr in config.score_thresholds_to_test:
            tr_trades = _engine_replay_trades(tr_1h, tr_4h, score_min=thr, fee_rt_pct=fee_rt_pct)
            if not tr_trades:
                continue
            s = _sharpe(_equity_from_trades(tr_trades))
            if s > best_sharpe:
                best_sharpe = s
                best_thr    = thr
                best_train_n = len(tr_trades)

        # Issue 9 — deflated-Sharpe gate on the train-window winner.
        deflated_p = None
        if best_train_n >= 2 and best_sharpe > -999.0:
            deflated_p = deflated_sharpe(
                observed_sharpe=best_sharpe,
                n_trials=n_thresholds,
                n_observations=best_train_n,
            )
        gate = config.deflated_p_gate
        no_edge = (
            config.require_deflated_significance
            and (deflated_p is None or deflated_p < gate)
        )

        if no_edge:
            test_trades = []
        else:
            test_trades = _engine_replay_trades(
                ts_1h, ts_4h, score_min=best_thr, fee_rt_pct=fee_rt_pct,
            )
        oos_trades_all.extend(test_trades)

        if test_trades:
            ec  = _equity_from_trades(test_trades)
            rpt = full_report(ec, test_trades)
        else:
            rpt = PerformanceReport(0,0,0,0,0,0,0,0,{})
            ec  = np.array([1.0])

        windows.append(WalkForwardWindow(
            window_idx=win_idx,
            train_start=idx, test_start=train_end, test_end=test_end,
            report=rpt,
            best_threshold=(None if no_edge else best_thr),
            equity_curve=list(ec),
            train_sharpe=(None if best_sharpe <= -999.0 else float(best_sharpe)),
            deflated_p=(None if deflated_p is None else float(deflated_p)),
            no_edge=no_edge,
        ))
        idx     += step
        win_idx += 1

    oos_ec = _equity_from_trades(oos_trades_all) if oos_trades_all else np.array([1.0, 1.0])
    agg    = full_report(oos_ec, oos_trades_all) if oos_trades_all else PerformanceReport(0,0,0,0,0,0,0,0,{})
    thr_arr = [w.best_threshold for w in windows if w.best_threshold is not None]
    if thr_arr:
        rec_thr = float(np.median(thr_arr))
    elif config.require_deflated_significance:
        rec_thr = None  # no windows survived the gate
    else:
        rec_thr = config.score_thresholds_to_test[0]

    regime_sharpes = {}
    if agg.regime_breakdown:
        for reg, stats in agg.regime_breakdown.items():
            regime_sharpes[reg] = stats.get("sharpe_proxy", 0.0)

    windows_with_edge = sum(1 for w in windows if not w.no_edge and w.best_threshold is not None)
    deflated_per_window = [w.deflated_p for w in windows]

    return WalkForwardResult(
        windows=windows, aggregate_report=agg,
        recommended_threshold=rec_thr, regime_sharpes=regime_sharpes,
        oos_equity_curve=list(oos_ec),
        windows_with_edge=windows_with_edge,
        deflated_p_per_window=deflated_per_window,
    )
