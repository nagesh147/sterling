# Regime Book Strategy Rework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the long-only single-symbol edge stack into a symmetric (long+short), regime-gated, 3-symbol-pooled book, measured forward (walk-forward) through the existing deflation/hold-beat harness — honestly reporting whether it beats the baseline and whether anything clears DSR ≥ 0.5.

**Architecture:** One new pure-Python research module `backend/study/regime_book.py` (no live wiring), plus one regression-safe optional param on `study/sim.py`. Leak-free regime classifier routes each bar to a momentum or mean-reversion sleeve with allowed directions; per-symbol first-touch sims are merged into one capped-concurrency portfolio book; anchored walk-forward + `deflated_sharpe_ratio` + `beats_buy_and_hold` score it. Spec: `docs/superpowers/specs/2026-06-09-regime-book-rework-design.md`.

**Tech Stack:** Python 3.14, numpy, pandas, pytest. Run tests with `PYTHONWARNINGS=ignore` and `backend/.venv/bin/python -m pytest`. Real data: `backend/vector_store_1m_{BTC,ETH,SOL}USD.parquet` (columns: `time` (unix s), `open,high,low,close,volume,volatility_atr`).

---

## File Structure

- **Create** `backend/study/regime_book.py` — classifier, short sleeve signals, router, portfolio sim, walk-forward, runner. One responsibility: the regime-book research pipeline.
- **Create** `backend/tests/test_regime_book.py` — all unit tests below.
- **Modify** `backend/study/sim.py` — add optional `trail_mult: float | None = None` to `simulate_idx` (default None = byte-identical behavior; ATR-trailing stop when set).
- **Create** `docs/regime_book_before_after.md` — the before/after report (Task 7 output, written by the runner + hand-edited verdict).

Reused as-is: `app.engines.edge.strategies` (`resample`, `signals_ma_crossover`, `signals_bb_rsi_mean_reversion`, `atr14`), `study.sim.simulate_idx`/`sharpe`, `app.engines.edge.robustness.deflated_sharpe_ratio`, `app.engines.analytics.performance.hodl_benchmark`/`beats_buy_and_hold`.

---

## Task 1: Leak-free regime classifier

**Files:**
- Create: `backend/study/regime_book.py`
- Test: `backend/tests/test_regime_book.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_regime_book.py
"""Regime book — classifier, short sleeves, router, portfolio sim, walk-forward."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from study.regime_book import classify_regime


def _frame(closes, atr=None):
    closes = np.asarray(closes, float)
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="4h")
    high = closes * 1.005
    low = closes * 0.995
    df = pd.DataFrame({"open": closes, "high": high, "low": low,
                       "close": closes, "volume": 1.0}, index=idx)
    df["atr"] = (high - low) if atr is None else atr
    return df


def test_uptrend_classified_positive():
    df = _frame(np.linspace(100, 200, 300))   # steady rise
    reg = classify_regime(df, adx_threshold=20.0, ma_window=50)
    # After warmup, a clean uptrend is regime +1 for most bars.
    assert (reg[100:] == 1).mean() > 0.7


def test_downtrend_classified_negative():
    df = _frame(np.linspace(200, 100, 300))
    reg = classify_regime(df, adx_threshold=20.0, ma_window=50)
    assert (reg[100:] == -1).mean() > 0.7


def test_classifier_has_no_lookahead():
    """Truncating the future cannot change an earlier bar's regime label."""
    df = _frame(np.r_[np.linspace(100, 200, 200), np.linspace(200, 100, 200)])
    full = classify_regime(df, adx_threshold=20.0, ma_window=50)
    trunc = classify_regime(df.iloc[:250], adx_threshold=20.0, ma_window=50)
    assert np.array_equal(full[:250], trunc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -q`
