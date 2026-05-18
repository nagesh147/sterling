"""
Unified performance metrics — honest version (Phase 2 / TTACE).

Key corrections over the legacy implementation:

* Sharpe is computed from CALENDAR-TIME DAILY returns when trade timestamps
  or a per-bar timestamp spacing are available, instead of treating each
  trade as a single "hourly" return and annualising by 8760. The legacy
  approach inflates Sharpe by a factor of ~sqrt(trades-per-year / 252).
* Sortino uses a lower-partial-moment downside deviation (root-mean-square
  of negative returns relative to a target), not the std of negative
  returns.
* Profit factor returns +inf when there are winners and zero losers
  (legacy returned 0.0 — masking a perfect run as nothing).
* Adds CAGR, ulcer index, pain ratio, tail ratio, and deflated Sharpe.

All functions are pure. Public function names from the legacy module are
preserved so existing imports keep working.
"""
from __future__ import annotations
import math
import numpy as np
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

# Calendar-time annualisation. Sterling trades crypto perpetuals 24/7, so
# Sharpe uses 365 calendar days rather than 252 trading days.
_DAYS_PER_YEAR    = 365.0
_MS_PER_DAY       = 86_400_000.0
_LEGACY_PERIODS_PER_YEAR = 8760  # 24 * 365 — back-compat for old signatures


@dataclass
class PerformanceReport:
    sharpe:           float
    calmar:           float
    sortino:          float
    max_drawdown:     float
    win_rate:         float
    avg_rr:           float
    profit_factor:    Optional[float]
    total_trades:     int
    cagr:             Optional[float] = None
    ulcer_index:      Optional[float] = None
    pain_ratio:       Optional[float] = None
    tail_ratio:       Optional[float] = None
    sharpe_method:    str = "calendar_daily"
    regime_breakdown: dict = field(default_factory=dict)


# ── core helpers ──────────────────────────────────────────────────────────────


def _equity_to_returns(equity_curve: np.ndarray) -> np.ndarray:
    if len(equity_curve) < 2:
        return np.array([], dtype=np.float64)
    e = np.asarray(equity_curve, dtype=np.float64)
    return np.diff(e) / e[:-1]


