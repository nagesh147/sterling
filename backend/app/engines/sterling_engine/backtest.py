"""Honest bar-by-bar replay for the scalping strategies.

The previous `/scalping/backtest` path did not actually replay history: it
scanned the *latest* bar once per strategy and reported the *planned* R:R as
the outcome (i.e. it assumed every trade hit its take-profit). That produces a
~100% win rate and zero drawdown — false confidence, the classic backtesting
pitfall.

This module replays each enabled strategy bar-by-bar with:

  * real fills — entry at the signal's planned level, exit walked forward bar
    by bar against the SL/TP (whichever the price path hits first), or a time
    stop at `maxh` bars;
  * real costs — taker fee + tiered slippage + perpetual funding by actual
    hold time, via `engines.backtest.costs.compute_trade_costs`, folded back
    into the per-trade R so PnL is reported NET of costs;
  * one trade at a time per strategy — mirrors the live idempotency guard, so
    overlapping signals don't inflate the trade count.

On top of the replay it reports the validation signals a single run needs to
be trustworthy rather than just "looks good on paper":

  * sample-size adequacy — <30 trades is unreliable, ~100 is the working
    floor, ~500+ is robust (see `classify_sample_size`);
  * regime coverage — whether the lookback window spanned both a bull and a
    bear leg, plus a per-regime trade breakdown (does the edge hold in both?);
  * an in-sample / out-of-sample split — the same 70/30 OOS discipline the
    optimizer uses, surfaced for a single symbol so one run shows whether the
    edge generalises or is curve-fit to the window.

Pure functions over candle lists. No I/O. The API layer loads candles and
calls `run_scalping_backtest()`.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from app.engines.sterling_engine.config import ScalpingProfile
from app.engines.sterling_engine.levels import detect_levels
from app.engines.sterling_engine.price_action import evaluate_price_action
from app.engines.sterling_engine.smc import evaluate_smc
from app.engines.sterling_engine.ma_crossover import evaluate_ma_crossover
from app.engines.sterling_engine.mean_reversion import evaluate_mean_reversion
from app.engines.sterling_engine.breakout import evaluate_breakout
from app.engines.sterling_engine.scanner import _macro_regime, _is_counter_trend
# Reuse the optimizer's validated replay windows / cadence so the single-symbol
# backtest and the OOS sweep observe the strategy under identical conditions.
from app.engines.sterling_engine.optimizer import W_EXEC, W_MACRO, EXEC_STEP, EXEC_MAXH, OOS_FRAC
from app.engines.backtest.costs import compute_trade_costs

# Default round-trip taker fee (matches engines.backtest.costs futures default).
FEE_RT_PCT = 0.001

def _resample_15m_to_1h(c_exec: list) -> list:
    """Aggregate a 15m candle list into 1h bars (open=first, high=max, low=min,
    close=last, volume=sum), bucketed by the wall-clock hour. ma_crossover gates
    entries on 1h structure (`check_1h_structure`); the live scanner passes a real
    1h series, so the replay must too — without it the strategy can never arm."""
    from app.schemas.market import Candle
    H = 3_600_000
    buckets: Dict[int, list] = {}
    order: list = []
    for c in c_exec:
        b = (int(c.timestamp_ms) // H) * H
        if b not in buckets:
            buckets[b] = []
            order.append(b)
        buckets[b].append(c)
    out = []
    for b in order:
        grp = buckets[b]
        out.append(Candle(
            timestamp_ms=b, open=grp[0].open,
            high=max(x.high for x in grp), low=min(x.low for x in grp),
            close=grp[-1].close, volume=sum(x.volume for x in grp),
        ))
    return out


def _ma_crossover_5arg(sym, c_macro, c_exec, levels, cfg):
    """Uniform 5-arg replay adapter for evaluate_ma_crossover, which uniquely
    needs a `candles_1h` series. Derive it from the 15m exec window so the
    backtest exercises the SAME 1h-gated logic the live scanner trades."""
    c_1h = _resample_15m_to_1h(c_exec)
    return evaluate_ma_crossover(sym, c_macro, c_exec, c_1h, levels, cfg)


# Strategy id -> evaluator. All share the (underlying, c_macro, c_exec, levels,
# cfg) signature and evaluate "as of" the last bar of the passed exec slice, so
# slicing the candle arrays gives a no-lookahead point-in-time signal.
EVALUATORS: Dict[str, Callable] = {
    "price_action":   evaluate_price_action,
    "smc":            evaluate_smc,
    "ma_crossover":   _ma_crossover_5arg,
    "mean_reversion": evaluate_mean_reversion,
    "breakout":       evaluate_breakout,
}

# Sample-size tiers. Thresholds reflect the common trader rule of thumb: under
# ~100 trades a backtest is "pretty much useless", 100-200 is a starting range,
# 500+ is where randomness is meaningfully averaged out.
_SAMPLE_TIERS: List[Tuple[int, str, str]] = [
    (500, "robust",     "500+ trades — randomness is well averaged out."),
    (100, "adequate",   "100-499 trades — a usable read; 500+ is firmer."),
    (30,  "thin",       "30-99 trades — directional only; the working floor is ~100."),
    (1,   "unreliable", "Under 30 trades — too few to trust; treat as noise."),
    (0,   "no_trades",  "No trades produced on this window."),
]

# Minimum OOS trades before the in-sample/out-of-sample verdict is trusted.
MIN_OOS_TRADES = 15


@dataclass
class TradeRec:
    strategy:     str
    direction:    str          # "long" | "short"
    entry_bar:    int          # exec-bar index of the signal (drives the IS/OOS split)
    entry_ts:     int
    exit_ts:      int
    entry_price:  float
    exit_price:   float
    bars_held:    int
    gross_pnl_r:  float        # R before costs
    cost_r:       float        # fee + slippage + funding, expressed in R
    pnl_r:        float        # NET R (gross - cost) — the honest number
    exit_reason:  str          # "take_profit" | "stop_loss" | "time"
    regime:       str          # macro regime at entry: bull | bear | chop


@dataclass
class BacktestOutput:
    trades:            List[TradeRec]
    bars_evaluated:    int
    total_trades:      int
    win_rate:          float
    expectancy_r:      float
    profit_factor:     Optional[float]
    net_return_pct:    float
    max_drawdown_pct:  float
    avg_cost_r:        float
    equity_curve:      List[float]
    sample_quality:    dict
    regime_coverage:   dict
    oos:               dict


# ── sample-size adequacy ────────────────────────────────────────────────────


def classify_sample_size(n: int) -> dict:
    """Map a trade count to a {label, note, min_reliable, adequate} verdict."""
    for floor, label, note in _SAMPLE_TIERS:
        if n >= floor:
            return {
                "label": label,
                "note": note,
                "min_reliable": 100,
                "adequate": n >= 100,
            }
    # Unreachable (the 0 tier matches everything) — defensive.
    return {"label": "no_trades", "note": _SAMPLE_TIERS[-1][2],
            "min_reliable": 100, "adequate": False}


# ── exit simulation ─────────────────────────────────────────────────────────


def _exit_fixed(
    cE: list, i: int, is_long: bool, entry: float, sl: float, tp: float, maxh: int,
) -> Tuple[float, int, str]:
    """Walk forward from bar i+1 until SL or TP is touched (SL checked first to
    stay conservative on bars that straddle both), else exit at the time stop.

    Returns (exit_price, exit_bar_index, reason).
    """
    for k in range(i + 1, min(i + 1 + maxh, len(cE))):
        hi, lo = cE[k].high, cE[k].low
        if is_long:
            if lo <= sl:
                return sl, k, "stop_loss"
            if hi >= tp:
                return tp, k, "take_profit"
        else:
            if hi >= sl:
                return sl, k, "stop_loss"
            if lo <= tp:
                return tp, k, "take_profit"
    j = min(i + maxh, len(cE) - 1)
    return cE[j].close, j, "time"


def _closes(candles: list) -> np.ndarray:
    return np.array([c.close for c in candles], dtype=np.float64)


# ── per-strategy replay ─────────────────────────────────────────────────────


def _replay_strategy(
    sym: str,
    cM: list,
    cE: list,
    ts_macro: list,
    cfg: ScalpingProfile,
    evaluator: Callable,
    strategy: str,
    step: int,
    maxh: int,
    fee_rt_pct: float,
) -> List[TradeRec]:
    """Replay one strategy over the exec series. One open trade at a time
    (cooldown until the prior exit) — mirrors the live idempotency guard."""
    out: List[TradeRec] = []
    cooldown, cj, levels = -1, -1, []
    n = len(cE)
    i = W_EXEC
    while i < n - 1:
        if i <= cooldown:
            i += step
            continue
        j = bisect.bisect_right(ts_macro, cE[i].timestamp_ms)
        if j < W_MACRO:
            i += step
            continue
        macro_window = cM[j - W_MACRO:j]
        if j != cj:
            cw = macro_window
            levels = detect_levels(
                np.array([c.high for c in cw]), np.array([c.low for c in cw]),
                _closes(cw), np.array([c.timestamp_ms for c in cw], dtype=np.int64), cfg)
            cj = j
        sig = evaluator(sym, macro_window, cE[i - W_EXEC:i + 1], levels, cfg)
        if not (sig.entry_ok and sig.entry and sig.stop_loss and sig.take_profit):
            i += step
            continue

        # Macro-trend regime at entry (also used for the macro filter + breakdown).
        base = cM[max(0, j - cfg.macro_trend_ema_slow - 5):j]
        regime = _macro_regime(_closes(base), cfg)
        if cfg.macro_trend_filter and regime in ("bull", "bear") \
                and _is_counter_trend(sig.direction, regime):
            i += step
            continue

        is_long = sig.direction == "long"
        risk_dist = abs(sig.entry - sig.stop_loss)
        if risk_dist <= 0:
            i += step
            continue

        ex, ck, reason = _exit_fixed(cE, i, is_long, sig.entry, sig.stop_loss,
                                     sig.take_profit, maxh)
        gross_r = (1 if is_long else -1) * (ex - sig.entry) / risk_dist
        entry_ts = int(cE[i].timestamp_ms)
        exit_ts = int(cE[ck].timestamp_ms)
        hold_hours = max(0.0, (exit_ts - entry_ts) / 3_600_000.0)

        bd = compute_trade_costs(
            direction=1 if is_long else -1,
            entry_price=sig.entry,
            exit_price=ex,
            structure_type="futures",
            leverage=1.0,
            fee_rt_pct=fee_rt_pct,
            hold_hours=hold_hours,
            apply_slippage=True,
        )
        # total_cost_pct is a fraction of notional (~entry price); convert to R.
        cost_r = bd.total_cost_pct * sig.entry / risk_dist
        net_r = gross_r - cost_r

        out.append(TradeRec(
            strategy=strategy, direction=sig.direction,
            entry_bar=i, entry_ts=entry_ts, exit_ts=exit_ts,
            entry_price=float(sig.entry), exit_price=float(ex),
            bars_held=ck - i,
            gross_pnl_r=round(gross_r, 4), cost_r=round(cost_r, 4),
            pnl_r=round(net_r, 4), exit_reason=reason, regime=regime,
        ))
        cooldown = ck
        i += step
    return out


# ── window-level regime coverage ────────────────────────────────────────────


def _window_regime_coverage(cM: list, cfg: ScalpingProfile) -> dict:
    """Classify each macro bar's regime over a rolling EMA window and report the
    bull/bear/chop split + whether the window spanned BOTH a bull and a bear leg
    (the 'cover one bull and one bear cycle' robustness rule)."""
    slow = cfg.macro_trend_ema_slow
    n = len(cM)
    if n <= slow:
        return {"covers_bull_and_bear": False,
                "bull_pct": 0.0, "bear_pct": 0.0, "chop_pct": 0.0}
    closes = _closes(cM)
    counts = {"bull": 0, "bear": 0, "chop": 0}
    for k in range(slow, n):
        counts[_macro_regime(closes[max(0, k - slow - 5):k + 1], cfg)] += 1
    total = sum(counts.values()) or 1
    return {
        "covers_bull_and_bear": counts["bull"] > 0 and counts["bear"] > 0,
        "bull_pct": round(counts["bull"] / total * 100, 1),
        "bear_pct": round(counts["bear"] / total * 100, 1),
        "chop_pct": round(counts["chop"] / total * 100, 1),
    }


def _regime_breakdown(trades: List[TradeRec]) -> dict:
    out: Dict[str, dict] = {}
    by: Dict[str, List[float]] = {}
    for t in trades:
        by.setdefault(t.regime, []).append(t.pnl_r)
    for regime, rs in by.items():
        arr = np.array(rs, dtype=np.float64)
        out[regime] = {
            "trade_count": int(arr.size),
            "win_rate": round(float(np.mean(arr > 0)), 3) if arr.size else 0.0,
            "avg_r": round(float(np.mean(arr)), 4) if arr.size else 0.0,
        }
    return out


# ── profit factor / expectancy helper ───────────────────────────────────────


def _pf_exp(rs: List[float]) -> Tuple[Optional[float], float, int]:
    n = len(rs)
    if not n:
        return None, 0.0, 0
    wins = sum(r for r in rs if r > 0)
    loss = abs(sum(r for r in rs if r <= 0))
    if loss > 0:
        pf = round(wins / loss, 3)
    else:
        pf = None  # no losers — undefined rather than a fake "perfect" number
    return pf, round(sum(rs) / n, 4), n


# ── orchestration ───────────────────────────────────────────────────────────


def run_scalping_backtest(
    underlying: str,
    c_macro: list,
    c_exec: list,
    cfg: ScalpingProfile,
    strategies: List[str],
    *,
    fee_rt_pct: float = FEE_RT_PCT,
) -> BacktestOutput:
    """Replay every requested-and-enabled strategy and assemble honest stats.

    Sizing for the equity curve / drawdown risks `cfg.risk_percent` of equity
    per trade (R-based), matching how the live `/scalping/execute` path sizes.
    """
    n_exec = len(c_exec)
    ts_macro = [c.timestamp_ms for c in c_macro]
    step = EXEC_STEP.get(cfg.execution_timeframe or "30m", 2)
    maxh = EXEC_MAXH.get(cfg.execution_timeframe or "30m", 96)

    # Only replay strategies that are both requested and enabled on the profile,
    # so the backtest matches what the live scanner would actually fire.
    active = [
        s for s in strategies
        if s in EVALUATORS and getattr(cfg, f"enable_{s}", False)
    ]

    enough_data = (n_exec >= W_EXEC + 50 and len(c_macro) >= W_MACRO + 5)

    all_trades: List[TradeRec] = []
    if enough_data:
        for strat in active:
            all_trades.extend(_replay_strategy(
                underlying, c_macro, c_exec, ts_macro, cfg,
                EVALUATORS[strat], strat, step, maxh, fee_rt_pct,
            ))
    all_trades.sort(key=lambda t: t.entry_ts)

    nets = [t.pnl_r for t in all_trades]
    total = len(all_trades)
    wins = sum(1 for r in nets if r > 0)
    win_rate = round(wins / total, 4) if total else 0.0
    pf, expectancy, _ = _pf_exp(nets)
    avg_cost_r = round(float(np.mean([t.cost_r for t in all_trades])), 4) if total else 0.0

    # Equity curve: compound R-sized returns at risk_percent of equity per trade.
    risk_frac = (cfg.risk_percent or 1.0) / 100.0
    eq = [1.0]
    for r in nets:
        eq.append(max(1e-9, eq[-1] * (1.0 + r * risk_frac)))
    curve = np.array(eq, dtype=np.float64)
    net_return_pct = round((curve[-1] / curve[0] - 1.0) * 100.0, 2) if total else 0.0
    if curve.size >= 2:
        peak = np.maximum.accumulate(curve)
        max_dd = round(float(np.min((curve - peak) / peak)) * 100.0, 2)
    else:
        max_dd = 0.0

    # In-sample / out-of-sample split by exec-bar position (70/30 by time).
    split_bar = int(W_EXEC + (n_exec - W_EXEC) * (1.0 - OOS_FRAC)) if enough_data else 0
    is_r = [t.pnl_r for t in all_trades if t.entry_bar < split_bar]
    oos_r = [t.pnl_r for t in all_trades if t.entry_bar >= split_bar]
    is_pf, is_exp, n_is = _pf_exp(is_r)
    oos_pf, oos_exp, n_oos = _pf_exp(oos_r)
    if n_oos < MIN_OOS_TRADES:
        generalises = False
        oos_note = (f"Only {n_oos} out-of-sample trades (< {MIN_OOS_TRADES}) — "
                    f"not enough to judge generalisation. Use a longer window.")
    elif oos_pf is not None and oos_pf > 1.0:
        generalises = True
        oos_note = (f"Edge holds out-of-sample (OOS PF {oos_pf} on {n_oos} held-out "
                    f"trades vs in-sample {is_pf}).")
    else:
        generalises = False
        oos_note = (f"Edge does NOT hold out-of-sample (OOS PF {oos_pf} on {n_oos} "
                    f"trades vs in-sample {is_pf}) — likely curve-fit to the window.")

    return BacktestOutput(
        trades=all_trades,
        bars_evaluated=n_exec,
        total_trades=total,
        win_rate=win_rate,
        expectancy_r=expectancy,
        profit_factor=pf,
        net_return_pct=net_return_pct,
        max_drawdown_pct=max_dd,
        avg_cost_r=avg_cost_r,
        equity_curve=[round(float(v), 6) for v in curve.tolist()],
        sample_quality=classify_sample_size(total),
        regime_coverage={
            **_window_regime_coverage(c_macro, cfg),
            "by_regime": _regime_breakdown(all_trades),
        },
        oos={
            "n_is": n_is, "n_oos": n_oos,
            "is_pf": is_pf, "is_exp": is_exp,
            "oos_pf": oos_pf, "oos_exp": oos_exp,
            "generalises": generalises, "note": oos_note,
        },
    )