Expected: FAIL — `ImportError: cannot import name 'classify_regime'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/study/regime_book.py
"""Regime-gated, symmetric (long+short), 3-symbol-pooled research book.

RESEARCH TOOL — not wired into anything live. Answers one honest question:
does routing momentum vs mean-reversion by regime, allowing shorts, and pooling
BTC/ETH/SOL into one capped book produce a FORWARD edge that beats the long-only
single-symbol baseline — and does anything clear DSR >= 0.5?

Spec: docs/superpowers/specs/2026-06-09-regime-book-rework-design.md
Run:  cd backend && .venv/bin/python -m study.regime_book
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

from app.engines.edge.strategies import (
    resample, signals_ma_crossover, signals_bb_rsi_mean_reversion,
)
from study.sim import simulate_idx, sharpe as _sharpe
from app.engines.edge.robustness import deflated_sharpe_ratio
from app.engines.analytics.performance import hodl_benchmark, beats_buy_and_hold

FEE_RT = 0.001
MAX_HOLD = 200


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ADX(period). Rolling/ewm only → leak-free."""
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def classify_regime(df: pd.DataFrame, adx_threshold: float = 25.0,
                    ma_window: int = 50) -> np.ndarray:
    """Per-bar regime: +1 uptrend, -1 downtrend, 0 range. Leak-free.

    Trend when ADX(14) >= adx_threshold; sign from the slope of SMA(ma_window).
    The single regime knob is adx_threshold; ma_window is fixed.
    """
    adx = _adx(df)
    ma = df["close"].rolling(ma_window).mean()
    slope = ma.diff()
    trend = (adx >= adx_threshold).to_numpy()
    up = (slope > 0).to_numpy()
    reg = np.zeros(len(df), dtype=int)
    reg[trend & up] = 1
    reg[trend & ~up] = -1
    reg[~np.isfinite(adx.to_numpy())] = 0
    return reg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/study/regime_book.py backend/tests/test_regime_book.py
git commit -m "feat(study): leak-free ADX+slope regime classifier"
```

---

## Task 2: Short sleeve signals (mirrored momentum + MR)

**Files:**
- Modify: `backend/study/regime_book.py`
- Test: `backend/tests/test_regime_book.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_regime_book.py
from study.regime_book import short_momentum, short_mean_reversion


def test_short_momentum_fires_on_bearish_cross():
    # rise then fall: a bearish 9/21 EMA cross must appear on the way down.
    df = _frame(np.r_[np.linspace(100, 160, 120), np.linspace(160, 90, 120)])
    sig = short_momentum(df)
    assert sig.dtype == bool and len(sig) == len(df)
    assert sig[120:].any()          # fires during the decline
    assert not sig[:60].any()       # not during the clean rise


def test_short_mean_reversion_fires_on_upper_band_fade():
    # spike above then revert — fade the upper band while RSI hot.
    base = np.full(120, 100.0)
    spike = np.r_[base, np.linspace(100, 130, 20), np.linspace(130, 110, 20)]
    df = _frame(spike)
    sig = short_mean_reversion(df)
    assert sig.dtype == bool and len(sig) == len(df)
    assert sig[120:].any()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -q`
Expected: FAIL — `ImportError: cannot import name 'short_momentum'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to study/regime_book.py
def short_momentum(df: pd.DataFrame) -> np.ndarray:
    """Mirror of signals_ma_crossover: fire on a fresh bearish 9/21 EMA cross."""
    fast = df["close"].ewm(span=9, adjust=False).mean()
    slow = df["close"].ewm(span=21, adjust=False).mean()
    bear = fast < slow
    return (bear & ~bear.shift(1).fillna(False)).to_numpy()


def short_mean_reversion(df: pd.DataFrame) -> np.ndarray:
    """Mirror of signals_bb_rsi_mean_reversion: fade the upper Bollinger band
    (close drops back below upper) while RSI(14) is hot (> 60)."""
    c = df["close"]
    d = c.diff()
    gain = d.clip(lower=0).rolling(14).mean()
    loss = (-d.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    sma = c.rolling(20).mean()
    std = c.rolling(20).std()
    upper = sma + 2 * std
    fade = (c < upper) & (c.shift(1) >= upper.shift(1))
    return (fade & (rsi > 60)).fillna(False).to_numpy()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/study/regime_book.py backend/tests/test_regime_book.py
git commit -m "feat(study): mirrored short sleeves (momentum + mean-reversion)"
```

