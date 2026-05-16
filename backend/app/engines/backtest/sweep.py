"""
Backtest robustness helpers.

 * walk_forward_split — non-leaking train/test windows over a candle series
 * param_sweep        — grid evaluation of run_backtest over a parameter dict
 * top_by             — pick the best N param sets by a chosen stat key

Pure functions; no I/O. Designed to be called from a CLI harness or notebook.
"""
from itertools import product
from typing import Dict, Iterable, List, Optional, Tuple, Any

from app.schemas.market import Candle
from app.schemas.backtest import BacktestResult
from app.engines.backtest.backtest_engine import run_backtest


def walk_forward_split(
    n_items: int,
    n_splits: int = 3,
    train_pct: float = 0.7,
    min_train: int = 50,
) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """
    Generate non-overlapping (train_range, test_range) index pairs over n_items.

    Each split takes a contiguous slice; within each slice the first `train_pct`
    is the in-sample (train) window and the rest is the held-out (test) window.
    Returns a list of ((tr_start, tr_end), (te_start, te_end)) — both end-exclusive.

    Splits with fewer than `min_train` train bars are dropped.
    """
    if n_items <= 0 or n_splits <= 0:
        return []
    slice_size = n_items // n_splits
    splits: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
    for k in range(n_splits):
        s_start = k * slice_size
        s_end   = s_start + slice_size if k < n_splits - 1 else n_items
        tr_end  = s_start + int((s_end - s_start) * train_pct)
        train   = (s_start, tr_end)
        test    = (tr_end, s_end)
        if (tr_end - s_start) >= min_train and (s_end - tr_end) >= 1:
            splits.append((train, test))
    return splits


def _slice(candles: List[Candle], rng: Tuple[int, int]) -> List[Candle]:
    s, e = rng
    return candles[s:e]


def walk_forward_run(
    underlying: str,
    candles_4h: List[Candle],
    candles_1h: List[Candle],
    n_splits: int = 3,
    train_pct: float = 0.7,
    sample_every_n_bars: int = 4,
    atm_iv: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Run a separate backtest on each train and test window. Returns a list of
    dicts: [{split, phase, sharpe, win_rate, profit_factor, ...}, ...].
    Walk-forward splits run on the 1H series; the 4H series is sliced
    proportionally so timestamps stay aligned.
    """
    n_1h = len(candles_1h)
    n_4h = len(candles_4h)
    if n_1h == 0:
        return []
    splits = walk_forward_split(n_1h, n_splits=n_splits, train_pct=train_pct)
    out: List[Dict[str, Any]] = []
    for k, (train_rng, test_rng) in enumerate(splits):
        for phase, rng in (("train", train_rng), ("test", test_rng)):
            ratio_s = rng[0] / max(1, n_1h)
            ratio_e = rng[1] / max(1, n_1h)
            c4h_slice = candles_4h[int(ratio_s * n_4h): int(ratio_e * n_4h)]
            c1h_slice = candles_1h[rng[0]: rng[1]]
            res = run_backtest(
                underlying=underlying,
                candles_4h=c4h_slice,
                candles_1h=c1h_slice,
                lookback_days=0,
                sample_every_n_bars=sample_every_n_bars,
                atm_iv=atm_iv,
            )
            out.append({
                "split": k,
                "phase": phase,
                "n_1h_bars": rng[1] - rng[0],
                "win_rate":      res.sim_win_rate,
                "expectancy":    res.sim_expectancy_pct,
                "profit_factor": res.sim_profit_factor,
                "max_drawdown":  res.sim_max_drawdown,
                "sharpe":        res.sim_sharpe,
                "trade_count":   res.sim_trade_count,
            })
    return out


def param_sweep(
    underlying: str,
    candles_4h: List[Candle],
    candles_1h: List[Candle],
    param_grid: Dict[str, Iterable[Any]],
    sample_every_n_bars: int = 4,
) -> List[Dict[str, Any]]:
    """
    Evaluate run_backtest over the cartesian product of param_grid.

    Recognised keys (others are ignored to keep the surface narrow):
      sample_every_n_bars : int
      atm_iv              : float | None
      option_dte          : int

    Returns a list of {params: {...}, stats: {...}} dicts.
    """
    keys = list(param_grid.keys())
    if not keys:
        return []
    out: List[Dict[str, Any]] = []
    for combo in product(*[list(param_grid[k]) for k in keys]):
        params = dict(zip(keys, combo))
        kwargs = {
            "sample_every_n_bars": params.get("sample_every_n_bars", sample_every_n_bars),
        }
        if "atm_iv" in params:
            kwargs["atm_iv"] = params["atm_iv"]
        if "option_dte" in params:
            kwargs["option_dte"] = params["option_dte"]

        res = run_backtest(
            underlying=underlying,
            candles_4h=candles_4h,
            candles_1h=candles_1h,
            lookback_days=0,
            **kwargs,
        )
        out.append({
            "params": params,
            "stats": {
                "win_rate":      res.sim_win_rate,
                "expectancy":    res.sim_expectancy_pct,
                "profit_factor": res.sim_profit_factor,
                "max_drawdown":  res.sim_max_drawdown,
                "sharpe":        res.sim_sharpe,
                "trade_count":   res.sim_trade_count,
            },
        })
    return out


def top_by(results: List[Dict[str, Any]], key: str = "sharpe", n: int = 5) -> List[Dict[str, Any]]:
    """Sort sweep/walk-forward results descending by stats[key]; return top N.
    Entries whose stat is None or NaN are pushed to the end."""
    def _score(r: Dict[str, Any]) -> float:
        v = r.get("stats", {}).get(key) if "stats" in r else r.get(key)
        if v is None:
            return float("-inf")
        try:
            return float(v)
        except (TypeError, ValueError):
            return float("-inf")
    return sorted(results, key=_score, reverse=True)[:n]
