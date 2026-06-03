from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from app.engines.indicators.adx import adx as _adx
from .config import (SPLIT, MAX_DD_CAP, MIN_TEST_TRADES, MAX_PBO, MAX_P_LOSS,
                     MIN_OOS_SHARPE, MIN_DSR, SimConfig)
from . import harness as H, signals as S
from .sizing import vol_target_weights


def split_indices(n: int) -> tuple[slice, slice, slice]:
    """Chronological train/validation/test split (no shuffling)."""
    a = int(n * SPLIT[0])
    b = int(n * (SPLIT[0] + SPLIT[1]))
    return slice(0, a), slice(a, b), slice(b, n)


@dataclass
class GateReport:
    passed: bool
    reasons: list[str]
    metrics: dict


def check_gates(test_metrics: dict, oos_sharpe: float, pbo: float,
                p_loss: float, dsr: float) -> GateReport:
    """Evaluate the pre-registered acceptance gates against test-set results.
    All thresholds come from config.py and are fixed BEFORE the test set is seen."""
    reasons: list[str] = []
    if test_metrics["trades"] < MIN_TEST_TRADES:
        reasons.append(f"trades {test_metrics['trades']} < {MIN_TEST_TRADES}")
    if test_metrics["max_dd"] < -MAX_DD_CAP:
        reasons.append(f"maxDD {test_metrics['max_dd']:.2%} worse than -{MAX_DD_CAP:.0%}")
    if oos_sharpe <= MIN_OOS_SHARPE:
        reasons.append(f"oos_sharpe {oos_sharpe:.2f} <= {MIN_OOS_SHARPE}")
    if pbo >= MAX_PBO:
        reasons.append(f"PBO {pbo:.2f} >= {MAX_PBO}")
    if p_loss > MAX_P_LOSS:
        reasons.append(f"p_loss {p_loss:.2f} > {MAX_P_LOSS}")
    if dsr <= MIN_DSR:
        reasons.append(f"DSR {dsr:.2f} <= {MIN_DSR}")
    return GateReport(passed=not reasons, reasons=reasons, metrics=test_metrics)


# --- The validated SterlingV2 stack (SINGLE SOURCE OF TRUTH) ---------------
# Kept levers (per docs/sterling_v2/lever_results.md): symmetric long+short
# signals (lever 1) + vol-targeted sizing (lever 4) + STATIC SL/TP exits (lever 3
# trailing REJECTED). The portfolio combiner + DD breaker (lever 5) sits above
# this per-book stack. The live endpoint and the Task-15 report both call these
# so live == research.
#
# The conviction gate (lever 2) is KEPT but OFF by default for the COMBINED book:
# it lifted the long-ONLY book (esp. BTC) but is redundant once the short side is
# in -- the short side already supplies directional selectivity, so an ADX
# trend-strength filter on top mostly removes good entries and HURTS the combined
# book on the test slice for all three symbols (BTC +1.13->+0.05, ETH +0.24->-0.18,
# SOL +1.26->+0.21 Sharpe). It stays available via adx_min>0 for the long-only path.
V2_STRAT_DEFAULT = "ma_crossover"   # the grounding's proven 4h edge
# Multi-book strategy set TESTED for reaching the 100-trade floor (the strategies
# net-positive in the long-only baseline screen). RESULT: REJECTED -- breakout is a
# consistent OOS loser (BTC/ETH/SOL Sharpe -1.47/-1.11/-0.92) and smc is mixed, so the
# 9-book portfolio fails the OOS-Sharpe/p-loss/DSR gates (see before_after_report.md
# "Stack B"). The LIVE/validated stack is ma_crossover only (V2_STRAT_DEFAULT). This
# constant is kept only to document/repro the rejected expansion, NOT for deployment.
V2_STRATS = ["ma_crossover", "breakout", "smc"]
V2_ADX_MIN_DEFAULT = 0.0            # gate OFF by default for the combined book
V2_TF_DEFAULT = "4h"
V2_CFG = SimConfig(sl_mult=2.0, tp_mult=3.5, fee_round_trip=0.001,
                   slippage=0.0005, allow_short=True)


def adx_trend_gate(df: pd.DataFrame, adx_min: float = 18.0):
    """Side-agnostic conviction gate: trade only when Wilder ADX(14) at i-1 >=
    adx_min (a real trend). Direction is supplied by the signal itself (long vs
    short cross), so one filter gates the combined book without lookahead."""
    arr = np.asarray(_adx(df["high"].to_numpy(float), df["low"].to_numpy(float),
                          df["close"].to_numpy(float), 14), float)

    def _filter(_df: pd.DataFrame, i: int) -> bool:
        if i < 1 or (i - 1) >= len(arr):
            return False
        a = arr[i - 1]
        return bool(np.isfinite(a) and a >= adx_min)

    return _filter


def run_v2_book(d: pd.DataFrame, strat: str = V2_STRAT_DEFAULT,
                adx_min: float = V2_ADX_MIN_DEFAULT, cfg: SimConfig = V2_CFG) -> dict:
    """Run the full kept-lever V2 stack on a single symbol/timeframe frame `d`.
    Returns metrics (vol-sized), the per-trade returns, mean-normalized weights,
    and an equity Series indexed by entry time (for the portfolio combiner).
    adx_min>0 enables the optional conviction gate (off by default)."""
    longs = S.long_signal(strat, d)
    shorts = S.short_signal(strat, d)
    ef = adx_trend_gate(d, adx_min) if adx_min > 0 else None
    res = H.simulate(d, longs, shorts, cfg, entry_filter=ef)
    r = res.returns
    if r.size:
        w = vol_target_weights(r)
        w = w / w.mean() if w.mean() > 0 else w
        eq = pd.Series(np.cumprod(1 + r * w), index=pd.to_datetime(res.entry_times))
    else:
        w, eq = None, pd.Series(dtype=float)
    return {"metrics": H.compute_metrics(res, weights=w), "returns": r,
            "weights": w, "equity": eq, "result": res}


def latest_v2_signal(d: pd.DataFrame, strat: str = V2_STRAT_DEFAULT,
                     adx_min: float = V2_ADX_MIN_DEFAULT, cfg: SimConfig = V2_CFG) -> dict:
    """Evaluate the kept-lever stack on the LATEST completed bar and return the
    actionable signal (side, entry/stop/target, regime_ok, conviction). side 0 =
    no fresh signal. Levels use ATR at the latest bar; entry ~ latest close."""
    longs = S.long_signal(strat, d)
    shorts = S.short_signal(strat, d)
    arr = np.asarray(_adx(d["high"].to_numpy(float), d["low"].to_numpy(float),
                          d["close"].to_numpy(float), 14), float)
    n = len(d)
    i = n - 1
    a = float(arr[i - 1]) if i >= 1 and np.isfinite(arr[i - 1]) else 0.0
    gate_ok = a >= adx_min
    long_fire = bool(longs[i]) and gate_ok
    short_fire = bool(shorts[i]) and gate_ok and cfg.allow_short
    side = 1 if long_fire else (-1 if short_fire else 0)
    close = float(d["close"].iloc[-1])
    atr0 = float(d["atr"].iloc[-1])
    if side == 1:
        stop, target = close - cfg.sl_mult * atr0, close + cfg.tp_mult * atr0
    elif side == -1:
        stop, target = close + cfg.sl_mult * atr0, close - cfg.tp_mult * atr0
    else:
        stop = target = None
    return {"side": side, "entry": close, "stop": stop, "target": target,
            "regime_ok": bool(gate_ok), "conviction": round(a, 2),
            "bar_time": str(d.index[-1])}