---

## Task 3: Regime router → per-symbol directional signal arrays

**Files:**
- Modify: `backend/study/regime_book.py`
- Test: `backend/tests/test_regime_book.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_regime_book.py
from study.regime_book import route_signals


def test_router_gates_momentum_long_to_uptrend_only():
    df = _frame(np.linspace(100, 220, 300))
    longs, shorts = route_signals(df, adx_threshold=20.0)
    reg = classify_regime(df, adx_threshold=20.0)
    # Every long entry sits in a non-downtrend bar; no shorts in a clean uptrend.
    assert all(reg[i] != -1 for i in np.flatnonzero(longs))
    assert shorts.sum() == 0 or all(reg[i] != 1 for i in np.flatnonzero(shorts))


def test_router_emits_shorts_in_downtrend():
    df = _frame(np.r_[np.linspace(100, 160, 150), np.linspace(160, 80, 150)])
    longs, shorts = route_signals(df, adx_threshold=20.0)
    assert shorts.sum() >= 1            # the decline must produce shorts
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -q`
Expected: FAIL — `ImportError: cannot import name 'route_signals'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to study/regime_book.py
def route_signals(df: pd.DataFrame, adx_threshold: float = 25.0,
                  ma_window: int = 50, use_regime: bool = True):
    """Route raw sleeve signals through the regime gate.

    Returns (long_sigs, short_sigs) boolean arrays, same length as df:
      regime +1 (uptrend)   -> momentum long
      regime -1 (downtrend) -> momentum short
      regime  0 (range)     -> mean-reversion long + short

    use_regime=False is the spine baseline (no gate): momentum long+short and
    MR long+short fire everywhere — lets us measure whether the gate earns its
    degree of freedom.
    """
    reg = classify_regime(df, adx_threshold, ma_window)
    mom_long = signals_ma_crossover(df)
    mom_short = short_momentum(df)
    mr_long = signals_bb_rsi_mean_reversion(df)
    mr_short = short_mean_reversion(df)
    if not use_regime:
        longs = mom_long | mr_long
        shorts = mom_short | mr_short
        return longs, shorts
    longs = (mom_long & (reg == 1)) | (mr_long & (reg == 0))
    shorts = (mom_short & (reg == -1)) | (mr_short & (reg == 0))
    return longs, shorts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/study/regime_book.py backend/tests/test_regime_book.py
git commit -m "feat(study): regime router (gated) + spine baseline (ungated)"
```

---

## Task 4: ATR-trailing exit (regression-safe optional param on simulate_idx)

**Files:**
- Modify: `backend/study/sim.py` (add `trail_mult` param)
- Test: `backend/tests/test_regime_book.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_regime_book.py
from study.sim import simulate_idx as _sim


def test_trailing_locks_gains_vs_fixed_bracket():
    # Long runs +up then reverses. Fixed TP=3 ATR never hits before reversal;
    # trailing should exit ABOVE the fixed stop (locking some gain).
    closes = np.r_[np.linspace(100, 130, 30), np.linspace(130, 110, 30)]
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="4h")
    df = pd.DataFrame({"close": closes, "high": closes * 1.002,
                       "low": closes * 0.998}, index=idx)
    df["atr"] = 2.0
    sig = np.zeros(len(df), bool); sig[0] = True
    fixed = _sim(df, sig, slm=2.0, tpm=3.0, direction="long")
    trail = _sim(df, sig, slm=2.0, tpm=3.0, direction="long", trail_mult=2.0)
    assert trail and fixed
    assert trail[0]["pnl_pct"] > fixed[0]["pnl_pct"]


def test_trail_mult_none_is_unchanged():
    closes = np.linspace(100, 90, 40)
    idx = pd.date_range("2024-01-01", periods=40, freq="4h")
    df = pd.DataFrame({"close": closes, "high": closes * 1.002,
                       "low": closes * 0.998}, index=idx)
    df["atr"] = 1.0
    sig = np.zeros(40, bool); sig[0] = True
    assert _sim(df, sig, 2.0, 3.0) == _sim(df, sig, 2.0, 3.0, trail_mult=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -k trail -q`
