"""
v4 BTC scalping edge-search driver.

Staged combinatorial-search × walk-forward × probabilistic-validation for the
three BTC short-TF profiles (scalping_5m / scalping_15m / scalping_30m). After
the v4 refactor these profiles still bleed cost-drag; ETH scalping_30m wins on
the same code at deflated_sharpe = 1.0. The driver isolates a BTC-specific
config per profile and writes the winner JSON + Markdown to backend/baselines/.

Search structure:

  Tier 1 — Coarse   : score_min × payoff_mode × v4_trail_mult     (40 combos)
  Tier 2 — Refine   : v4_stop_mult × v4_tp_mult × hold_bars       (27 × 5 cand)
  Tier 2.5 — Direction filter: long_only / short_only / both       (3 × 3 cand)
  Tier 3 — st_configs fallback (only if Tier 2.5 fails the gate)

Walk-forward: 3 non-overlapping splits via `walk_forward_split`. Train on the
first 70% of each, pick best by mean train Sharpe across splits, validate on
the remaining 30%. Aggregate OOS trades across splits → one final trade list
per profile.

Statistical gates (all three must pass):

  1. Deflated Sharpe ≥ 0.95 (multiple-comparisons corrected with n_trials
     equal to the total combos searched at the tier that produced the winner)
  2. Bootstrap Sharpe 5th percentile > 0 (2000 resamples)
  3. Permutation test p-value < 0.05 (2000 sign-flips, label permutation null)

ETH safety check: ETHUSD scalping_30m baseline is re-run before AND after the
search; (sharpe, trade_count, deflated_sharpe, net_pnl_sum) must match within
1e-9. Falls through to PROFILES because PROFILES_BY_ASSET has no "ETH" key.

Output: backend/baselines/btc_scalping_search_<YYYYMMDD>.json (machine) and
        backend/baselines/btc_scalping_search_<YYYYMMDD>.md   (human).
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
from app.engines.analytics.performance import deflated_sharpe, sharpe as _sharpe_curve
from app.services.funding import default_funding_8h_pct
from baseline_report import build_report


# ────────────────────────────────────────────────────────────────────────────
# Candle loading (mirrors run_baseline_db.py — same DB, same resolutions)
# ────────────────────────────────────────────────────────────────────────────

_RESOLUTION_MAP = {
    "5m":  "5m", "15m": "15m", "30m": "30m",
    "1H":  "1h", "2H":  "2h",  "4H":  "4h", "1D":  "1D",
}
_DAY_MS = 24 * 3_600_000


def _load_candles(symbol: str, resolution: str, db_path: Path) -> List[Candle]:
    db_res = _RESOLUTION_MAP.get(resolution, resolution.lower())
    uri = f"file:{db_path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, timeout=30.0)
    rows = conn.execute(
        "SELECT time, open, high, low, close, volume FROM ohlcv "
        "WHERE symbol=? AND resolution=? ORDER BY time ASC",
        (symbol, db_res),
    ).fetchall()
    conn.close()
    return [
        Candle(
            timestamp_ms=int(t) * 1000,
            open=float(o), high=float(h), low=float(l),
            close=float(c), volume=float(v or 0.0),
        )
        for t, o, h, l, c, v in rows
    ]


def _aggregate_to_1d(c_4h: List[Candle]) -> List[Candle]:
    """Aggregate 4H bars to 1D by UTC-day bucket (matches run_baseline_db.py)."""
    if not c_4h:
        return []
    buckets: Dict[int, List[Candle]] = {}
    for c in c_4h:
        buckets.setdefault(c.timestamp_ms // _DAY_MS, []).append(c)
    out: List[Candle] = []
    for day in sorted(buckets):
        bars = buckets[day]
        if len(bars) != 6:
            continue
        bars.sort(key=lambda b: b.timestamp_ms)
        out.append(Candle(
            timestamp_ms=day * _DAY_MS, open=bars[0].open,
            high=max(b.high for b in bars), low=min(b.low for b in bars),
            close=bars[-1].close, volume=sum(b.volume for b in bars),
        ))
    return out


# ────────────────────────────────────────────────────────────────────────────
# Walk-forward slicing
# ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Splits:
    """Per-profile train/test index ranges (inclusive start, exclusive end)."""
    train: List[Tuple[int, int]]
    test:  List[Tuple[int, int]]


def _profile_splits(n_signal_bars: int, n_splits: int = 3, train_pct: float = 0.7) -> _Splits:
    raw = walk_forward_split(n_signal_bars, n_splits=n_splits, train_pct=train_pct)
    return _Splits(train=[t for t, _ in raw], test=[te for _, te in raw])


def _proportional_slice(c: List[Candle], n_ref: int, rng: Tuple[int, int]) -> List[Candle]:
    """Slice an aux series by the ratio of (rng[0]:rng[1])/n_ref."""
    if not c or n_ref <= 0:
        return []
    s_ratio = rng[0] / n_ref
    e_ratio = rng[1] / n_ref
    s = int(s_ratio * len(c))
    e = int(e_ratio * len(c))
    return c[s:e]


# ────────────────────────────────────────────────────────────────────────────
# Per-combo backtest helper
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class _Combo:
    """One concrete knob assignment that we'll evaluate."""
    score_min:     float
    payoff_mode:   str          # "chandelier_trail" | "signal_atr_v4"
    v4_trail_mult: float
    v4_stop_mult:  float = 1.2
    v4_tp_mult:    float = 2.0
    hold_bars:     Optional[int] = None  # None → use profile default
    st_configs:    Optional[List[Tuple[int, float]]] = None
    direction_filter: Optional[str] = None

    def overrides(self, profile_key: str) -> Dict[str, Any]:
        ov: Dict[str, Any] = {
            "v4_trail_mult": self.v4_trail_mult,
            "v4_stop_mult":  self.v4_stop_mult,
            "v4_tp_mult":    self.v4_tp_mult,
        }
        if self.hold_bars is not None:
            ov["hold_bars"] = self.hold_bars
        if self.st_configs is not None:
            ov["st_configs"] = self.st_configs
        return ov

    def as_dict(self) -> Dict[str, Any]:
        return {
            "score_min": self.score_min,
            "payoff_mode": self.payoff_mode,
            "v4_trail_mult": self.v4_trail_mult,
            "v4_stop_mult":  self.v4_stop_mult,
            "v4_tp_mult":    self.v4_tp_mult,
            "hold_bars":     self.hold_bars,
            "st_configs":    self.st_configs,
            "direction_filter": self.direction_filter,
        }


