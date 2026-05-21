"""
Sterling v4 Phase 1 — BTC mean-reversion knob search.

Sweeps the FadeExtremesConfig knobs across BTC scalping_5m / 15m / 30m and
the BTC TFProfile exit knobs (stop / tp / trail / hold_bars). Same staged
shape + statistical gates as `btc_scalping_search.py`:

  Tier 1 — Coarse  : rsi_extreme_high × vol_climax_pct × short_bias_boost
                     × payoff_mode × v4_trail_mult            (≤ 64 combos)
  Tier 2 — Refine  : v4_stop_mult × v4_tp_mult × hold_bars   (27 × 3 cand)
  Tier 3 — score_min : 6 / 8 / 10 / 12                          (4 combos)

Validation: walk-forward (3 splits, 70/30 train/test) + deflated_sharpe ≥ 0.95
+ bootstrap p05 > 0 + permutation p < 0.05. ETH safety check identical to
`btc_scalping_search.py`.

The track router is set to route BTC short-TF to "mean_reversion" — that's
hard-coded in `config/tracks.yaml`. This driver just sweeps the MR knobs
behind the router; it does not re-route.
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

from app.schemas.market import Candle
from app.engines.backtest.backtest_mtf import run_mtf_backtest, PROFILES
from app.engines.backtest.sweep import walk_forward_split
from app.engines.analytics.performance import sharpe as _sharpe_curve
from app.services.funding import default_funding_8h_pct
from baseline_report import build_report
from scripts.btc_scalping_search import (
    _load_candles, _aggregate_to_1d, _proportional_slice, _trades_from_result,
    _train_sharpe, _bootstrap_sharpe_ci, _permutation_p_value, _all_gates_pass,
    _eth_safety_snapshot, _eth_snapshots_match,
)


# ────────────────────────────────────────────────────────────────────────────
# Knob grids
# ────────────────────────────────────────────────────────────────────────────

# Tier 1 — fade-extremes confluence knobs.
_T1_RSI_HIGH       = [70.0, 75.0, 80.0]
_T1_VOL_PCT        = [0.85, 0.92, 0.95]
_T1_SHORT_BIAS     = [0.0, 2.0, 4.0]
_T1_PAYOFF         = ["chandelier_trail", "signal_atr_v4"]
_T1_TRAIL          = [1.5, 2.0, 2.5]
# Cardinality cap: 3·3·3·2·3 = 162 combos — too many. Subsample below.

# Tier 2 — TFProfile exit knobs.
_T2_STOP           = [1.0, 1.2, 1.5]
_T2_TP             = [1.5, 2.0, 2.5]
def _t2_hold(pkey: str) -> List[int]:
    base = {"scalping_5m": 16, "scalping_15m": 16, "scalping_30m": 10}[pkey]
    return [max(2, base - 4), base, base + 4]

# Tier 3 — score_min sweep on the refined winner.
_T3_SCORE_MIN      = [6.0, 8.0, 10.0, 12.0]


# Choose a balanced subset of Tier 1 so cardinality stays under 60.
# Take all rsi/payoff/trail combos but pin vol_pct=0.92 and short_bias=2.0
# in the coarse pass. Tier 2 lets the strongest survivors widen those knobs.
def _build_tier1_combos() -> List[Dict[str, Any]]:
    out = []
    for rsi_h, pay, trail in product(_T1_RSI_HIGH, _T1_PAYOFF, _T1_TRAIL):
        out.append({
            "rsi_extreme_high":  rsi_h,
            "rsi_extreme_low":   100.0 - rsi_h,
            "vol_climax_pct":    0.92,
            "short_bias_boost":  2.0,
            "payoff_mode":       pay,
            "v4_trail_mult":     trail,
        })
    # Add a few extra (vol_pct, short_bias) variants at rsi_high=75 to expand.
    for vp, sb in product(_T1_VOL_PCT, _T1_SHORT_BIAS):
        if vp == 0.92 and sb == 2.0:
            continue  # already covered
        out.append({
            "rsi_extreme_high":  75.0,
            "rsi_extreme_low":   25.0,
            "vol_climax_pct":    vp,
            "short_bias_boost":  sb,
            "payoff_mode":       "chandelier_trail",
            "v4_trail_mult":     2.0,
        })
    return out  # 18 + 8 = 26 combos


def _build_tier2_combos(profile_key: str, base: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for stop, tp, hold in product(_T2_STOP, _T2_TP, _t2_hold(profile_key)):
        c = dict(base)
        c["v4_stop_mult"] = stop
        c["v4_tp_mult"]   = tp
        c["hold_bars"]    = hold
        out.append(c)
    return out  # 27 per base


# ────────────────────────────────────────────────────────────────────────────
# Per-combo backtest
# ────────────────────────────────────────────────────────────────────────────

def _split_pair_for_profile(profile_key: str, n_signal_bars: int):
    return walk_forward_split(n_signal_bars, n_splits=3, train_pct=0.7)


def _candle_kwargs(profile_key: str, sig_slice: List[Candle],
                   reg_slice: List[Candle]) -> Dict[str, Any]:
    """All non-target candle lists empty so run_mtf_backtest skips them."""
    kw = {k: [] for k in ("candles_5m", "candles_15m", "candles_30m",
                          "candles_1h", "candles_2h", "candles_4h", "c_1d")}
    if profile_key == "scalping_5m":
        kw["candles_5m"]  = sig_slice
        kw["candles_15m"] = reg_slice
    elif profile_key == "scalping_15m":
        kw["candles_15m"] = sig_slice
        kw["candles_1h"]  = reg_slice
    elif profile_key == "scalping_30m":
        kw["candles_30m"] = sig_slice
        kw["candles_2h"]  = reg_slice
    return kw


def _run_combo(
    underlying: str, profile_key: str,
    sig_full: List[Candle], reg_full: List[Candle],
    splits, phase: str, combo: Dict[str, Any], score_min: float,
    funding_8h: float,
) -> Tuple[float, int, List[List[Dict[str, Any]]]]:
    """Run one combo across all train (or test) windows. Returns
    (mean_sharpe, total_trades, per_window_trade_lists)."""
    ranges = [tr for tr, _ in splits] if phase == "train" else [te for _, te in splits]
    sharpes: List[float] = []
    total_n  = 0
    per_window: List[List[Dict[str, Any]]] = []
    n_sig = len(sig_full)

    mr_config = {
        "rsi_extreme_high":  combo.get("rsi_extreme_high",  75.0),
        "rsi_extreme_low":   combo.get("rsi_extreme_low",   25.0),
        "vol_climax_pct":    combo.get("vol_climax_pct",    0.95),
        "short_bias_boost":  combo.get("short_bias_boost",  2.0),
    }
    profile_overrides = {profile_key: {
        "payoff_mode":  combo.get("payoff_mode",  "chandelier_trail"),
        "v4_trail_mult": combo.get("v4_trail_mult", 2.0),
        "v4_stop_mult":  combo.get("v4_stop_mult",  1.2),
        "v4_tp_mult":    combo.get("v4_tp_mult",    2.0),
        "hold_bars":     combo.get("hold_bars",     16),
    }}

    for rng in ranges:
        sig_slice = sig_full[rng[0]:rng[1]]
        reg_slice = _proportional_slice(reg_full, n_sig, rng)
        kw = _candle_kwargs(profile_key, sig_slice, reg_slice)
        res = run_mtf_backtest(
            underlying=underlying,
            profiles=[profile_key],
            score_min=score_min,
            payoff_mode=(combo.get("payoff_mode") if combo.get("payoff_mode") != "signal_atr_v4"
                         else "chandelier_trail"),
            exit_atr_tf="signal",
            funding_8h_pct=funding_8h,
            apply_slippage=True, emit_events=True,
            profile_overrides=profile_overrides,
            mr_config=mr_config,
            **kw,
        )
        trades = _trades_from_result(res.get(profile_key, {}))
        s, n = _train_sharpe(trades)
        sharpes.append(s)
        total_n += n
        per_window.append(trades)
    mean_s = float(np.mean(sharpes)) if sharpes else -999.0
    return mean_s, total_n, per_window


# ────────────────────────────────────────────────────────────────────────────
# Per-profile staged search
# ────────────────────────────────────────────────────────────────────────────

def _gate_eval(
    underlying: str, profile_key: str,
    sig_full: List[Candle], reg_full: List[Candle],
    splits, combo: Dict[str, Any], score_min: float, funding_8h: float,
    n_trials_for_deflate: int,
) -> Dict[str, Any]:
    """Run OOS evaluation on `combo`; compute all three statistical gates."""
    test_sharpe_per_split, n_per_split, per_win = [], [], []
    oos_all: List[Dict[str, Any]] = []
    _mean, _n, per_window = _run_combo(
        underlying, profile_key, sig_full, reg_full,
        splits, "test", combo, score_min, funding_8h,
    )
    for tr in per_window:
        s, n = _train_sharpe(tr)
        test_sharpe_per_split.append(s)
        n_per_split.append(n)
        oos_all.extend(tr)

    signal_bar_ms = PROFILES[profile_key].signal_bar_ms
    rpt = build_report(
        asset=underlying, profile=profile_key, trades=oos_all,
        signal_bar_ms=signal_bar_ms, n_trials_search=n_trials_for_deflate,
    )
    pnls = np.array([float(t["pnl_pct"]) for t in oos_all], dtype=np.float64)
    b_p05, b_p50, b_p95 = _bootstrap_sharpe_ci(pnls)
    perm_p = _permutation_p_value(pnls)
    deflated_p = rpt.get("deflated_sharpe")
    gates_pass = _all_gates_pass(
        None if deflated_p is None else float(deflated_p), b_p05, perm_p,
    )
    return {
        "config": dict(combo, score_min=score_min),
        "test_sharpe_per_split": test_sharpe_per_split,
        "test_sharpe":  rpt.get("sharpe"),
        "test_profit_factor": rpt.get("profit_factor"),
        "test_win_rate":      rpt.get("win_rate"),
        "test_max_drawdown":  rpt.get("max_drawdown"),
        "oos_trade_count":    len(oos_all),
        "oos_trade_count_per_split": n_per_split,
        "deflated_sharpe":    deflated_p,
        "bootstrap_sharpe_p05_p50_p95": [b_p05, b_p50, b_p95],
        "permutation_p_value": perm_p,
        "all_gates_pass":     gates_pass,
        "regime_breakdown":   rpt.get("regime_breakdown"),
        "edge_status":        rpt.get("edge_status"),
    }


def _search_profile(
    underlying: str, profile_key: str,
    candles_all: Dict[str, List[Candle]], funding_8h: float,
) -> Dict[str, Any]:
    sig_key, reg_key = {
        "scalping_5m":  ("5m",  "15m"),
        "scalping_15m": ("15m", "1h"),
        "scalping_30m": ("30m", "2h"),
    }[profile_key]
    sig_full = candles_all[sig_key]
    reg_full = candles_all[reg_key]
    splits = _split_pair_for_profile(profile_key, len(sig_full))
    if not splits:
        return {"profile": profile_key, "error": "no_splits"}

    print(f"\n┌── {underlying} {profile_key} — MR knob search ─────────────────")
    n_trials_searched = 0

    # ── Tier 1 ───────────────────────────────────────────────────────────
    t1 = _build_tier1_combos()
    n_trials_searched += len(t1)
    print(f"│ Tier 1: {len(t1)} combos × {len(splits)} splits "
          f"= {len(t1) * len(splits)} backtests")
    t1_results: List[Tuple[Dict[str, Any], float, int]] = []
    for i, combo in enumerate(t1):
        mean_s, n, _ = _run_combo(
            underlying, profile_key, sig_full, reg_full,
            splits, "train", combo, score_min=8.0, funding_8h=funding_8h,
        )
        t1_results.append((combo, mean_s, n))
        if (i + 1) % 10 == 0:
            print(f"│   T1 progress {i+1}/{len(t1)}")
    t1_results.sort(key=lambda r: r[1], reverse=True)
    top1 = t1_results[:3]
    print(f"│ T1 top3 train_sharpe: {[round(r[1], 3) for r in top1]}")

    # ── Tier 2 ───────────────────────────────────────────────────────────
    t2_combos = [c for combo, _, _ in top1
                 for c in _build_tier2_combos(profile_key, combo)]
    n_trials_searched += len(t2_combos)
    print(f"│ Tier 2: {len(t2_combos)} combos × {len(splits)} splits "
          f"= {len(t2_combos) * len(splits)} backtests")
    t2_results: List[Tuple[Dict[str, Any], float, int]] = []
    for i, combo in enumerate(t2_combos):
        mean_s, n, _ = _run_combo(
            underlying, profile_key, sig_full, reg_full,
            splits, "train", combo, score_min=8.0, funding_8h=funding_8h,
        )
        t2_results.append((combo, mean_s, n))
        if (i + 1) % 20 == 0:
            print(f"│   T2 progress {i+1}/{len(t2_combos)}")
    t2_results.sort(key=lambda r: r[1], reverse=True)
    if not t2_results:
        return {"profile": profile_key, "error": "no_t2", "n_trials": n_trials_searched}
    best_combo = t2_results[0][0]
    best_train_sharpe = t2_results[0][1]
    print(f"│ T2 best train_sharpe={best_train_sharpe:.3f}")

    # ── Tier 3 — sweep score_min on best combo ──────────────────────────
    t3_results: List[Dict[str, Any]] = []
    n_trials_searched += len(_T3_SCORE_MIN)
    print(f"│ Tier 3: score_min sweep across {_T3_SCORE_MIN}")
    for sm in _T3_SCORE_MIN:
        ev = _gate_eval(
            underlying, profile_key, sig_full, reg_full, splits,
            best_combo, sm, funding_8h, n_trials_searched,
        )
        t3_results.append(ev)
        print(f"│   score_min={sm} test_sharpe={ev['test_sharpe']} "
              f"deflated_p={ev['deflated_sharpe']} oos_n={ev['oos_trade_count']} "
              f"gates={ev['all_gates_pass']}")

    # Pick the highest test Sharpe among Tier-3 evaluations.
    def _score(e):
        ts = e.get("test_sharpe")
        return ts if isinstance(ts, (int, float)) else -999.0
    winner_idx = max(range(len(t3_results)), key=lambda i: _score(t3_results[i]))
    # Copy out to avoid the self-reference when serialising all_t3.
    winner = dict(t3_results[winner_idx])
    winner["n_trials_searched"] = n_trials_searched
    # all_t3 stores a serialisable summary of each score_min sweep result
    # without the regime_breakdown (which is already deep + bulky).
    winner["all_t3"] = [
        {k: v for k, v in e.items() if k != "regime_breakdown"}
        for e in t3_results
    ]

    print(f"│ FINAL winner test_sharpe={winner['test_sharpe']} "
          f"deflated_p={winner['deflated_sharpe']} oos_n={winner['oos_trade_count']} "
          f"gates={winner['all_gates_pass']}")
    print(f"└──────────────────────────────────────────────────────────────\n")
    return winner


# ────────────────────────────────────────────────────────────────────────────
# Driver
# ────────────────────────────────────────────────────────────────────────────

def _format_md(winners: Dict[str, Any]) -> str:
    cols = ["profile", "rsi_high", "vol_pct", "short_bias", "payoff_mode",
            "stop", "tp", "trail", "hold", "score_min",
            "test Sharpe", "deflated_p", "bootstrap p05", "perm p",
            "trades", "WR", "PF", "gates_pass"]
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join(["---"] * len(cols)) + "|"]
    for p, w in winners.items():
        if "error" in w:
            out.append(f"| {p} | ERROR: {w['error']} |" + " |" * (len(cols) - 2))
            continue
        c = w["config"]
        out.append("| " + " | ".join([
            p,
            f"{c.get('rsi_extreme_high', 75.0):.0f}",
            f"{c.get('vol_climax_pct', 0.95):.2f}",
            f"{c.get('short_bias_boost', 2.0):.1f}",
            c.get("payoff_mode", "chandelier_trail"),
            f"{c.get('v4_stop_mult', 1.2):.2f}",
            f"{c.get('v4_tp_mult',  2.0):.2f}",
            f"{c.get('v4_trail_mult', 2.0):.2f}",
            str(c.get("hold_bars", "—")),
            f"{c.get('score_min', 8.0):.1f}",
            (f"{w['test_sharpe']:.3f}" if w["test_sharpe"] is not None else "—"),
            (f"{w['deflated_sharpe']:.3f}" if w["deflated_sharpe"] is not None else "—"),
            f"{w['bootstrap_sharpe_p05_p50_p95'][0]:.3f}",
            f"{w['permutation_p_value']:.4f}",
            str(w["oos_trade_count"]),
            (f"{w['test_win_rate']:.1f}" if w["test_win_rate"] is not None else "—"),
            (f"{w['test_profit_factor']:.2f}" if w["test_profit_factor"] is not None else "—"),
            ("✓" if w["all_gates_pass"] else "✗"),
        ]) + " |")
    return "\n".join(out) + "\n"


def main() -> int:
    db_path = _HERE / "sterling_paper.db"
    if not db_path.exists():
        print(f"[mr-search] db not found: {db_path}", file=sys.stderr)
        return 1
    out_dir = _HERE / "baselines"
    out_dir.mkdir(exist_ok=True)

    t0 = time.time()
    print("[mr-search] loading candles…")
    btc_5m  = _load_candles("BTCUSD", "5m",  db_path)
    btc_15m = _load_candles("BTCUSD", "15m", db_path)
    btc_30m = _load_candles("BTCUSD", "30m", db_path)
    btc_1h  = _load_candles("BTCUSD", "1H",  db_path)
    btc_2h  = _load_candles("BTCUSD", "2H",  db_path)
    btc_4h  = _load_candles("BTCUSD", "4H",  db_path)
    btc_1d  = _aggregate_to_1d(btc_4h)

    eth_5m  = _load_candles("ETHUSD", "5m",  db_path)
    eth_15m = _load_candles("ETHUSD", "15m", db_path)
    eth_30m = _load_candles("ETHUSD", "30m", db_path)
    eth_1h  = _load_candles("ETHUSD", "1H",  db_path)
    eth_2h  = _load_candles("ETHUSD", "2H",  db_path)
    eth_4h  = _load_candles("ETHUSD", "4H",  db_path)
    eth_1d  = _aggregate_to_1d(eth_4h)
    print(f"[mr-search] BTC sizes 5m={len(btc_5m)} 15m={len(btc_15m)} 30m={len(btc_30m)}")

    funding_btc = default_funding_8h_pct("BTC")
    funding_eth = default_funding_8h_pct("ETH")

    print("[mr-search] ETH safety snapshot — before search …")
    eth_before = _eth_safety_snapshot(eth_5m, eth_15m, eth_30m, eth_1h, eth_2h,
                                      eth_4h, eth_1d, funding_eth)
    print(f"[mr-search]   eth_before = {asdict(eth_before)}")

    btc_candles_all = {
        "5m": btc_5m, "15m": btc_15m, "30m": btc_30m,
        "1h": btc_1h, "2h": btc_2h, "4h": btc_4h, "1d": btc_1d,
    }

    winners: Dict[str, Any] = {}
    for pkey in ("scalping_30m", "scalping_15m", "scalping_5m"):
        winners[pkey] = _search_profile("BTC", pkey, btc_candles_all, funding_btc)

    print("[mr-search] ETH safety snapshot — after search …")
    eth_after = _eth_safety_snapshot(eth_5m, eth_15m, eth_30m, eth_1h, eth_2h,
                                     eth_4h, eth_1d, funding_eth)
    eth_ok = _eth_snapshots_match(eth_before, eth_after)
    print(f"[mr-search]   eth_after  = {asdict(eth_after)}")
    print(f"[mr-search]   ETH match  = {eth_ok}")

    elapsed = time.time() - t0
    print(f"[mr-search] total wall-clock {elapsed:.1f}s")

    payload = {
        "run_at": datetime.utcnow().isoformat() + "Z",
        "wall_clock_seconds": round(elapsed, 1),
        "eth_safety_check": {
            "before": asdict(eth_before),
            "after":  asdict(eth_after),
            "ok":     eth_ok,
        },
        "winners": winners,
    }
    date = datetime.utcnow().strftime("%Y%m%d")
    json_path = out_dir / f"btc_mr_search_{date}.json"
    md_path   = out_dir / f"btc_mr_search_{date}.md"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_format_md(winners))
    print(f"[mr-search] wrote {json_path}")
    print(f"[mr-search] wrote {md_path}")

    if not eth_ok:
        print("[mr-search] FATAL: ETH safety check failed — MR overrides leaked.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