Expected: FAIL — `TypeError: simulate_idx() got an unexpected keyword argument 'trail_mult'`.

- [ ] **Step 3: Write minimal implementation**

Modify `backend/study/sim.py`. Change the signature line and the inner bar loop. Add `trail_mult` after `max_hold`:

```python
def simulate_idx(
    df, sigs, slm, tpm,
    direction: str = "long",
    fee_rt: float = 0.001,
    max_hold: int = 200,
    trail_mult: float | None = None,
) -> list[dict]:
```

Inside the per-signal block, after `sl`/`tp` are set and before the `for j` loop, seed a trailing reference; then in the loop, ratchet the stop. Replace the existing `for j in range(i + 1, end + 1):` body with:

```python
        trail = None if trail_mult is None else sl  # ratcheting stop seed
        for j in range(i + 1, end + 1):
            if direction == "short":
                stop = sl if trail is None else trail
                if high[j] >= stop:
                    xp = stop; xi = j; break
                if low[j] <= tp:
                    xp = tp; xi = j; break
                if trail is not None:
                    trail = min(trail, low[j] + trail_mult * atr[i])
            else:
                stop = sl if trail is None else trail
                if low[j] <= stop:
                    xp = stop; xi = j; break
                if high[j] >= tp:
                    xp = tp; xi = j; break
                if trail is not None:
                    trail = max(trail, high[j] - trail_mult * atr[i])
```