def _candles_for_profile(
    profile_key: str,
    c_5m, c_15m, c_30m, c_1h, c_2h, c_4h, c_1d,
) -> Tuple[List[Candle], List[Candle]]:
    """Map a profile key to (signal_candles, regime_candles)."""
    return {
        "scalping_5m":  (c_5m, c_15m),
        "scalping_15m": (c_15m, c_1h),
        "scalping_30m": (c_30m, c_2h),
        "intraday_1h":  (c_1h, c_4h),
        "intraday_4h":  (c_4h, c_1d),
    }[profile_key]


def _backtest_one(
    underlying:  str,
    profile_key: str,
    combo:       _Combo,
    sig_candles: List[Candle],
    reg_candles: List[Candle],
    funding_8h:  float,
    *,
    candles_5m=None, candles_15m=None, candles_30m=None,
    candles_1h=None, candles_2h=None, candles_4h=None, c_1d=None,
) -> Dict[str, Any]:
    """One backtest run for a (profile, combo) on the supplied candle slices.

    The candle slices ARE the train (or test) window. Non-target profiles are
    passed empty so they don't run; the keyword args mirror run_mtf_backtest.
    """
    # All non-target candle lists default to empty so run_mtf_backtest skips them.
    res = run_mtf_backtest(
        underlying=underlying,
        candles_15m=candles_15m or [], candles_1h=candles_1h or [],
        candles_4h=candles_4h or [], c_1d=c_1d or [],
        candles_5m=candles_5m or [], candles_30m=candles_30m or [],
        candles_2h=candles_2h or [],
        profiles=[profile_key],
        score_min=combo.score_min,
        payoff_mode=combo.payoff_mode if combo.payoff_mode != "signal_atr_v4" else "chandelier_trail",
        # Note: run_mtf_backtest doesn't expose payoff_mode="signal_atr_v4" via
        # Literal; we instead set TFProfile.payoff_mode via profile_overrides.
        exit_atr_tf="signal",
        funding_8h_pct=funding_8h,
        apply_slippage=True,
        emit_events=True,
        profile_overrides={profile_key: {**combo.overrides(profile_key), "payoff_mode": combo.payoff_mode}},
        direction_filter=combo.direction_filter,
    )
    return res.get(profile_key, {})