def _daily_returns_from_trades(trades: List[dict]) -> Optional[np.ndarray]:
    """
    Bucket trade returns into calendar days using exit timestamps.
    Returns the per-day log-style returns approximated by sum(pnl_pct) per day.
    """
    stamps = [t.get("exit_ts_ms") for t in trades if t.get("exit_ts_ms")]
    if len(stamps) < 2:
        return None
    pnls = [float(t["pnl_pct"]) for t in trades if t.get("exit_ts_ms")]
    if not pnls:
        return None
    days = np.array([int(s) // int(_MS_PER_DAY) for s in stamps], dtype=np.int64)
    first, last = int(days.min()), int(days.max())
    if last <= first:
        return None
    n = last - first + 1
    daily = np.zeros(n, dtype=np.float64)
    for d, p in zip(days, pnls):
        daily[int(d) - first] += float(p)
    return daily


def max_drawdown(equity_curve: np.ndarray) -> float:
    e = np.asarray(equity_curve, dtype=np.float64)
    if len(e) < 2:
        return 0.0
    peak = np.maximum.accumulate(e)
    dd = (e - peak) / peak
    return float(np.min(dd))


def sharpe(
    equity_curve: np.ndarray,
    periods_per_year: int = _LEGACY_PERIODS_PER_YEAR,
    *,
    trades: Optional[List[dict]] = None,
    signal_bar_ms: Optional[int] = None,
) -> float:
    """
    Annualised Sharpe ratio (rf=0).

    Preferred: when `trades` contain exit timestamps, returns are bucketed
    into calendar days and annualised with sqrt(252). When unavailable but
    a `signal_bar_ms` is provided, the curve is treated as per-signal-bar
    returns and annualised by the implied bars-per-year. Otherwise the
    legacy `periods_per_year` argument is used (kept only for back-compat).
    """
    daily = None
    if trades is not None:
        daily = _daily_returns_from_trades(trades)
    if daily is not None and daily.std() > 0:
        return float(daily.mean() / daily.std() * np.sqrt(_DAYS_PER_YEAR))
    rets = _equity_to_returns(equity_curve)
    if rets.size == 0 or rets.std() == 0:
        return 0.0
    if signal_bar_ms and signal_bar_ms > 0:
        bars_per_year = (_DAYS_PER_YEAR * _MS_PER_DAY) / float(signal_bar_ms)
        return float(rets.mean() / rets.std() * math.sqrt(bars_per_year))
    return float(rets.mean() / rets.std() * math.sqrt(periods_per_year))


def sortino(
    equity_curve: np.ndarray,
    periods_per_year: int = _LEGACY_PERIODS_PER_YEAR,
    *,
    trades: Optional[List[dict]] = None,
    signal_bar_ms: Optional[int] = None,
    target: float = 0.0,
) -> float:
    """
    Sortino ratio using lower-partial-moment downside deviation:

        downside = sqrt(mean(min(0, r - target)^2))

    Annualisation mirrors `sharpe()`. The legacy implementation used
    std(negative_returns), which is mathematically *not* the LPM definition
    and overstates Sortino when there are very few losers.
    """
    daily = None
    if trades is not None:
        daily = _daily_returns_from_trades(trades)
    if daily is not None:
        rets = daily
        ann = math.sqrt(_DAYS_PER_YEAR)
    else:
        rets = _equity_to_returns(equity_curve)
        if rets.size == 0:
            return 0.0
        if signal_bar_ms and signal_bar_ms > 0:
            ann = math.sqrt(
                (_DAYS_PER_YEAR * _MS_PER_DAY) / float(signal_bar_ms)
            )
        else:
            ann = math.sqrt(periods_per_year)
    if rets.size == 0:
        return 0.0
    downside_sq = np.minimum(0.0, rets - target) ** 2
    dd_dev = float(np.sqrt(downside_sq.mean()))
    if dd_dev <= 1e-12:
        return 0.0
    return float(rets.mean() / dd_dev * ann)


def calmar(
    equity_curve: np.ndarray,
    periods_per_year: int = _LEGACY_PERIODS_PER_YEAR,
    *,
    trades: Optional[List[dict]] = None,
    signal_bar_ms: Optional[int] = None,
) -> float:
    """
    Annualised return / |MaxDD|. Returns 0 when MaxDD is zero.
    Uses CAGR when timestamps allow; otherwise mean-return * periods.
    """
    e = np.asarray(equity_curve, dtype=np.float64)
    mdd = abs(max_drawdown(e))
    if mdd <= 0:
        return 0.0
    cg = cagr(e, trades=trades)
    if cg is not None:
        return float(cg / mdd)
    rets = _equity_to_returns(e)
    if signal_bar_ms and signal_bar_ms > 0:
        bars_per_year = (_DAYS_PER_YEAR * _MS_PER_DAY) / float(signal_bar_ms)
        ann_ret = float(rets.mean() * bars_per_year)
    else:
        ann_ret = float(rets.mean() * periods_per_year)
    return float(ann_ret / mdd) if mdd > 0 else 0.0


def cagr(
    equity_curve: np.ndarray, *, trades: Optional[List[dict]] = None
) -> Optional[float]:
    """
    Compound annual growth rate over the actual date span — None when the
    timestamps aren't available or span < 1 day.
    """
    e = np.asarray(equity_curve, dtype=np.float64)
    if len(e) < 2 or e[0] <= 0 or e[-1] <= 0:
        return None
    if not trades:
        return None
    ts = [t.get("exit_ts_ms") or t.get("entry_ts_ms") for t in trades]
    ts = [int(s) for s in ts if s]
    if len(ts) < 2:
        return None
    span_ms = max(ts) - min(ts)
    if span_ms <= 0:
        return None
    years = span_ms / (_DAYS_PER_YEAR * _MS_PER_DAY)
    if years <= 0:
        return None
    return float((e[-1] / e[0]) ** (1.0 / years) - 1.0)


def ulcer_index(equity_curve: np.ndarray) -> float:
    e = np.asarray(equity_curve, dtype=np.float64)
    if len(e) < 2:
        return 0.0
    peak = np.maximum.accumulate(e)
    dd_pct = (e - peak) / peak * 100.0
    return float(np.sqrt(np.mean(dd_pct ** 2)))


def pain_ratio(
    equity_curve: np.ndarray, *, trades: Optional[List[dict]] = None,
    signal_bar_ms: Optional[int] = None,
) -> float:
    """
    Annualised return / ulcer_index. Returns 0 when ulcer is zero.
    """
    ui = ulcer_index(equity_curve)
    if ui <= 0:
        return 0.0
    cg = cagr(equity_curve, trades=trades)
    if cg is None:
        rets = _equity_to_returns(equity_curve)
        if rets.size == 0:
            return 0.0
        if signal_bar_ms and signal_bar_ms > 0:
            bars_per_year = (_DAYS_PER_YEAR * _MS_PER_DAY) / float(signal_bar_ms)
            cg = float(rets.mean() * bars_per_year)
        else:
            cg = float(rets.mean() * _LEGACY_PERIODS_PER_YEAR)
    return float(cg * 100.0 / ui)


def tail_ratio(returns_or_trades: Iterable) -> Optional[float]:
    """
    abs(95th percentile) / abs(5th percentile) over the supplied trade pnls
    (or already-computed returns array). Returns None on insufficient data.
    """
    arr = np.asarray(
        [t["pnl_pct"] if isinstance(t, dict) else float(t)
         for t in returns_or_trades], dtype=np.float64,
    )
    if arr.size < 10:
        return None
    p95 = float(np.percentile(arr, 95))
    p05 = float(np.percentile(arr, 5))
    if p05 == 0:
        return None
    return float(abs(p95) / abs(p05))


def regime_breakdown(trades: list) -> dict:
    from collections import defaultdict
    groups = defaultdict(list)
    for t in trades:
        groups[t.get("regime", "unknown")].append(t["pnl_pct"])
    out = {}
    for regime, pnls in groups.items():
        arr = np.array(pnls, dtype=np.float64)
        out[regime] = {
            "trade_count": int(len(arr)),
            "win_rate":    float(np.mean(arr > 0)) if arr.size else 0.0,
            "avg_pnl":     float(np.mean(arr)) if arr.size else 0.0,
            "sharpe_proxy": float(np.mean(arr) / arr.std())
                            if arr.size and arr.std() > 0 else 0.0,
        }
    return out


def profit_factor(trades: List[dict]) -> Optional[float]:
    """
    Profit factor = sum(winners) / |sum(losers)|.
    Conventions:
      * No trades            → None
      * Winners, no losers   → +inf  (legacy returned 0 — masking perfect run)
      * No winners, losers   → 0.0
    """
    if not trades:
        return None
    pnls = [float(t["pnl_pct"]) for t in trades]
    winners_sum = sum(p for p in pnls if p > 0)
    losers_sum  = abs(sum(p for p in pnls if p < 0))
    if losers_sum == 0:
        return float("inf") if winners_sum > 0 else 0.0
    return float(winners_sum / losers_sum)


# ── deflated Sharpe ──────────────────────────────────────────────────────────


def _phi(x: float) -> float:
    """Standard normal CDF without scipy."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def deflated_sharpe(
    observed_sharpe: float,
    n_trials: int,
    n_observations: int,
    *,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """
    Conservative deflated Sharpe probability (Lopez de Prado / Bailey).

    Returns the probability that the observed annualised Sharpe is greater
    than the maximum expected from `n_trials` independent strategies under
    the null. Monotonic:
      * More trials → harder hurdle  (lower output)
      * Higher observed Sharpe       → higher output
      * Higher n_observations        → tighter estimate, output moves
                                       toward 0 or 1 depending on sign

    Inputs are kept simple — skewness/kurtosis default to a normal returns
    assumption (0, 3) which makes the formula well-defined for synthetic
    tests. Real usage should pass sample skew/kurtosis.
    """
    if n_trials <= 0:
        n_trials = 1
    if n_observations < 2:
        return 0.0
    # Expected maximum Sharpe under the null across n_trials i.i.d. tests
    # (Bailey & Lopez de Prado 2012, simplified).
    euler_mascheroni = 0.5772156649015329
    inv_phi_first  = _inverse_normal_cdf(1.0 - 1.0 / n_trials)
    inv_phi_second = _inverse_normal_cdf(1.0 - 1.0 / (n_trials * math.e))
    sr_expected_max = (
        (1.0 - euler_mascheroni) * inv_phi_first
        + euler_mascheroni       * inv_phi_second
    )
    # Standard error of the Sharpe estimator with skew / kurt correction.
    var_term = (
        1.0
        - skewness * observed_sharpe
        + ((kurtosis - 1.0) / 4.0) * observed_sharpe ** 2
    )
    if var_term <= 0:
        var_term = 1e-9
    se = math.sqrt(var_term / max(1, (n_observations - 1)))
    if se <= 0:
        return 1.0 if observed_sharpe > sr_expected_max else 0.0
    z = (observed_sharpe - sr_expected_max) / se
    return float(_phi(z))


def _inverse_normal_cdf(p: float) -> float:
    """
    Acklam's rational approximation for the inverse standard normal CDF —
    avoids scipy. Accurate to ~1.15e-9 over (0, 1).
    """
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    a = [-3.969683028665376e+01,  2.209460984245205e+02,
         -2.759285104469687e+02,  1.383577518672690e+02,
         -3.066479806614716e+01,  2.506628277459239e+00]
    b = [-5.447609879822406e+01,  1.615858368580409e+02,
         -1.556989798598866e+02,  6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
          4.374664141464968e+00,  2.938163982698783e+00]
    d = [ 7.784695709041462e-03,  3.224671290700398e-01,
          2.445134137142996e+00,  3.754408661907416e+00]
    plow  = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
           (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)


# ── report ───────────────────────────────────────────────────────────────────


def full_report(
    equity_curve: np.ndarray,
    trades: list,
    *,
    signal_bar_ms: Optional[int] = None,
) -> PerformanceReport:
    pnls = [float(t["pnl_pct"]) for t in trades]
    winners = [p for p in pnls if p > 0]
    losers  = [p for p in pnls if p < 0]

    has_ts = any(t.get("exit_ts_ms") for t in trades)
    method = "calendar_daily" if has_ts else (
        "per_bar" if signal_bar_ms else "legacy_periods"
    )

    return PerformanceReport(
        sharpe        = sharpe(
            equity_curve, trades=trades, signal_bar_ms=signal_bar_ms,
        ),
        calmar        = calmar(
            equity_curve, trades=trades, signal_bar_ms=signal_bar_ms,
        ),
        sortino       = sortino(
            equity_curve, trades=trades, signal_bar_ms=signal_bar_ms,
        ),
        max_drawdown  = max_drawdown(equity_curve),
        win_rate      = len(winners) / len(pnls) if pnls else 0.0,
        avg_rr        = (float(np.mean(winners)) / abs(float(np.mean(losers))))
                        if (winners and losers) else 0.0,
        profit_factor = profit_factor(trades),
        total_trades  = len(trades),
        cagr          = cagr(equity_curve, trades=trades),
        ulcer_index   = ulcer_index(equity_curve),
        pain_ratio    = pain_ratio(
            equity_curve, trades=trades, signal_bar_ms=signal_bar_ms,
        ),
        tail_ratio    = tail_ratio(trades),
        sharpe_method = method,
        regime_breakdown = regime_breakdown(trades),
    )