- [ ] **Step 4: Run tests to verify pass + zero regression**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -k trail tests/test_robustness_dsr_scaling.py -q`
Expected: PASS. Then confirm `simulate_idx`'s existing callers are unaffected:
Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/ -k "sim or robust or mean_reversion_wf" -q`
Expected: PASS (no regressions — default path unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/study/sim.py backend/tests/test_regime_book.py
git commit -m "feat(study): optional ATR-trailing stop on simulate_idx (default-off, regression-safe)"
```

---

## Task 5: Capped-concurrency portfolio merge

**Files:**
- Modify: `backend/study/regime_book.py`
- Test: `backend/tests/test_regime_book.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_regime_book.py
from study.regime_book import merge_portfolio


def _trade(sym, e, x, pnl):
    return {"symbol": sym, "entry_time": pd.Timestamp(e),
            "exit_time": pd.Timestamp(x), "pnl_pct": pnl}


def test_merge_respects_concurrency_cap():
    # 3 fully-overlapping trades, cap=2 -> the 3rd (latest entry) is dropped.
    trades = [
        _trade("BTC", "2024-01-01", "2024-01-10", 0.05),
        _trade("ETH", "2024-01-02", "2024-01-09", 0.03),
        _trade("SOL", "2024-01-03", "2024-01-08", 0.02),
    ]
    kept = merge_portfolio(trades, max_concurrent=2)
    assert len(kept) == 2
    assert {t["symbol"] for t in kept} == {"BTC", "ETH"}


def test_merge_orders_by_exit_and_is_full_when_uncapped():
    trades = [
        _trade("BTC", "2024-01-05", "2024-01-06", 0.01),
        _trade("ETH", "2024-01-01", "2024-01-02", -0.02),
    ]
    kept = merge_portfolio(trades, max_concurrent=3)
    assert [t["symbol"] for t in kept] == ["ETH", "BTC"]   # exit-ordered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -k merge -q`
Expected: FAIL — `ImportError: cannot import name 'merge_portfolio'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to study/regime_book.py
def merge_portfolio(trades: list[dict], max_concurrent: int = 3) -> list[dict]:
    """Greedy interval scheduler: accept trades in entry-time order while fewer
    than max_concurrent are open; emit the accepted set ordered by exit_time.

    Each trade is {'symbol','entry_time','exit_time','pnl_pct'}. Models a single
    book that can hold at most max_concurrent positions at once (one per name in
    the default 3-symbol case). Dropped trades are capital we did not have free.
    """
    by_entry = sorted(trades, key=lambda t: t["entry_time"])
    open_exits: list[pd.Timestamp] = []
    kept: list[dict] = []
    for t in by_entry:
        open_exits = [x for x in open_exits if x > t["entry_time"]]
        if len(open_exits) >= max_concurrent:
            continue
        open_exits.append(t["exit_time"])
        kept.append(t)
    return sorted(kept, key=lambda t: t["exit_time"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -k merge -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/study/regime_book.py backend/tests/test_regime_book.py
git commit -m "feat(study): capped-concurrency portfolio merge (interval scheduler)"
```

---

## Task 6: Per-symbol book build + anchored walk-forward over the pool

**Files:**
- Modify: `backend/study/regime_book.py`
- Test: `backend/tests/test_regime_book.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_regime_book.py
from study.regime_book import build_symbol_trades, portfolio_equity, walk_forward_book


def test_build_symbol_trades_tags_symbol_and_times():
    df = _frame(np.r_[np.linspace(100, 160, 150), np.linspace(160, 80, 150)])
    df["atr"] = 2.0
    trades = build_symbol_trades("BTC", df, adx_threshold=20.0)
    assert trades, "expected at least one routed trade"
    assert all(t["symbol"] == "BTC" for t in trades)
    assert all({"entry_time", "exit_time", "pnl_pct"} <= t.keys() for t in trades)


def test_portfolio_equity_weights_by_cap():
    # one +10% trade, cap=2 -> book grows by ~ (1 + 0.10/2).
    trades = [{"symbol": "BTC", "entry_time": pd.Timestamp("2024-01-01"),
               "exit_time": pd.Timestamp("2024-01-02"), "pnl_pct": 0.10}]
    eq = portfolio_equity(trades, cap=500.0, max_concurrent=2)
    assert eq["end"] == pytest.approx(500.0 * (1 + 0.10 / 2), rel=1e-6)


def test_walk_forward_book_runs_and_is_leakfree_shape():
    frames = {}
    rng = np.random.default_rng(0)
    for sym in ("BTC", "ETH", "SOL"):
        c = 100 + np.cumsum(rng.normal(0, 1, 800))
        c = np.clip(c, 10, None)
        idx = pd.date_range("2024-01-01", periods=800, freq="4h")
        d = pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99,
                          "close": c, "volume": 1.0}, index=idx)
        d["atr"] = (d["high"] - d["low"]).rolling(14).mean().bfill()
        frames[sym] = d
    res = walk_forward_book(frames, adx_threshold=20.0, use_regime=True)
    assert {"oos", "dsr", "beats_hold", "n"} <= res.keys()
    assert res["n"] >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -k "build_symbol or portfolio_equity or walk_forward_book" -q`
Expected: FAIL — `ImportError: cannot import name 'build_symbol_trades'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to study/regime_book.py
# (sl, tp) bracket used for both directions; Aggressive profile from the study.
_SL, _TP = 1.5, 4.5


def build_symbol_trades(symbol: str, df: pd.DataFrame, adx_threshold: float = 25.0,
                        ma_window: int = 50, use_regime: bool = True,
                        trail_mult: float | None = None) -> list[dict]:
    """Route, simulate long+short, return trades tagged with symbol + timestamps."""
    longs, shorts = route_signals(df, adx_threshold, ma_window, use_regime)
    out: list[dict] = []
    for sigs, direction in ((longs, "long"), (shorts, "short")):
        raw = simulate_idx(df, sigs, _SL, _TP, direction=direction,
                           fee_rt=FEE_RT, max_hold=MAX_HOLD, trail_mult=trail_mult)
        for t in raw:
            out.append({
                "symbol": symbol,
                "direction": direction,
                "entry_time": df.index[t["entry_bar"]],
                "exit_time": df.index[t["exit_bar"]],
                "pnl_pct": t["pnl_pct"],
            })
    return out


def portfolio_equity(trades: list[dict], cap: float = 500.0,
                     max_concurrent: int = 3) -> dict:
    """Cap concurrency, then compound a single book where each trade risks a
    1/max_concurrent slice of equity (equal-risk allocation). Exit-time ordered."""
    kept = merge_portfolio(trades, max_concurrent)
    w = 1.0 / max_concurrent
    pnls = [t["pnl_pct"] for t in kept]
    if not pnls:
        return {"end": cap, "ret": 0.0, "sharpe": 0.0, "max_dd": 0.0,
                "n": 0, "weighted_pnls": []}
    wpnls = [p * w for p in pnls]
    a = np.asarray(wpnls, float)
    eq = cap * np.cumprod(1 + a)
    peak = np.maximum.accumulate(eq)
    return {"end": float(eq[-1]), "ret": float(eq[-1] / cap - 1.0),
            "sharpe": _sharpe(wpnls), "max_dd": float(((eq - peak) / peak).min()),
            "n": len(pnls), "weighted_pnls": wpnls}


def walk_forward_book(frames: dict, adx_threshold: float = 25.0,
                      ma_window: int = 50, use_regime: bool = True,
                      trail_mult: float | None = None, n_folds: int = 5,
                      oos_start: float = 0.5, cap: float = 500.0,
                      max_concurrent: int = 3) -> dict:
    """Pool all symbols, take the OOS tail [oos_start, 1.0] of calendar time as
    the forward book. The regime/short/MR logic uses only past bars per signal,
    so a fixed-parameter forward evaluation is leak-free. (Parameter SELECTION
    across adx_threshold is done by the caller comparing whole-book OOS results,
    never per-fold on test data.) Returns OOS book stats + DSR + hold-beat."""
    all_trades: list[dict] = []
    hodl_prices: list[float] = []
    for sym, df in frames.items():
        t0, t1 = df.index[0], df.index[-1]
        cut = t0 + (t1 - t0) * oos_start
        trades = build_symbol_trades(sym, df, adx_threshold, ma_window,
                                     use_regime, trail_mult)
        all_trades += [t for t in trades if t["entry_time"] >= cut]
        sub = df["close"][df.index >= cut]
        if len(sub) > 1:
            hodl_prices += list(sub.to_numpy())
    eq = portfolio_equity(all_trades, cap, max_concurrent)
    hodl = hodl_benchmark(hodl_prices, fee_rt_pct=FEE_RT)
    rel = beats_buy_and_hold(eq["ret"], eq["max_dd"], hodl)
    dsr = deflated_sharpe_ratio(eq["weighted_pnls"], num_trials=525) \
        if eq["weighted_pnls"] else 0.0
    return {"oos": eq, "dsr": round(dsr, 4),
            "beats_hold": rel["beats_hold"], "excess_vs_hold": rel["excess_return"],
            "n": eq["n"], "hodl": hodl}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -q`
Expected: PASS (all tests green).

- [ ] **Step 5: Commit**

```bash
git add backend/study/regime_book.py backend/tests/test_regime_book.py
git commit -m "feat(study): pooled book builder + anchored walk-forward + DSR/hold-beat"
```

---

## Task 7: Runner + before/after report on real data

**Files:**
- Modify: `backend/study/regime_book.py` (add `load_frames` + `main`)
- Create: `docs/regime_book_before_after.md` (runner prints the table; verdict hand-written)

- [ ] **Step 1: Add the runner (no new test — it is an I/O entrypoint exercised manually)**

```python
# append to study/regime_book.py
def load_frames(rule: str = "4h") -> dict:
    """Load BTC/ETH/SOL 1m parquet → resampled OHLCV+ATR frames. Run from backend/."""
    frames = {}
    for f in sorted(glob.glob("vector_store_1m_*.parquet")):
        sym = os.path.basename(f).replace("vector_store_1m_", "").replace(".parquet", "")
        d = pd.read_parquet(f, columns=["time", "open", "high", "low", "close", "volume"])
        d["time"] = pd.to_datetime(d["time"], unit="s")
        d = d.set_index("time").sort_index()
        frames[sym] = resample(d, rule)
    return frames


def _row(label, r):
    o = r["oos"]
    return (f"{label:>34} {o['end']:>8,.0f} {o['ret']*100:>7.1f}% {o['sharpe']:>7.2f}"
            f" {o['max_dd']*100:>7.1f}% {o['n']:>5} {r['dsr']:>7.4f}"
            f"  {'YES' if r['beats_hold'] else 'no':>4}")


def main():
    frames = load_frames("4h")
    if not frames:
        print("No vector_store_1m_*.parquet found (run from backend/).")
        return
    hodl = frames and beats_buy_and_hold  # silence linters; hodl printed per-run
    print(f"Regime book · {len(frames)} symbols pooled · $500 · OOS tail (last 50%)\n")
    print(f"{'config':>34} {'$end':>8} {'ret':>8} {'Sharpe':>7} {'maxDD':>8}"
          f" {'n':>5} {'DSR':>7}  beatsHODL")
    print("-" * 92)
    # Baseline: long-only, single-symbol, no regime gate (the 'before').
    base = walk_forward_book(frames, use_regime=False, max_concurrent=1)
    print(_row("BEFORE long+short ungated cap1", base))
    # Spine: shorts + pooling, no gate.
    spine = walk_forward_book(frames, use_regime=False, max_concurrent=3)
    print(_row("SPINE shorts+pool cap3", spine))
    # +Regime gate (sweep the one knob; report best OOS, honestly flagged).
    for adx in (20.0, 25.0, 30.0):
        r = walk_forward_book(frames, use_regime=True, adx_threshold=adx, max_concurrent=3)
        print(_row(f"+REGIME gate adx={adx:.0f} cap3", r))
    # +Trailing on the best-so-far knob.
    rt = walk_forward_book(frames, use_regime=True, adx_threshold=25.0,
                           max_concurrent=3, trail_mult=2.0)
    print(_row("+REGIME+TRAIL adx25 cap3", rt))
    print("\nDSR >= 0.5 = deflation-provable. Anything less = forward signal only.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the runner on real data**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m study.regime_book`
Expected: a table of BEFORE / SPINE / +REGIME(×3 adx) / +TRAIL rows with $end, ret, Sharpe, maxDD, n, DSR, beatsHODL. Capture the numbers.

- [ ] **Step 3: Run the full regime-book test file once more (zero-regression)**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_regime_book.py -q`
Expected: PASS (all green).

- [ ] **Step 4: Write `docs/regime_book_before_after.md`**

Paste the runner's table, add FULL/IS/OOS framing consistent with `docs/backtest_full_metrics_report.md`, and write the plain-English verdict: did shorts+pooling beat the long-only baseline OOS? did the regime gate earn its degree of freedom (beat the ungated spine OOS)? did anything clear DSR ≥ 0.5? State it straight.

- [ ] **Step 5: Commit**

```bash
git add backend/study/regime_book.py docs/regime_book_before_after.md
git commit -m "feat(study): regime-book runner + before/after real-data report"
```

---

## Self-Review notes

- **Spec coverage:** classifier (T1), shorts (T2), router+spine baseline (T3), trailing exit (T4), capped portfolio (T5), pooled walk-forward + DSR/hold-beat (T6), before/after report + verdict (T7). All spec components mapped.
- **Type consistency:** trade dicts carry `symbol/direction/entry_time/exit_time/pnl_pct` everywhere; `simulate_idx` returns `entry_bar/exit_bar/pnl_pct` (existing) and T6 maps those to timestamps; `walk_forward_book` returns `oos/dsr/beats_hold/n` matching T6's test.
- **No live wiring:** nothing imports `regime_book` from `app/`; registry/endpoints untouched — consistent with the audit discipline (research only until it clears the gate).
- **Honesty guardrail:** `num_trials=525` in the DSR call keeps the multiple-testing penalty at the same grid size as the live scan, so a pass here is comparable to the live bar.