def _trades_from_result(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pluck trade-kind events from a single-profile result."""
    out: List[Dict[str, Any]] = []
    for ev in res.get("events", []):
        if ev.get("kind") != "trade":
            continue
        p = ev.get("payload") or {}
        out.append({
            "pnl_pct":       p.get("net_pnl_pct") or 0.0,
            "gross_pnl_pct": p.get("gross_pnl_pct"),
            "net_pnl_pct":   p.get("net_pnl_pct"),
            "cost_pct":      p.get("cost_pct"),
            "regime":        p.get("regime"),
            "direction":     p.get("direction"),
            "entry_ts_ms":   p.get("entry_ts_ms"),
            "exit_ts_ms":    p.get("exit_ts_ms"),
        })
    return out


# Tiny-sample guard. Below this trade count the per-trade Sharpe is dominated
# by noise (a 3-trade curve with near-zero variance can produce inf/1e16 values
# and dominate the search). 15 is a practical floor that matches what
# baseline_report.py uses for "low_sample_size" warnings (_MIN_TRADES_FOR_METRICS=30).
_MIN_TRADES_FOR_VALID_SHARPE = 15


def _train_sharpe(trades: List[Dict[str, Any]]) -> Tuple[float, int]:
    """Compute compounding-curve Sharpe. NaN-safe; returns (sharpe, n).

    Returns the -999 sentinel when:
      - no trades
      - fewer than _MIN_TRADES_FOR_VALID_SHARPE (small-sample noise)
      - resulting Sharpe is non-finite (inf / NaN from zero-variance curves)
    The sentinel keeps these combos out of the top-K ranking so the search
    doesn't favour artifacts of tiny-N anomalies.
    """
    n = len(trades)
    if n == 0:
        return -999.0, 0
    if n < _MIN_TRADES_FOR_VALID_SHARPE:
        return -999.0, n
    pnls = [float(t["pnl_pct"]) for t in trades]
    curve = np.ones(len(pnls) + 1, dtype=np.float64)
    for i, p in enumerate(pnls):
        curve[i + 1] = curve[i] * (1.0 + p)
    s = float(_sharpe_curve(curve))
    if not math.isfinite(s):
        return -999.0, n
    return s, n


# ────────────────────────────────────────────────────────────────────────────
# Statistical-validation helpers (the "probability" component)
# ────────────────────────────────────────────────────────────────────────────

def _sharpe_from_pnls(pnls: np.ndarray) -> float:
    """Sample Sharpe from a per-trade PnL array (no curve compounding)."""
    if pnls.size < 2 or float(np.std(pnls, ddof=1)) == 0.0:
        return 0.0
    return float(np.mean(pnls) / np.std(pnls, ddof=1) * math.sqrt(252))


def _bootstrap_sharpe_ci(
    pnls: np.ndarray, n_resamples: int = 2000, seed: int = 7,
) -> Tuple[float, float, float]:
    """Resample-with-replacement bootstrap of the Sharpe ratio.
    Returns (p05, p50, p95)."""
    if pnls.size < 5:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    sharpes = np.empty(n_resamples, dtype=np.float64)
    n = pnls.size
    for k in range(n_resamples):
        idx = rng.integers(0, n, n)
        sharpes[k] = _sharpe_from_pnls(pnls[idx])
    return (
        float(np.quantile(sharpes, 0.05)),
        float(np.quantile(sharpes, 0.50)),
        float(np.quantile(sharpes, 0.95)),
    )


def _permutation_p_value(
    pnls: np.ndarray, n_permutations: int = 2000, seed: int = 11,
) -> float:
    """Sign-flip permutation null: under the null (no edge), the sign of each
    trade PnL is random. Returns P(null_sharpe >= observed_sharpe).
    """
    if pnls.size < 5:
        return 1.0
    observed = _sharpe_from_pnls(pnls)
    if not np.isfinite(observed):
        return 1.0
    rng = np.random.default_rng(seed)
    abs_p = np.abs(pnls)
    count_ge = 0
    for _ in range(n_permutations):
        signs = rng.choice([-1.0, 1.0], size=pnls.size)
        s = _sharpe_from_pnls(abs_p * signs)
        if s >= observed:
            count_ge += 1
    return (count_ge + 1) / (n_permutations + 1)


def _all_gates_pass(
    deflated_p: Optional[float], bootstrap_p05: float, perm_p: float,
) -> bool:
    return bool(
        deflated_p is not None
        and deflated_p >= 0.95
        and bootstrap_p05 > 0.0
        and perm_p < 0.05
    )


# ────────────────────────────────────────────────────────────────────────────
# ETH safety check
# ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _EthSnapshot:
    sharpe:          float
    trade_count:     int
    deflated_sharpe: Optional[float]
    net_pnl_sum:     float


def _eth_safety_snapshot(
    c5m, c15m, c30m, c1h, c2h, c4h, c1d, funding_8h: float,
) -> _EthSnapshot:
    """Run the ETHUSD scalping_30m baseline once and snapshot its top stats."""
    profile = PROFILES["scalping_30m"]
    res = run_mtf_backtest(
        underlying="ETH",
        candles_15m=c15m, candles_1h=c1h, candles_4h=c4h, c_1d=c1d,
        candles_5m=c5m, candles_30m=c30m, candles_2h=c2h,
        profiles=["scalping_30m"],
        score_min=11.0,  # mirrors _PROFILE_SCORE_MIN_PER_ASSET[("ETH","scalping_30m")]
        funding_8h_pct=funding_8h,
        apply_slippage=True,
        emit_events=True,
        exit_atr_tf="signal",
        payoff_mode="chandelier_trail",
    )
    trades = _trades_from_result(res["scalping_30m"])
    rpt = build_report(
        asset="ETH", profile="scalping_30m",
        trades=trades, signal_bar_ms=profile.signal_bar_ms, n_trials_search=1,
    )
    return _EthSnapshot(
        sharpe=float(rpt.get("sharpe") or 0.0),
        trade_count=int(rpt.get("trade_count") or 0),
        deflated_sharpe=(None if rpt.get("deflated_sharpe") is None
                         else float(rpt["deflated_sharpe"])),
        net_pnl_sum=float(rpt.get("net_pnl_sum") or 0.0),
    )


def _eth_snapshots_match(a: _EthSnapshot, b: _EthSnapshot) -> bool:
    if a.trade_count != b.trade_count:
        return False
    if abs(a.sharpe - b.sharpe) > 1e-9:
        return False
    if abs(a.net_pnl_sum - b.net_pnl_sum) > 1e-9:
        return False
    da, db = a.deflated_sharpe, b.deflated_sharpe
    if (da is None) != (db is None):
        return False
    if da is not None and db is not None and abs(da - db) > 1e-9:
        return False
    return True


# ────────────────────────────────────────────────────────────────────────────
# Staged search
# ────────────────────────────────────────────────────────────────────────────

# Per-profile knob grids.
_PROFILE_BASE_HOLD = {"scalping_5m": 16, "scalping_15m": 16, "scalping_30m": 10}

# Lower the upper score_min bound to 16 — at 18 nearly every combo produced
# <15 trades per split, which under the small-sample guard now returns -999
# and starves the top-K. The first search showed tight v4_stop_mult=1.0 also
# killed too many trades; widen the lower bound up to 1.2 and add 2.0 as the
# upper to test looser stops (especially useful on 5m where signal-TF ATR is
# small and 1.2×ATR is brutal).
_TIER1_SCORE_MIN  = [8.0, 10.0, 12.0, 14.0, 16.0]
_TIER1_PAYOFF     = ["chandelier_trail", "signal_atr_v4"]
_TIER1_TRAIL_MULT = [1.5, 2.0, 2.5, 3.0]

_TIER2_STOP_MULT  = [1.2, 1.5, 2.0]
_TIER2_TP_MULT    = [1.5, 2.0, 2.5]
def _tier2_hold_grid(profile_key: str) -> List[int]:
    base = _PROFILE_BASE_HOLD[profile_key]
    return [max(2, base - 4), base, base + 4]

_TIER25_DIRECTIONS = ["both", "long_only", "short_only"]

_TIER3_ST_PRESETS = [
    [(7,  3.0), (14, 2.0), (21, 2.0)],   # base
    [(10, 3.0), (20, 2.0), (28, 1.5)],   # smoother
    [(5,  2.5), (12, 2.0), (20, 1.5)],   # faster
]


def _build_tier1_combos() -> List[_Combo]:
    out: List[_Combo] = []
    for sm, pm, tm in product(_TIER1_SCORE_MIN, _TIER1_PAYOFF, _TIER1_TRAIL_MULT):
        out.append(_Combo(
            score_min=sm, payoff_mode=pm, v4_trail_mult=tm,
        ))
    return out


def _build_tier2_combos(profile_key: str, base: _Combo) -> List[_Combo]:
    out: List[_Combo] = []
    for sm, tp, hb in product(_TIER2_STOP_MULT, _TIER2_TP_MULT, _tier2_hold_grid(profile_key)):
        out.append(_Combo(
            score_min=base.score_min, payoff_mode=base.payoff_mode,
            v4_trail_mult=base.v4_trail_mult,
            v4_stop_mult=sm, v4_tp_mult=tp, hold_bars=hb,
            direction_filter=base.direction_filter,
            st_configs=base.st_configs,
        ))
    return out


def _build_tier25_combos(base: _Combo) -> List[_Combo]:
    out: List[_Combo] = []
    for d in _TIER25_DIRECTIONS:
        out.append(_Combo(
            score_min=base.score_min, payoff_mode=base.payoff_mode,
            v4_trail_mult=base.v4_trail_mult, v4_stop_mult=base.v4_stop_mult,
            v4_tp_mult=base.v4_tp_mult, hold_bars=base.hold_bars,
            direction_filter=(None if d == "both" else d),
            st_configs=base.st_configs,
        ))
    return out


def _build_tier3_combos(base: _Combo) -> List[_Combo]:
    out: List[_Combo] = []
    for st in _TIER3_ST_PRESETS:
        out.append(_Combo(
            score_min=base.score_min, payoff_mode=base.payoff_mode,
            v4_trail_mult=base.v4_trail_mult, v4_stop_mult=base.v4_stop_mult,
            v4_tp_mult=base.v4_tp_mult, hold_bars=base.hold_bars,
            direction_filter=base.direction_filter,
            st_configs=st,
        ))
    return out


def _candles_kwargs_for(
    profile_key: str, c5m, c15m, c30m, c1h, c2h, c4h, c1d,
) -> Dict[str, Any]:
    """Returns the candles= kwargs needed by run_mtf_backtest for this profile."""
    if profile_key == "scalping_5m":
        return dict(candles_5m=c5m, candles_15m=c15m)
    if profile_key == "scalping_15m":
        return dict(candles_15m=c15m, candles_1h=c1h)
    if profile_key == "scalping_30m":
        return dict(candles_30m=c30m, candles_2h=c2h)
    return {}


def _evaluate_combo_on_splits(
    underlying: str, profile_key: str, combo: _Combo,
    candles_all: Dict[str, List[Candle]], splits: _Splits, funding_8h: float,
    phase: str,
) -> Tuple[float, int, List[List[Dict[str, Any]]]]:
    """Run `combo` on all train (or all test) windows of `splits`. Returns
    (mean_sharpe, total_trades, per_window_trade_lists)."""
    ranges = splits.train if phase == "train" else splits.test
    sharpes: List[float] = []
    total_n  = 0
    all_trades: List[List[Dict[str, Any]]] = []

    sig_key, reg_key = {
        "scalping_5m":  ("5m",  "15m"),
        "scalping_15m": ("15m", "1h"),
        "scalping_30m": ("30m", "2h"),
    }[profile_key]
    sig_full = candles_all[sig_key]
    reg_full = candles_all[reg_key]
    n_sig = len(sig_full)

    for rng in ranges:
        sig_slice = sig_full[rng[0]:rng[1]]
        reg_slice = _proportional_slice(reg_full, n_sig, rng)
        kw = _candles_kwargs_for(profile_key, None, None, None, None, None, None, None)
        # Use slices for THIS profile, empty for others.
        kw_with_slices = {k: [] for k in
                          ("candles_5m", "candles_15m", "candles_30m",
                           "candles_1h", "candles_2h", "candles_4h", "c_1d")}
        if profile_key == "scalping_5m":
            kw_with_slices["candles_5m"]  = sig_slice
            kw_with_slices["candles_15m"] = reg_slice
        elif profile_key == "scalping_15m":
            kw_with_slices["candles_15m"] = sig_slice
            kw_with_slices["candles_1h"]  = reg_slice
        elif profile_key == "scalping_30m":
            kw_with_slices["candles_30m"] = sig_slice
            kw_with_slices["candles_2h"]  = reg_slice
        res = run_mtf_backtest(
            underlying=underlying,
            profiles=[profile_key],
            score_min=combo.score_min,
            payoff_mode=(combo.payoff_mode
                         if combo.payoff_mode != "signal_atr_v4"
                         else "chandelier_trail"),
            exit_atr_tf="signal",
            funding_8h_pct=funding_8h,
            apply_slippage=True,
            emit_events=True,
            profile_overrides={profile_key: {**combo.overrides(profile_key),
                                             "payoff_mode": combo.payoff_mode}},
            direction_filter=combo.direction_filter,
            **kw_with_slices,
        )
        trades = _trades_from_result(res.get(profile_key, {}))
        s, n = _train_sharpe(trades)
        sharpes.append(s)
        total_n += n
        all_trades.append(trades)
    mean_s = float(np.mean(sharpes)) if sharpes else -999.0
    return mean_s, total_n, all_trades


# ────────────────────────────────────────────────────────────────────────────
# Per-profile search orchestration
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class _CandidateResult:
    combo:             _Combo
    train_sharpe_mean: float
    train_n_total:     int
    train_sharpe_per_split: List[float] = field(default_factory=list)


def _rank_top_k(cands: List[_CandidateResult], k: int) -> List[_CandidateResult]:
    return sorted(cands, key=lambda r: r.train_sharpe_mean, reverse=True)[:k]


def _search_one_profile(
    underlying: str, profile_key: str,
    candles_all: Dict[str, List[Candle]], splits: _Splits, funding_8h: float,
) -> Dict[str, Any]:
    """Drive Tier 1 → Tier 2 → Tier 2.5 → Tier 3 for one profile.
    Returns a dict with all candidates, OOS metrics, and gate verdicts."""
    print(f"\n┌── {underlying} {profile_key} — staged search ─────────────────")
    n_trials_searched = 0

    # ── Tier 1 ───────────────────────────────────────────────────────────
    tier1 = _build_tier1_combos()
    n_trials_searched += len(tier1)
    print(f"│ Tier 1 (coarse): {len(tier1)} combos × {len(splits.train)} splits "
          f"= {len(tier1) * len(splits.train)} backtests")
    tier1_results: List[_CandidateResult] = []
    for i, combo in enumerate(tier1):
        mean_s, n, _ = _evaluate_combo_on_splits(
            underlying, profile_key, combo, candles_all, splits, funding_8h, "train",
        )
        tier1_results.append(_CandidateResult(combo, mean_s, n))
        if (i + 1) % 10 == 0:
            print(f"│   T1 progress {i+1}/{len(tier1)}")
    # Reduced from top-5 to top-3 in Tier 2 to fit the ~1h wall-clock budget
    # on the 5m profile (which is 3× slower than 30m due to ~6× more bars).
    top1 = _rank_top_k(tier1_results, 3)
    print(f"│ T1 top3 mean_train_sharpe: "
          f"{[round(r.train_sharpe_mean, 3) for r in top1]}")

    # ── Tier 2 ───────────────────────────────────────────────────────────
    tier2_combos: List[_Combo] = []
    for cand in top1:
        tier2_combos.extend(_build_tier2_combos(profile_key, cand.combo))
    n_trials_searched += len(tier2_combos)
    print(f"│ Tier 2 (refine): {len(tier2_combos)} combos × {len(splits.train)} splits "
          f"= {len(tier2_combos) * len(splits.train)} backtests")
    tier2_results: List[_CandidateResult] = []
    for i, combo in enumerate(tier2_combos):
        mean_s, n, _ = _evaluate_combo_on_splits(
            underlying, profile_key, combo, candles_all, splits, funding_8h, "train",
        )
        tier2_results.append(_CandidateResult(combo, mean_s, n))
        if (i + 1) % 20 == 0:
            print(f"│   T2 progress {i+1}/{len(tier2_combos)}")
    # Reduced from top-3 to top-1 in Tier 2.5 — direction filter is a single
    # categorical knob, so the top training Sharpe is a strong prior here.
    top2 = _rank_top_k(tier2_results, 1)
    print(f"│ T2 top1 mean_train_sharpe: "
          f"{[round(r.train_sharpe_mean, 3) for r in top2]}")

    # ── Tier 2.5 — direction filter ──────────────────────────────────────
    tier25_combos: List[_Combo] = []
    for cand in top2:
        tier25_combos.extend(_build_tier25_combos(cand.combo))
    n_trials_searched += len(tier25_combos)
    print(f"│ Tier 2.5 (direction): {len(tier25_combos)} combos × {len(splits.train)} splits "
          f"= {len(tier25_combos) * len(splits.train)} backtests")
    tier25_results: List[_CandidateResult] = []
    for combo in tier25_combos:
        mean_s, n, _ = _evaluate_combo_on_splits(
            underlying, profile_key, combo, candles_all, splits, funding_8h, "train",
        )
        tier25_results.append(_CandidateResult(combo, mean_s, n))
    top25 = _rank_top_k(tier25_results, 1)
    if not top25:
        print("│ Tier 2.5 produced no candidates — bailing out")
        return {"profile": profile_key, "error": "no_tier25_candidates",
                "n_trials_searched": n_trials_searched}
    best_pre_tier3 = top25[0]
    print(f"│ T2.5 best: train_sharpe={best_pre_tier3.train_sharpe_mean:.3f} "
          f"dir={best_pre_tier3.combo.direction_filter or 'both'}")

    # ── Tier 3 — st_configs fallback (only fired if OOS gate fails) ──────
    # We always try Tier 3 only when Tier 2.5 winner's OOS doesn't clear the
    # gate; first compute that OOS to decide.
    def _oos_of(c: _Combo) -> Tuple[List[Dict[str, Any]], List[float], List[int]]:
        per_split_sharpe: List[float] = []
        per_split_n: List[int] = []
        all_oos: List[Dict[str, Any]] = []
        for rng in splits.test:
            kw = {k: [] for k in
                  ("candles_5m", "candles_15m", "candles_30m",
                   "candles_1h", "candles_2h", "candles_4h", "c_1d")}
            sig_key, reg_key = {
                "scalping_5m":  ("5m",  "15m"),
                "scalping_15m": ("15m", "1h"),
                "scalping_30m": ("30m", "2h"),
            }[profile_key]
            sig_slice = candles_all[sig_key][rng[0]:rng[1]]
            reg_slice = _proportional_slice(candles_all[reg_key],
                                            len(candles_all[sig_key]), rng)
            if profile_key == "scalping_5m":
                kw["candles_5m"]  = sig_slice; kw["candles_15m"] = reg_slice
            elif profile_key == "scalping_15m":
                kw["candles_15m"] = sig_slice; kw["candles_1h"]  = reg_slice
            else:  # scalping_30m
                kw["candles_30m"] = sig_slice; kw["candles_2h"]  = reg_slice
            res = run_mtf_backtest(
                underlying=underlying,
                profiles=[profile_key],
                score_min=c.score_min,
                payoff_mode=(c.payoff_mode if c.payoff_mode != "signal_atr_v4"
                             else "chandelier_trail"),
                exit_atr_tf="signal",
                funding_8h_pct=funding_8h,
                apply_slippage=True, emit_events=True,
                profile_overrides={profile_key:
                                   {**c.overrides(profile_key),
                                    "payoff_mode": c.payoff_mode}},
                direction_filter=c.direction_filter,
                **kw,
            )
            tr = _trades_from_result(res.get(profile_key, {}))
            s, n = _train_sharpe(tr)
            per_split_sharpe.append(s)
            per_split_n.append(n)
            all_oos.extend(tr)
        return all_oos, per_split_sharpe, per_split_n

    def _gate_eval(c: _Combo, n_trials_for_deflate: int) -> Dict[str, Any]:
        oos_trades, per_split_sharpe, per_split_n = _oos_of(c)
        signal_bar_ms = PROFILES[profile_key].signal_bar_ms
        rpt = build_report(asset=underlying, profile=profile_key,
                           trades=oos_trades, signal_bar_ms=signal_bar_ms,
                           n_trials_search=n_trials_for_deflate)
        pnls = np.array([float(t["pnl_pct"]) for t in oos_trades], dtype=np.float64)
        b_p05, b_p50, b_p95 = _bootstrap_sharpe_ci(pnls)
        perm_p = _permutation_p_value(pnls)
        deflated_p = rpt.get("deflated_sharpe")
        gates_pass = _all_gates_pass(
            None if deflated_p is None else float(deflated_p),
            b_p05, perm_p,
        )
        return {
            "config": c.as_dict(),
            "train_sharpe_per_split": per_split_sharpe,
            "train_sharpe_mean": float(np.mean(per_split_sharpe))
                                 if per_split_sharpe else -999.0,
            "oos_trade_count":     len(oos_trades),
            "oos_trade_count_per_split": per_split_n,
            "test_sharpe":         rpt.get("sharpe"),
            "test_profit_factor":  rpt.get("profit_factor"),
            "test_win_rate":       rpt.get("win_rate"),
            "test_max_drawdown":   rpt.get("max_drawdown"),
            "deflated_sharpe":     deflated_p,
            "bootstrap_sharpe_p05_p50_p95": [b_p05, b_p50, b_p95],
            "permutation_p_value": perm_p,
            "all_gates_pass":      gates_pass,
            "regime_breakdown":    rpt.get("regime_breakdown"),
            "edge_status":         rpt.get("edge_status"),
        }

    winner = _gate_eval(best_pre_tier3.combo, n_trials_searched)
    if not winner["all_gates_pass"]:
        # ── Tier 3 fallback ─────────────────────────────────────────────
        # Only REPLACE the Tier 2.5 winner if a Tier 3 candidate both
        # (a) beats the Tier 2.5 train Sharpe AND (b) clears all gates.
        # Otherwise we preserve the Tier 2.5 winner so the final output
        # reflects the best-found configuration, not the empty fallback.
        print(f"│ T2.5 winner did not clear gates — running Tier 3 (st_configs)")
        tier3_combos = _build_tier3_combos(best_pre_tier3.combo)
        n_trials_searched += len(tier3_combos)
        for combo in tier3_combos:
            mean_s, n, _ = _evaluate_combo_on_splits(
                underlying, profile_key, combo, candles_all, splits,
                funding_8h, "train",
            )
            if mean_s > best_pre_tier3.train_sharpe_mean:
                cand_eval = _gate_eval(combo, n_trials_searched)
                if cand_eval["all_gates_pass"]:
                    print(f"│ T3 candidate cleared gates")
                    winner = cand_eval
                    break

    print(f"│ FINAL train_mean={winner['train_sharpe_mean']:.3f} "
          f"test_sharpe={winner['test_sharpe']} "
          f"deflated_p={winner['deflated_sharpe']} "
          f"gates_pass={winner['all_gates_pass']}")
    print(f"└──────────────────────────────────────────────────────────────\n")

    # All candidates summary (top 10 by mean train sharpe) for postmortem.
    all_cands: List[_CandidateResult] = list(tier1_results) + list(tier2_results) + list(tier25_results)
    top10 = _rank_top_k(all_cands, 10)
    winner["n_trials_searched"] = n_trials_searched
    winner["all_candidates_top10"] = [
        {"config": c.combo.as_dict(),
         "train_sharpe_mean": c.train_sharpe_mean,
         "train_n_total": c.train_n_total}
        for c in top10
    ]
    return winner


# ────────────────────────────────────────────────────────────────────────────
# Driver entry point
# ────────────────────────────────────────────────────────────────────────────

def _format_md(winners: Dict[str, Any]) -> str:
    cols = ["profile", "score_min", "payoff_mode", "trail", "stop", "tp",
            "hold", "dir", "train Sharpe", "test Sharpe", "deflated_p",
            "bootstrap p05", "perm p", "trades", "gates_pass"]
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join(["---"] * len(cols)) + "|"]
    for pkey, w in winners.items():
        if "error" in w:
            out.append(f"| {pkey} | ERROR: {w['error']} | | | | | | | | | | | | | |")
            continue
        c = w["config"]
        out.append("| " + " | ".join([
            pkey,
            str(c["score_min"]),
            c["payoff_mode"],
            f"{c['v4_trail_mult']:.2f}",
            f"{c['v4_stop_mult']:.2f}",
            f"{c['v4_tp_mult']:.2f}",
            str(c["hold_bars"]),
            (c["direction_filter"] or "both"),
            f"{w['train_sharpe_mean']:.3f}",
            (f"{w['test_sharpe']:.3f}" if w["test_sharpe"] is not None else "—"),
            (f"{w['deflated_sharpe']:.3f}" if w["deflated_sharpe"] is not None else "—"),
            f"{w['bootstrap_sharpe_p05_p50_p95'][0]:.3f}",
            f"{w['permutation_p_value']:.4f}",
            str(w["oos_trade_count"]),
            ("✓" if w["all_gates_pass"] else "✗"),
        ]) + " |")
    return "\n".join(out) + "\n"


def main() -> int:
    db_path = _HERE / "sterling_paper.db"
    if not db_path.exists():
        print(f"[search] db not found: {db_path}", file=sys.stderr)
        return 1
    out_dir = _HERE / "baselines"
    out_dir.mkdir(exist_ok=True)

    t0 = time.time()
    print(f"[search] loading BTC + ETH candles from {db_path.name} …")
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
    print(f"[search] BTC sizes 5m={len(btc_5m)} 15m={len(btc_15m)} 30m={len(btc_30m)} "
          f"1H={len(btc_1h)} 2H={len(btc_2h)} 4H={len(btc_4h)} 1D={len(btc_1d)}")
    print(f"[search] ETH sizes 5m={len(eth_5m)} 15m={len(eth_15m)} 30m={len(eth_30m)} "
          f"1H={len(eth_1h)} 2H={len(eth_2h)} 4H={len(eth_4h)} 1D={len(eth_1d)}")

    funding_btc = default_funding_8h_pct("BTC")
    funding_eth = default_funding_8h_pct("ETH")

    # ── ETH safety: before ───────────────────────────────────────────────
    print(f"[search] ETH safety snapshot — before search …")
    eth_before = _eth_safety_snapshot(
        eth_5m, eth_15m, eth_30m, eth_1h, eth_2h, eth_4h, eth_1d, funding_eth,
    )
    print(f"[search]   eth_before = {asdict(eth_before)}")

    btc_candles_all = {
        "5m": btc_5m, "15m": btc_15m, "30m": btc_30m,
        "1h": btc_1h, "2h": btc_2h, "4h": btc_4h, "1d": btc_1d,
    }

    winners: Dict[str, Any] = {}
    for pkey in ("scalping_5m", "scalping_15m", "scalping_30m"):
        sig_key, _reg_key = {
            "scalping_5m":  ("5m",  "15m"),
            "scalping_15m": ("15m", "1h"),
            "scalping_30m": ("30m", "2h"),
        }[pkey]
        splits = _profile_splits(len(btc_candles_all[sig_key]),
                                 n_splits=3, train_pct=0.7)
        if not splits.train:
            winners[pkey] = {"profile": pkey, "error": "no_splits"}
            continue
        winners[pkey] = _search_one_profile(
            "BTC", pkey, btc_candles_all, splits, funding_btc,
        )

    # ── ETH safety: after ────────────────────────────────────────────────
    print(f"[search] ETH safety snapshot — after search …")
    eth_after = _eth_safety_snapshot(
        eth_5m, eth_15m, eth_30m, eth_1h, eth_2h, eth_4h, eth_1d, funding_eth,
    )
    eth_ok = _eth_snapshots_match(eth_before, eth_after)
    print(f"[search]   eth_after  = {asdict(eth_after)}")
    print(f"[search]   ETH match  = {eth_ok}")

    elapsed = time.time() - t0
    print(f"[search] total wall-clock {elapsed:.1f}s")

    payload: Dict[str, Any] = {
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
    json_path = out_dir / f"btc_scalping_search_{date}.json"
    md_path   = out_dir / f"btc_scalping_search_{date}.md"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_format_md(winners))
    print(f"[search] wrote {json_path}")
    print(f"[search] wrote {md_path}")

    if not eth_ok:
        print("[search] FATAL: ETH safety check failed — BTC overrides leaked.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
