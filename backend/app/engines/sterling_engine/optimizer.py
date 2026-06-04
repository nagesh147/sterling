"""Focused, overfit-safe parameter + timeframe optimizer for the price-action scalper.

Sweeps a small grid of the highest-impact parameters AND a set of (structure TF,
entry TF) pairs, ranking each combination by its **out-of-sample** profit factor —
every symbol's bars are split 70/30 by time, combos are scored on the held-out
last 30%, so settings that only curve-fit the in-sample window are penalised. We
also report the IS↔OOS PF correlation across the whole grid as an honesty signal:
if it's low/negative the rankings don't generalise and the manual config should be
preferred (mirrors the project's existing cross-validation discipline).

The optimum is only *recommended* (and overlaid by the `use_optimized` toggle) when
it genuinely generalises — beats the baseline out-of-sample, clears PF 1, has a
non-trivial OOS sample, and the grid's IS↔OOS correlation is non-negative.
Otherwise `best_params` falls back to the baseline (current) values, making the
toggle a safe no-op rather than a vehicle for adopting overfit settings.

Pure functions over candle maps — no I/O. The API layer loads candles (per
resolution) and runs `optimize(...)` in a background thread.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, asdict
from itertools import product
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from app.engines.sterling_engine.config import ScalpingConfig
from app.engines.sterling_engine.levels import detect_levels
from app.engines.sterling_engine.price_action import evaluate_price_action
from app.engines.sterling_engine.scanner import _macro_regime, _is_counter_trend

# (structure, entry) pairs to sweep — the new 4h/30m default, the 30m-focused
# alternatives that generalised best, and the old 4h/15m as a reference (it was
# the worst OOS pair, so it confirms the move). Each needs both resolutions stored.
DEFAULT_TF_PAIRS: List[Tuple[str, str]] = [("4h", "15m"), ("4h", "30m"), ("1h", "30m")]

# Param grid (level_tolerance left at the config default to keep the TF-expanded
# sweep tractable: 3 TF pairs × 8 param combos = 24 runs).
DEFAULT_GRID: Dict[str, list] = {
    "pa_confirm_bars": [3, 5],
    "pa_min_rr": [1.5, 2.0],
    "macro_trend_filter": [False, True],
}

# Per execution-TF scan cadence (bars) and max hold (~1 trading day of bars).
# Finer TFs use a coarser step so the swept replay stays tractable (the confirm
# window ≥3 still catches breakouts within the step).
EXEC_STEP = {"5m": 6, "15m": 2, "30m": 1, "1h": 1}
EXEC_MAXH = {"5m": 288, "15m": 96, "30m": 48, "1h": 24}

W_EXEC, W_MACRO = 672, 180
OOS_FRAC = 0.30
MIN_OOS_TRADES = 15


def grid_combos(grid: Dict[str, list]) -> List[dict]:
    keys = list(grid.keys())
    return [dict(zip(keys, vals)) for vals in product(*[grid[k] for k in keys])]


def _exit_fixed(cE, i, is_long, entry, sl, tp, maxh):
    for k in range(i + 1, min(i + 1 + maxh, len(cE))):
        hi, lo = cE[k].high, cE[k].low
        if is_long:
            if lo <= sl: return sl, k
            if hi >= tp: return tp, k
        else:
            if hi >= sl: return sl, k
            if lo <= tp: return tp, k
    j = min(i + maxh, len(cE) - 1)
    return cE[j].close, j


def _replay_symbol(sym, cM, cE, cfg, tsM, step, maxh) -> List[tuple]:
    """(exec_bar_index, pnl_r) for every armed signal on one symbol (fixed SL/TP
    exit, one trade at a time — mirrors the live idempotency guard)."""
    out: List[tuple] = []
    cooldown, cj, levels = -1, -1, []
    n = len(cE)
    i = W_EXEC
    while i < n - 1:
        if i <= cooldown:
            i += step; continue
        j = bisect.bisect_right(tsM, cE[i].timestamp_ms)
        if j < W_MACRO:
            i += step; continue
        if j != cj:
            cw = cM[j - W_MACRO:j]
            levels = detect_levels(
                np.array([c.high for c in cw]), np.array([c.low for c in cw]),
                np.array([c.close for c in cw]), np.array([c.timestamp_ms for c in cw], dtype=np.int64), cfg)
            cj = j
        sig = evaluate_price_action(sym, cM[j - W_MACRO:j], cE[i - W_EXEC:i + 1], levels, cfg)
        if sig.entry_ok and sig.entry and sig.stop_loss and sig.take_profit:
            if cfg.macro_trend_filter:
                base = cM[max(0, j - cfg.macro_trend_ema_slow - 5):j]
                regime = _macro_regime(np.array([c.close for c in base]), cfg)
                if regime in ("bull", "bear") and _is_counter_trend(sig.direction, regime):
                    i += step; continue
            is_long = sig.direction == "long"
            ex, ck = _exit_fixed(cE, i, is_long, sig.entry, sig.stop_loss, sig.take_profit, maxh)
            out.append((i, (1 if is_long else -1) * (ex - sig.entry) / abs(sig.entry - sig.stop_loss)))
            cooldown = ck
        i += step
    return out


def _pf_exp(trades: List[float]):
    n = len(trades)
    if not n:
        return 0.0, 0.0, 0
    wins = sum(t for t in trades if t > 0)
    loss = abs(sum(t for t in trades if t <= 0))
    pf = (wins / loss) if loss > 0 else (999.0 if wins > 0 else 0.0)
    return round(pf, 3), round(sum(trades) / n, 4), n


@dataclass
class ComboResult:
    params: dict                # swept params + macro_timeframe + execution_timeframe
    is_pf: float
    is_exp: float
    n_is: int
    oos_pf: float
    oos_exp: float
    n_oos: int
    total_trades: int
    score: float


@dataclass
class OptimizeResult:
    combos: List[dict]
    best_params: dict           # overlaid by the toggle (= baseline if no safe improvement)
    baseline: dict
    is_oos_corr: float
    recommend_change: bool      # False ⇒ overlay is a no-op; keep the manual config
    n_combos: int
    universe: List[str]
    note: str


def _evaluate_combo(tf_pair, params, base_cfg, candles_by_res, ts_by_res) -> ComboResult:
    macro, execr = tf_pair
    cfg = base_cfg.model_copy(update={**params, "macro_timeframe": macro, "execution_timeframe": execr})
    step = EXEC_STEP.get(execr, 2)
    maxh = EXEC_MAXH.get(execr, 96)
    cM_map, cE_map = candles_by_res.get(macro, {}), candles_by_res.get(execr, {})
    is_t: List[float] = []
    oos_t: List[float] = []
    for sym in cE_map:
        cM, cE = cM_map.get(sym), cE_map.get(sym)
        if cM is None or cE is None or len(cE) < W_EXEC + 50 or len(cM) < W_MACRO + 5:
            continue
        n = len(cE)
        split = int(W_EXEC + (n - W_EXEC) * (1 - OOS_FRAC))
        for (i, pnl) in _replay_symbol(sym, cM, cE, cfg, ts_by_res[macro][sym], step, maxh):
            (oos_t if i >= split else is_t).append(pnl)
    is_pf, is_exp, n_is = _pf_exp(is_t)
    oos_pf, oos_exp, n_oos = _pf_exp(oos_t)
    score = round(oos_pf * min(1.0, n_oos / MIN_OOS_TRADES), 3)
    out_params = {**params, "macro_timeframe": macro, "execution_timeframe": execr}
    return ComboResult(out_params, is_pf, is_exp, n_is, oos_pf, oos_exp, n_oos, n_is + n_oos, score)


def optimize(
    candles_by_res: Dict[str, Dict[str, list]],
    base_cfg: ScalpingConfig,
    grid: Optional[Dict[str, list]] = None,
    tf_pairs: Optional[List[Tuple[str, str]]] = None,
    progress: Optional[Callable[[int, int], None]] = None,
) -> OptimizeResult:
    """Rank (timeframe × param) combinations by held-out (OOS) profit factor.

    `candles_by_res` is {resolution: {symbol: [Candle, ...]}} and must contain
    every resolution referenced by `tf_pairs` (and the base_cfg's own TFs).
    """
    grid = grid or DEFAULT_GRID
    tf_pairs = tf_pairs or DEFAULT_TF_PAIRS
    ts_by_res = {res: {s: [c.timestamp_ms for c in arr] for s, arr in m.items()}
                 for res, m in candles_by_res.items()}
    universe = sorted({s for m in candles_by_res.values() for s in m})

    param_combos = grid_combos(grid)
    all_combos = [(tf, p) for tf in tf_pairs for p in param_combos]
    results: List[ComboResult] = []
    for n, (tf, p) in enumerate(all_combos, 1):
        results.append(_evaluate_combo(tf, p, base_cfg, candles_by_res, ts_by_res))
        if progress:
            progress(n, len(all_combos))

    # Baseline = the engine's current TF + default params (use_optimized off).
    base_tf = (base_cfg.macro_timeframe or "4h", base_cfg.execution_timeframe or "15m")
    base_params = {k: getattr(base_cfg, k) for k in grid}
    baseline = asdict(_evaluate_combo(base_tf, base_params, base_cfg, candles_by_res, ts_by_res))
    base_only = {**base_params, "macro_timeframe": base_tf[0], "execution_timeframe": base_tf[1]}

    results.sort(key=lambda r: (r.score, r.oos_exp), reverse=True)

    is_arr = np.array([r.is_pf for r in results])
    oos_arr = np.array([r.oos_pf for r in results])
    corr = (float(np.corrcoef(is_arr, oos_arr)[0, 1])
            if len(results) > 1 and is_arr.std() > 1e-9 and oos_arr.std() > 1e-9 else 0.0)

    best = results[0] if results else None
    base_oos_pf = baseline.get("oos_pf", 0.0)
    recommend_change = bool(
        best is not None and corr >= 0.0
        and best.oos_pf > base_oos_pf and best.oos_pf > 1.0
        and best.n_oos >= MIN_OOS_TRADES
    )
    recommended_params = best.params if (recommend_change and best) else base_only

    if not results:
        note = "No combinations produced trades on this window."
    elif recommend_change:
        note = (f"Optimum generalises (IS↔OOS corr {corr:+.2f}): OOS PF {best.oos_pf} vs "
                f"baseline {base_oos_pf} at {best.params['macro_timeframe']}/"
                f"{best.params['execution_timeframe']} — safe to enable.")
    elif corr < 0.0:
        note = (f"Overfit (IS↔OOS corr {corr:+.2f}): in-sample winners fail out-of-sample. "
                f"No generalising improvement — recommending NO change (keep manual config).")
    elif best.n_oos < MIN_OOS_TRADES:
        note = (f"Too few out-of-sample trades to trust (best combo n={best.n_oos} < {MIN_OOS_TRADES}, "
                f"corr {corr:+.2f}) — recommending NO change. Re-run with more symbols / a longer window.")
    elif best.oos_pf <= base_oos_pf:
        note = (f"No combo beats the baseline out-of-sample (best OOS PF {best.oos_pf} vs "
                f"{base_oos_pf}, corr {corr:+.2f}) — recommending NO change.")
    else:
        note = (f"Best OOS PF {best.oos_pf} ≤ 1.0 — not profitable out-of-sample "
                f"(corr {corr:+.2f}) — recommending NO change.")

    return OptimizeResult(
        combos=[asdict(r) for r in results],
        best_params=recommended_params,
        baseline=baseline,
        is_oos_corr=round(corr, 3),
        recommend_change=recommend_change,
        n_combos=len(results),
        universe=universe,
        note=note,
    )
