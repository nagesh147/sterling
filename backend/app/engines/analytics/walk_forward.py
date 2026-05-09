"""
Rolling walk-forward backtesting engine.
Pure functions, no I/O. Results persisted by API layer.
"""
import numpy as np
from dataclasses import dataclass, field
from app.engines.analytics.performance import PerformanceReport, full_report


@dataclass
class WalkForwardConfig:
    train_bars: int = 180
    test_bars:  int = 60
    step_bars:  int = 30
    score_thresholds_to_test: list = field(default_factory=lambda: [65, 70, 75, 80, 85])
    underlying: str = "BTC"


@dataclass
class WalkForwardWindow:
    window_idx:      int
    train_start:     int
    test_start:      int
    test_end:        int
    report:          PerformanceReport
    best_threshold:  float
    equity_curve:    list


@dataclass
class WalkForwardResult:
    windows:               list
    aggregate_report:      PerformanceReport
    recommended_threshold: float
    regime_sharpes:        dict
    oos_equity_curve:      list


def _synthetic_trades(candles: list, score_threshold: float, hold_bars: int = 4) -> list:
    """
    Simulate trades from a candle list using a simple momentum signal.
    Returns list of {pnl_pct, regime, entry_bar, exit_bar}.
    Signal: if close[i] > close[i-1] * 1.001 and hypothetical_score >= threshold → long.
    Simplified stand-in for full engine replay.
    """
    trades = []
    if len(candles) < hold_bars + 2:
        return trades
    for i in range(1, len(candles) - hold_bars):
        c = candles[i]
        prev = candles[i - 1]
        # Simple proxy signal: momentum + threshold check
        close = c.get('close', 1.0)
        prev_close = prev.get('close', 1.0)
        if prev_close <= 0:
            continue
        momentum_score = abs((close - prev_close) / prev_close) * 10000  # bps
        if momentum_score < score_threshold:
            continue
        direction = 1 if close > prev_close else -1
        exit_close = candles[i + hold_bars].get('close', close)
        pnl_pct = direction * (exit_close - close) / close
        trades.append({
            'pnl_pct': pnl_pct,
            'regime': c.get('regime', 'unknown'),
            'entry_bar': i,
            'exit_bar': i + hold_bars,
        })
    return trades


def _equity_from_trades(trades: list) -> np.ndarray:
    curve = [1.0]
    for t in trades:
        curve.append(curve[-1] * (1 + t['pnl_pct']))
    return np.array(curve) if len(curve) > 1 else np.array([1.0, 1.0])


def run(candles: list, config: WalkForwardConfig) -> WalkForwardResult:
    """
    candles: list of dict with keys close, regime (4H bars).
    Slides train/test windows forward by step_bars.
    Threshold selection uses train window only (no look-ahead).
    """
    windows = []
    oos_trades_all = []
    total = len(candles)

    idx = 0
    win_idx = 0
    while idx + config.train_bars + config.test_bars <= total:
        train_end = idx + config.train_bars
        test_end  = train_end + config.test_bars

        train_candles = candles[idx:train_end]
        test_candles  = candles[train_end:test_end]

        # Select threshold on TRAIN data only
        best_thr = config.score_thresholds_to_test[0]
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
                best_thr = thr

        # Evaluate on TEST data with best_thr
        test_trades = _synthetic_trades(test_candles, best_thr)
        oos_trades_all.extend(test_trades)

        if test_trades:
            ec = _equity_from_trades(test_trades)
            rpt = full_report(ec, test_trades)
        else:
            from app.engines.analytics.performance import PerformanceReport
            rpt = PerformanceReport(0,0,0,0,0,0,0,0,{})
            ec = [1.0]

        windows.append(WalkForwardWindow(
            window_idx=win_idx,
            train_start=idx,
            test_start=train_end,
            test_end=test_end,
            report=rpt,
            best_threshold=best_thr,
            equity_curve=list(_equity_from_trades(test_trades)) if test_trades else [1.0],
        ))

        idx += config.step_bars
        win_idx += 1

    # Aggregate
    oos_ec = _equity_from_trades(oos_trades_all) if oos_trades_all else np.array([1.0, 1.0])
    agg = full_report(oos_ec, oos_trades_all) if oos_trades_all else PerformanceReport(0,0,0,0,0,0,0,0,{})

    thresholds = [w.best_threshold for w in windows]
    rec_thr = float(np.median(thresholds)) if thresholds else config.score_thresholds_to_test[0]

    regime_sharpes = {}
    if agg.regime_breakdown:
        for regime, stats in agg.regime_breakdown.items():
            regime_sharpes[regime] = stats.get('sharpe_proxy', 0.0)

    return WalkForwardResult(
        windows=windows,
        aggregate_report=agg,
        recommended_threshold=rec_thr,
        regime_sharpes=regime_sharpes,
        oos_equity_curve=list(oos_ec),
    )
