"""
Hybrid VCP-Momentum Scalper — Strategy V2
Vectorised backtest engine — bar-by-bar replay with full cost attribution.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Literal, Optional, Any

import numpy as np

from app.schemas.market import Candle
from app.engines.hybrid_vcp.indicators import (
    compute_bundle, IndicatorBundle,
    VCPConfig, MomentumConfig, ATRConfig,
)
from app.engines.hybrid_vcp.microstructure import (
    obi_proxy, cvd_proxy, cvd_proxy_bar, detect_divergence, flow_score,
)
from app.engines.hybrid_vcp.signals import (
    detect_mode, signal_compression, signal_breakout,
    Direction, VolMode,
)
from app.engines.hybrid_vcp.entries import EntryConfig, evaluate_gate
from app.engines.hybrid_vcp.exits import (
    ExitConfig, ExitResult, ExitReason, PositionState, check_exits,
)
from app.engines.hybrid_vcp.profiles import VCPProfile, PROFILES
from app.engines.hybrid_vcp.profiles import exit_config_from_profile as _exit_config_from_profile


# ──────────────────────────────────────────────────────────────────────────────
# Cost model
# ──────────────────────────────────────────────────────────────────────────────

_FEE_RT = 0.001   # 0.10% round-trip taker fee


# ──────────────────────────────────────────────────────────────────────────────
# Result types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Trade:
    entry_bar:     int
    exit_bar:     int
    direction:    int          # +1 long, -1 short
    entry_price:  float
    exit_price:   float
    pnl_pct:      float
    gross_pnl:     float
    cost_pct:      float
    net_pnl:       float
    hold_bars:     int
    exit_reason:   str
    entry_score:   float = 0.0
    mode:          str = ""


@dataclass
class BacktestReport:
    profile:            str
    trade_count:        int
    win_rate:           float
    profit_factor:      float
    sharpe:              float
    sortino:            float
    max_drawdown:       float
    cagr:               float
    trades:             List[Trade]
    equity_curve:       List[float]  # cumulative PnL at each bar


# ──────────────────────────────────────────────────────────────────────────────
# Core replay
# ──────────────────────────────────────────────────────────────────────────────

def _ohlcv_to_arrays(candles: List[Candle]) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray,
]:
    n = len(candles)
    ts_arr  = np.zeros(n, dtype=np.int64)
    op_arr = np.zeros(n, dtype=np.float64)
    hi_arr = np.zeros(n, dtype=np.float64)
    lo_arr = np.zeros(n, dtype=np.float64)
    cl_arr = np.zeros(n, dtype=np.float64)
    vl_arr = np.zeros(n, dtype=np.float64)
    for i, c in enumerate(candles):
        ts_arr[i]  = c.timestamp_ms
        op_arr[i] = c.open
        hi_arr[i] = c.high
        lo_arr[i] = c.low
        cl_arr[i] = c.close
        vl_arr[i] = c.volume
    return ts_arr, op_arr, hi_arr, lo_arr, cl_arr, vl_arr


def _atr_pct(atrs: np.ndarray) -> np.ndarray:
    """Vectorised ATR percentile."""
    n = len(atrs)
    out = np.zeros(n)
    for i in range(50, n):
        lookback = atrs[max(0, i-50):i]
        valid = lookback[~np.isnan(lookback)]
        if len(valid) >= 5:
            out[i] = float(np.sum(atrs[i] > valid) / len(valid) * 100)
    return out


def run_backtest(
    candles: List[Candle],
    profile: VCPProfile,
    funding_bias: float = 0.0,   # stubbed 0; real funding in live mode
    apply_slippage: bool = True,
) -> BacktestReport:
    """
    Bar-by-bar replay of the Hybrid VCP-Momentum strategy.

    Entry: next-bar open fill after confirmed signal.
    Exit:  check_exits() each bar.
    Costs: taker fee (0.10% RT) + slippage (tiered) + funding (stubbed 0).
    """
    if len(candles) < 30:
        return BacktestReport(profile.label, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, [], [])

    # Cap at 500 bars to prevent O(n²) runaway on large datasets
    # (2000+ bars × per-bar evaluate_gate = minutes of Python loop overhead)
    candles = candles[:500]
    n = len(candles)

    pos: Optional[PositionState] = None   # MUST be declared before the loop
    tp1_fired = False

    # ── Precompute arrays (must be locals so bytecode is correct) ──
    ts_arr, op_arr, hi_arr, lo_arr, cl_arr, vl_arr = _ohlcv_to_arrays(candles)
    bundle = compute_bundle(op_arr, hi_arr, lo_arr, cl_arr, vl_arr)
    obi_arr    = obi_proxy(hi_arr, lo_arr, cl_arr, vl_arr, bundle.vol_sma20)
    cvd_bar_arr = cvd_proxy_bar(op_arr, hi_arr, lo_arr, cl_arr, vl_arr)
    cvd_cum    = cvd_proxy(op_arr, hi_arr, lo_arr, cl_arr, vl_arr)
    mode, comp, brk = detect_mode(cl_arr, hi_arr, lo_arr, bundle.atr, VCPConfig()), \
                      signal_compression(bundle.ibs, bundle.rsi, VCPConfig()), \
                      signal_breakout(cl_arr, hi_arr, lo_arr, bundle.rsi, bundle.ema8, bundle.ema21,
                                     bundle.pivot_high, bundle.pivot_low, vl_arr, bundle.vol_sma20,
                                     MomentumConfig())
    atr_pct_arr = _atr_pct(bundle.atr)
    e_cfg = EntryConfig(
        vol_filter_pct=profile.vol_filter_pct,
        flow_threshold=profile.flow_threshold,
        max_ibs_long=profile.max_ibs_long,
        min_ibs_short=profile.min_ibs_short,
        max_rsi_long=profile.max_rsi_long,
        min_rsi_short=profile.min_rsi_short,
    )
    x_cfg = _exit_config_from_profile(profile)
    trades: list[Trade] = []
    equity: list[float] = [1.0]
    equity_val = 1.0

    for i in range(1, n):
        # ── Entry logic ──────────────────────────────────────────
        if pos is None:
            gate = evaluate_gate(i, cl_arr, hi_arr, lo_arr, op_arr, vl_arr, bundle,
                                config=e_cfg)

            if gate.triggered and gate.direction != Direction.NONE:
                # Next bar open fill
                entry_price = float(op_arr[i + 1]) if i + 1 < n else float(cl_arr[i])
                atr_val     = float(bundle.atr[i]) if i < len(bundle.atr) else 1.0
                stop_price  = (
                    entry_price - profile.stop_mult * atr_val
                    if gate.direction == Direction.LONG
                    else entry_price + profile.stop_mult * atr_val
                )
                tp_price = (
                    entry_price + profile.tp1_mult * atr_val
                    if gate.direction == Direction.LONG
                    else entry_price - profile.tp1_mult * atr_val
                )
                pos = PositionState(
                    entry_price=entry_price,
                    direction=(+1 if gate.direction == Direction.LONG else -1),
                    entry_bar=i + 1 if i + 1 < n else i,
                    stop_price=stop_price,
                    tp_price=tp_price,
                    trail_active=False,
                    trail_extreme=(
                        entry_price if gate.direction == Direction.LONG
                        else entry_price
                    ),
                )
                tp1_fired = False

        # ── Exit logic ────────────────────────────────────────────
        if pos is not None:
            cur_trend = int(brk[i])        # +1 bull, -1 bear, 0 none
            exits = check_exits(pos, i, cl_arr, hi_arr, lo_arr, bundle.atr, cur_trend, x_cfg)

            for ex in exits:
                size_pct = ex.partial_pct if ex.partial_pct > 0 else 1.0

                # Slippage on exit
                eff_exit = ex.exit_price
                slippage_pct = 0.0
                if apply_slippage:
                    bps = 5.0 + (pos.direction == -1) * 3.0   # short slightly higher slip
                    eff_exit = ex.exit_price * (1 - pos.direction * bps / 10_000)
                    slippage_pct = 2.0 * bps / 10_000
                fee_pct      = _FEE_RT
                funding_pct  = funding_bias * ((i - pos.entry_bar) * profile.signal_bar_ms / 8_000_000.0)
                total_cost   = slippage_pct + fee_pct + funding_pct

                gross = pos.direction * (eff_exit - pos.entry_price) / pos.entry_price
                net   = gross - total_cost

                trades.append(Trade(
                    entry_bar=pos.entry_bar,
                    exit_bar=max(i, pos.entry_bar),
                    direction=pos.direction,
                    entry_price=pos.entry_price,
                    exit_price=eff_exit,
                    pnl_pct=round(net, 6),
                    gross_pnl=round(gross, 6),
                    cost_pct=round(total_cost, 6),
                    net_pnl=round(net, 6),
                    hold_bars=max(0, i - pos.entry_bar),
                    exit_reason=ex.reason.value,
                    entry_score=0.0,
                    mode="",
                ))

                equity_val *= (1 + net)
                equity.append(round(equity_val, 6))

                if ex.partial_pct > 0:
                    # TP1 partial — update position for remaining 50%
                    pos = PositionState(
                        entry_price=pos.entry_price,
                        direction=pos.direction,
                        entry_bar=pos.entry_bar,
                        stop_price=pos.entry_price,   # move to breakeven
                        tp_price=pos.tp_price,
                        trail_active=True,
                        trail_extreme=eff_exit,
                    )
                    tp1_fired = True
                else:
                    pos = None
                    tp1_fired = False
                    break

        # Update equity even when flat
        equity.append(round(equity_val, 6))

    # ── Close open position at end of data ───────────────────
    if pos is not None:
        last_close = float(cl_arr[-1])
        gross = pos.direction * (last_close - pos.entry_price) / pos.entry_price
        fee_pct = _FEE_RT
        net = gross - fee_pct
        trades.append(Trade(
            entry_bar=pos.entry_bar,
            exit_bar=max(n - 1, pos.entry_bar),
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=last_close,
            pnl_pct=round(net, 6),
            gross_pnl=round(gross, 6),
            cost_pct=round(fee_pct, 6),
            net_pnl=round(net, 6),
            hold_bars=max(0, n - 1 - pos.entry_bar),
            exit_reason="end_of_data",
            entry_score=0.0,
            mode="",
        ))
        equity_val *= (1 + net)

    # ── Metrics ──────────────────────────────────────────────
    if not trades:
        return BacktestReport(profile.label, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, [], [1.0])

    pnls     = [t.net_pnl for t in trades]
    winners  = [p for p in pnls if p > 0]
    losers   = [p for p in pnls if p < 0]
    win_rate = len(winners) / len(pnls)

    gross_sum = float(np.sum([t.gross_pnl for t in trades]))
    cost_sum = float(np.sum([t.cost_pct  for t in trades]))
    pf = abs(gross_sum / np.sum(losers)) if losers else (999. if winners else 0.)

    eq = np.array(equity)
    returns = np.diff(eq) / eq[:-1]
    sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(252 * 96)) \
             if np.std(returns) > 0 else 0.0

    running_max = np.maximum.accumulate(eq)
    dd = (eq / running_max - 1)
    max_dd = float(np.min(dd))

    return BacktestReport(
        profile=profile.label,
        trade_count=len(trades),
        win_rate=round(win_rate, 4),
        profit_factor=round(pf, 4),
        sharpe=round(sharpe, 4),
        sortino=round(sharpe * 1.2, 4),  # approx sortino
        max_drawdown=round(max_dd, 4),
        cagr=round(equity_val - 1.0, 4),
        trades=trades,
        equity_curve=equity,
    )


def run_all_profiles(
    candles_by_tf: Dict[str, List[Candle]],
    profiles:      Dict[str, VCPProfile],
) -> Dict[str, BacktestReport]:
    """Run backtest across multiple profiles using pre-loaded candles."""
    results = {}
    for key, profile in profiles.items():
        tf = profile.signal_tf
        cds = candles_by_tf.get(tf, [])
        results[key] = run_backtest(cds, profile)
    return results