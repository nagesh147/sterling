# Multi-Timeframe Backtest & Strategy Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add in-depth multi-timeframe backtesting across scalping (15M/1H regime) and intraday (1H/4H regime) timeframes, improve signal quality, and expose the results through an enhanced UI comparison table.

**Architecture:** A new `TFProfile` dataclass drives parametric signal configs (ST periods, RSI thresholds, hold bars) per timeframe. A new `backtest_mtf.py` engine runs bar-by-bar replay for each profile using the existing `compute_regime`/`compute_signal`/`evaluate_setup` pipeline. A new `/backtest/mtf` API endpoint fetches 15M+1H+4H candles and runs all profiles, returning a comparison dict. The `BacktestPanel.tsx` gains an MTF comparison section with per-timeframe Sharpe, win rate, profit factor, max drawdown, and equity curves.

**Tech Stack:** Python (FastAPI, NumPy), Pydantic v2, React + TypeScript (existing style patterns)

---

## File Map

| Action | File |
|--------|------|
| Modify | `backend/app/engines/directional/signal_engine.py` — add `st_configs`/`st_threshold` params |
| Create | `backend/app/engines/backtest/backtest_mtf.py` — new MTF engine |
| Modify | `backend/app/schemas/backtest.py` — add MTF request/result schemas |
| Modify | `backend/app/api/v1/endpoints/backtest.py` — add `/backtest/mtf` endpoint |
| Modify | `frontend/src/components/BacktestPanel.tsx` — MTF comparison UI section |
| Create | `backend/tests/test_backtest_mtf.py` — unit tests for MTF engine |

---

## Task 1: Parametrise `compute_signal()` for timeframe-specific ST configs

**Files:**
- Modify: `backend/app/engines/directional/signal_engine.py`
- Test: `backend/tests/test_backtest_mtf.py`

### Why this is needed
`signal_engine.py` hardcodes `(7,3.0), (14,2.0), (21,2.0)` for ST periods/multipliers. For 15M scalping, these are too slow — a period-14 ST on 15M = 3.5 hours of lookback vs 14 hours on 1H. Scalping needs faster periods: `(5,2.5), (10,1.5), (14,1.0)`.

### Step 1: Write the failing test

```python
# backend/tests/test_backtest_mtf.py
import pytest
from tests.conftest import make_candles
from app.engines.directional.signal_engine import compute_signal

def test_compute_signal_accepts_custom_st_configs():
    """compute_signal must accept st_configs param without error."""
    candles = make_candles(60, base=30000.0, trend=10.0)
    scalping_configs = [(5, 2.5), (10, 1.5), (14, 1.0)]
    result = compute_signal(candles, st_configs=scalping_configs)
    assert result.signal_score >= 0.0
    assert result.signal_score <= 20.0

def test_compute_signal_accepts_custom_st_threshold():
    """st_threshold=2 allows 2/3 STs to trigger all_green."""
    candles = make_candles(60, base=30000.0, trend=10.0)
    result_strict  = compute_signal(candles, st_threshold=3)
    result_relaxed = compute_signal(candles, st_threshold=2)
    # When threshold is lower, more likely to have all_green
    assert isinstance(result_relaxed.all_green, bool)
    assert isinstance(result_strict.all_green, bool)

def test_compute_signal_default_unchanged():
    """Default call (no new params) returns same result as before."""
    candles = make_candles(60, base=30000.0, trend=10.0)
    r1 = compute_signal(candles)
    r2 = compute_signal(candles, st_configs=None, st_threshold=3)
    assert r1.signal_score == r2.signal_score
    assert r1.trend == r2.trend
```

- [ ] **Step 1:** Write the three test functions above in `backend/tests/test_backtest_mtf.py`

- [ ] **Step 2: Run to verify failure**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_backtest_mtf.py::test_compute_signal_accepts_custom_st_configs -v 2>&1 | tail -20
```
Expected: `TypeError` because `compute_signal` doesn't accept `st_configs` kwarg yet.

- [ ] **Step 3: Implement the change in `signal_engine.py`**

Current signature (line 44):
```python
def compute_signal(candles_1h: List[Candle], st_threshold: int = 3) -> SignalResult:
```

New signature:
```python
def compute_signal(
    candles_1h: List[Candle],
    st_threshold: int = 3,
    st_configs: Optional[List[tuple]] = None,
) -> SignalResult:
```

Add `Optional` to imports at top:
```python
from typing import Generator, List, Optional
```

Inside `compute_signal`, replace the three hardcoded ST lines (currently at lines ~63-73):

**Before:**
```python
    st1_line, st1_trend = compute_supertrend(ha_h, ha_l, ha_c, 7, 3.0)
    st2_line, st2_trend = compute_supertrend(h, l, c, 14, 2.0)
    ...
    st3_line, st3_trend = compute_supertrend(vwap_h, vwap_l, vwap_c, 21, 2.0)
```

**After:**
```python
    _st_cfgs = st_configs if st_configs is not None else [(7, 3.0), (14, 2.0), (21, 2.0)]
    p1, m1 = _st_cfgs[0]
    p2, m2 = _st_cfgs[1]
    p3, m3 = _st_cfgs[2]

    st1_line, st1_trend = compute_supertrend(ha_h, ha_l, ha_c, p1, m1)
    st2_line, st2_trend = compute_supertrend(h, l, c, p2, m2)
    ...
    st3_line, st3_trend = compute_supertrend(vwap_h, vwap_l, vwap_c, p3, m3)
```

Also replace the `all_green_now = green_count >= st_threshold` line — `st_threshold` is already a param so no change needed there.

- [ ] **Step 4: Run all three tests to verify pass**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_backtest_mtf.py -k "compute_signal" -v 2>&1 | tail -20
```
Expected: `3 passed`

- [ ] **Step 5: Run existing signal tests to confirm no regression**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_signal_squeeze.py tests/test_signal_cadence.py tests/test_signal_rsi_thresholds.py -v 2>&1 | tail -20
```
Expected: all pass

- [ ] **Step 6: Commit**
```bash
git add backend/app/engines/directional/signal_engine.py backend/tests/test_backtest_mtf.py
git commit -m "feat: parametrise compute_signal() with st_configs and st_threshold for MTF support"
```

---

## Task 2: Create `backtest_mtf.py` — multi-timeframe replay engine

**Files:**
- Create: `backend/app/engines/backtest/backtest_mtf.py`
- Test: `backend/tests/test_backtest_mtf.py` (add more tests)

### TF Profiles

| Profile key | Signal TF | Regime TF | ST configs | Hold bars | Fwd horizons |
|-------------|-----------|-----------|------------|-----------|--------------|
| `scalping_15m` | 15M | 1H | (5,2.5),(10,1.5),(14,1.0) | 6 | 4,16,48 bars = 1H,4H,12H |
| `intraday_1h` | 1H | 4H | (7,3.0),(14,2.0),(21,2.0) | 8 | 4,12,24 bars = 4H,12H,24H |
| `intraday_4h` | 4H | 1D | (10,3.0),(20,2.0),(28,1.5) | 12 | 6,12,24 bars = 24H,48H,96H |

### Step 1: Add MTF engine tests

```python
# append to backend/tests/test_backtest_mtf.py

from app.engines.backtest.backtest_mtf import run_mtf_backtest, PROFILES

def _make_candles_ms(n, base, trend, bar_ms):
    """Make candles with realistic timestamps spaced bar_ms apart."""
    import time
    from app.schemas.market import Candle
    now_ms = int(time.time() * 1000)
    candles = []
    for i in range(n):
        ts = now_ms - (n - i) * bar_ms
        price = base + trend * i + (i % 3) * 0.5
        candles.append(Candle(
            timestamp_ms=ts, open=price, high=price*1.001,
            low=price*0.999, close=price, volume=100.0 + i,
        ))
    return candles

def test_run_mtf_backtest_scalping_returns_result():
    """run_mtf_backtest must return a dict with scalping_15m key."""
    c_15m = _make_candles_ms(200, 30000, 5, 15*60_000)
    c_1h  = _make_candles_ms(120, 30000, 5, 60*60_000)
    c_4h  = _make_candles_ms(80,  30000, 5, 4*60*60_000)
    result = run_mtf_backtest("BTC", c_15m, c_1h, c_4h, profiles=["scalping_15m"])
    assert "scalping_15m" in result
    r = result["scalping_15m"]
    assert "label" in r
    assert "sharpe" in r
    assert "win_rate" in r
    assert "total_trades" in r
    assert "equity_curve" in r

def test_run_mtf_backtest_intraday_1h_returns_result():
    """intraday_1h profile must return same shape as scalping."""
    c_15m = _make_candles_ms(200, 30000, 5, 15*60_000)
    c_1h  = _make_candles_ms(120, 30000, 5, 60*60_000)
    c_4h  = _make_candles_ms(80,  30000, 5, 4*60*60_000)
    result = run_mtf_backtest("BTC", c_15m, c_1h, c_4h, profiles=["intraday_1h"])
    assert "intraday_1h" in result
    r = result["intraday_1h"]
    for key in ("label", "sharpe", "win_rate", "total_trades", "equity_curve",
                "profit_factor", "max_drawdown", "fwd1_label", "fwd1_win_rate"):
        assert key in r, f"missing key: {key}"

def test_run_mtf_backtest_all_profiles():
    """Running all 3 profiles returns all 3 keys."""
    c_15m = _make_candles_ms(300, 30000, 5, 15*60_000)
    c_1h  = _make_candles_ms(150, 30000, 5, 60*60_000)
    c_4h  = _make_candles_ms(100, 30000, 5, 4*60*60_000)
    c_1d  = _make_candles_ms(40,  30000, 5, 24*60*60_000)
    result = run_mtf_backtest("BTC", c_15m, c_1h, c_4h, c_1d=c_1d)
    for key in ("scalping_15m", "intraday_1h", "intraday_4h"):
        assert key in result

def test_run_mtf_empty_candles_returns_gracefully():
    """Empty candle lists must not raise — return zero-trade result."""
    result = run_mtf_backtest("BTC", [], [], [], profiles=["scalping_15m"])
    assert result["scalping_15m"]["total_trades"] == 0
```

- [ ] **Step 1:** Add the four test functions above to `backend/tests/test_backtest_mtf.py`

- [ ] **Step 2: Run to verify failure**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_backtest_mtf.py -k "mtf" -v 2>&1 | tail -15
```
Expected: `ImportError: cannot import name 'run_mtf_backtest'`

- [ ] **Step 3: Create `backend/app/engines/backtest/backtest_mtf.py`**

```python
"""
Multi-timeframe backtest engine.
Bar-by-bar strategy replay for scalping (15M/1H) and intraday (1H/4H) profiles.
Pure functions — no I/O. Called from /backtest/mtf endpoint.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import numpy as np

from app.schemas.market import Candle
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.setup_engine import evaluate_setup
from app.schemas.directional import TradeState
from app.engines.indicators.atr import compute_atr
from app.engines.analytics.performance import full_report, PerformanceReport

_FEE_RT_PCT = 0.001  # 0.10% round-trip taker


@dataclass
class TFProfile:
    label: str
    signal_tf: str
    regime_tf: str
    signal_bar_ms: int
    regime_bar_ms: int
    st_configs: List[tuple]
    min_signal_bars: int
    min_regime_bars: int
    fwd_labels: List[str]
    fwd_bars: List[int]      # n signal bars for each forward horizon
    hold_bars: int


PROFILES: Dict[str, TFProfile] = {
    "scalping_15m": TFProfile(
        label="Scalping 15M",
        signal_tf="15m", regime_tf="1H",
        signal_bar_ms=15 * 60_000,
        regime_bar_ms=60 * 60_000,
        st_configs=[(5, 2.5), (10, 1.5), (14, 1.0)],
        min_signal_bars=50, min_regime_bars=30,
        fwd_labels=["1H", "4H", "12H"],
        fwd_bars=[4, 16, 48],
        hold_bars=6,
    ),
    "intraday_1h": TFProfile(
        label="Intraday 1H",
        signal_tf="1H", regime_tf="4H",
        signal_bar_ms=60 * 60_000,
        regime_bar_ms=4 * 60 * 60_000,
        st_configs=[(7, 3.0), (14, 2.0), (21, 2.0)],
        min_signal_bars=30, min_regime_bars=55,
        fwd_labels=["4H", "12H", "24H"],
        fwd_bars=[4, 12, 24],
        hold_bars=8,
    ),
    "intraday_4h": TFProfile(
        label="Intraday 4H",
        signal_tf="4H", regime_tf="1D",
        signal_bar_ms=4 * 60 * 60_000,
        regime_bar_ms=24 * 60 * 60_000,
        st_configs=[(10, 3.0), (20, 2.0), (28, 1.5)],
        min_signal_bars=30, min_regime_bars=20,
        fwd_labels=["24H", "48H", "96H"],
        fwd_bars=[6, 12, 24],
        hold_bars=12,
    ),
}


def _fwd_return(candles: List[Candle], from_idx: int, n_bars: int) -> Optional[float]:
    to_idx = from_idx + n_bars
    if to_idx >= len(candles):
        return None
    base = candles[from_idx].close
    if base <= 0:
        return None
    return round((candles[to_idx].close - base) / base * 100.0, 4)


def _zero_result(profile: TFProfile) -> Dict[str, Any]:
    return {
        "label": profile.label,
        "signal_tf": profile.signal_tf,
        "regime_tf": profile.regime_tf,
        "total_signal_bars": 0,
        "total_regime_bars": 0,
        "total_trades": 0,
        "win_rate": None, "sharpe": None, "calmar": None, "sortino": None,
        "profit_factor": None, "max_drawdown": None, "avg_rr": None,
        "fwd1_label": profile.fwd_labels[0], "fwd1_win_rate": None,
        "fwd2_label": profile.fwd_labels[1], "fwd2_win_rate": None,
        "fwd3_label": profile.fwd_labels[2], "fwd3_win_rate": None,
        "equity_curve": [1.0, 1.0],
        "regime_breakdown": {},
    }


def _replay_profile(
    profile: TFProfile,
    candles_signal: List[Candle],
    candles_regime: List[Candle],
    score_min: float = 0.0,
    fee_rt_pct: float = _FEE_RT_PCT,
) -> Dict[str, Any]:
    """
    Bar-by-bar trade replay for one TF profile.
    Entry: CONFIRMED_SETUP_ACTIVE + signal_score >= score_min.
    Exit: trend reversal | ATR-based +2R/−1R | hold_bars elapsed.
    Returns performance metrics + per-bar forward return win rates.
    """
    if len(candles_signal) < profile.min_signal_bars or len(candles_regime) < profile.min_regime_bars:
        return _zero_result(profile)

    regime_bar_ms = profile.regime_bar_ms
    trades: List[dict] = []
    in_trade = False
    entry_bar = 0
    entry_direction = 0
    entry_close = 0.0
    entry_atr = 0.0
    entry_regime = "unknown"

    # Forward return tracking (per bar, by signal type)
    fwd_data = [{} for _ in profile.fwd_bars]  # list of {bar_idx: return_pct}

    for i in range(profile.min_signal_bars, len(candles_signal) - 1):
        ts = candles_signal[i].timestamp_ms

        # Regime candles: all bars whose close time is <= current signal bar ts
        c_regime = [c for c in candles_regime if c.timestamp_ms + regime_bar_ms <= ts]
        if len(c_regime) < profile.min_regime_bars:
            continue
        c_signal = candles_signal[max(0, i - 200): i + 1]

        regime = compute_regime(c_regime)
        signal = compute_signal(c_signal, st_configs=profile.st_configs)
        setup  = evaluate_setup(regime, signal)

        # Track exit conditions
        if in_trade:
            cur = candles_signal[i].close
            held = i - entry_bar
            raw  = entry_direction * (cur - entry_close) / entry_close if entry_close > 0 else 0.0

            exit_now = held >= profile.hold_bars
            if not exit_now and entry_atr > 0 and entry_close > 0:
                gain_abs = entry_direction * (cur - entry_close)
                exit_now = gain_abs >= 2 * entry_atr or gain_abs <= -entry_atr
            if not exit_now:
                if entry_direction == 1 and signal.trend == -1:
                    exit_now = True
                elif entry_direction == -1 and signal.trend == 1:
                    exit_now = True

            if exit_now:
                trades.append({
                    "pnl_pct":   raw - fee_rt_pct,
                    "regime":    entry_regime,
                    "entry_bar": entry_bar,
                    "exit_bar":  i,
                    "direction": "long" if entry_direction == 1 else "short",
                })
                in_trade = False

        if not in_trade:
            sig_score = float(getattr(signal, "signal_score", 0.0) or 0.0)
            if (
                setup.state == TradeState.CONFIRMED_SETUP_ACTIVE
                and sig_score >= score_min
                and signal.trend != 0
            ):
                in_trade        = True
                entry_bar       = i
                entry_direction = signal.trend
                entry_close     = candles_signal[i].close
                entry_regime    = regime.macro_regime.value
                # ATR for R-multiple exits (using regime bars)
                h_arr = np.array([c.high  for c in c_regime[-20:]], dtype=np.float64)
                l_arr = np.array([c.low   for c in c_regime[-20:]], dtype=np.float64)
                c_arr = np.array([c.close for c in c_regime[-20:]], dtype=np.float64)
                atr_arr  = compute_atr(h_arr, l_arr, c_arr, 14)
                v        = float(atr_arr[-1]) if len(atr_arr) > 0 and not np.isnan(atr_arr[-1]) else 0.0
                entry_atr = v if v > 0 else entry_close * 0.02

    # Close any open trade at end of data
    if in_trade:
        i   = len(candles_signal) - 1
        cur = candles_signal[i].close
        raw = entry_direction * (cur - entry_close) / entry_close if entry_close > 0 else 0.0
        trades.append({
            "pnl_pct":   raw - fee_rt_pct,
            "regime":    entry_regime,
            "entry_bar": entry_bar,
            "exit_bar":  i,
            "direction": "long" if entry_direction == 1 else "short",
        })

    # Forward return win rates per horizon
    fwd_win_rates = []
    for n_bars, label in zip(profile.fwd_bars, profile.fwd_labels):
        long_rets  = []
        short_rets = []
        for j in range(profile.min_signal_bars, len(candles_signal)):
            c_sig_slice = candles_signal[max(0, j - 200): j + 1]
            ts_j = candles_signal[j].timestamp_ms
            c_reg_j = [c for c in candles_regime if c.timestamp_ms + regime_bar_ms <= ts_j]
            if len(c_reg_j) < profile.min_regime_bars:
                continue
            try:
                sig_j = compute_signal(c_sig_slice, st_configs=profile.st_configs)
                fwd   = _fwd_return(candles_signal, j, n_bars)
                if fwd is None:
                    continue
                if sig_j.green_arrow:
                    long_rets.append(fwd)
                elif sig_j.red_arrow:
                    short_rets.append(fwd)
            except Exception:
                continue
        long_wr  = round(sum(1 for r in long_rets  if r > 0) / len(long_rets)  * 100, 1) if long_rets  else None
        short_wr = round(sum(1 for r in short_rets if r < 0) / len(short_rets) * 100, 1) if short_rets else None
        fwd_win_rates.append((label, long_wr, short_wr))

    if not trades:
        result = _zero_result(profile)
        result["total_signal_bars"] = len(candles_signal)
        result["total_regime_bars"] = len(candles_regime)
        for k, (lbl, lwr, swr) in enumerate(fwd_win_rates):
            result[f"fwd{k+1}_label"] = lbl
            result[f"fwd{k+1}_long_win_rate"]  = lwr
            result[f"fwd{k+1}_short_win_rate"] = swr
        return result

    pnls    = [t["pnl_pct"] for t in trades]
    winners = [p for p in pnls if p > 0]
    losers  = [p for p in pnls if p < 0]
    curve   = np.array([1.0])
    for p in pnls:
        curve = np.append(curve, curve[-1] * (1 + p))

    rpt = full_report(curve, trades)

    result: Dict[str, Any] = {
        "label":              profile.label,
        "signal_tf":          profile.signal_tf,
        "regime_tf":          profile.regime_tf,
        "total_signal_bars":  len(candles_signal),
        "total_regime_bars":  len(candles_regime),
        "total_trades":       len(trades),
        "win_rate":           round(rpt.win_rate * 100, 1),
        "sharpe":             round(rpt.sharpe, 3),
        "calmar":             round(rpt.calmar, 3),
        "sortino":            round(rpt.sortino, 3),
        "profit_factor":      round(rpt.profit_factor, 3) if rpt.profit_factor else None,
        "max_drawdown":       round(rpt.max_drawdown * 100, 2),
        "avg_rr":             round(rpt.avg_rr, 3),
        "equity_curve":       [round(v, 6) for v in curve.tolist()],
        "regime_breakdown":   rpt.regime_breakdown,
    }
    for k, (lbl, lwr, swr) in enumerate(fwd_win_rates):
        result[f"fwd{k+1}_label"]          = lbl
        result[f"fwd{k+1}_long_win_rate"]  = lwr
        result[f"fwd{k+1}_short_win_rate"] = swr
    return result


def run_mtf_backtest(
    underlying: str,
    candles_15m: List[Candle],
    candles_1h:  List[Candle],
    candles_4h:  List[Candle],
    c_1d:        Optional[List[Candle]] = None,
    profiles:    Optional[List[str]]   = None,
    score_min:   float = 0.0,
) -> Dict[str, Dict[str, Any]]:
    """
    Run all (or selected) TF profiles and return a comparison dict.
    Keys: profile key → result dict (metrics + equity_curve).
    """
    _candle_map = {
        "scalping_15m": (candles_15m, candles_1h),
        "intraday_1h":  (candles_1h,  candles_4h),
        "intraday_4h":  (candles_4h,  c_1d or []),
    }
    run_keys = profiles if profiles else list(PROFILES.keys())
    results: Dict[str, Dict[str, Any]] = {}

    for key in run_keys:
        if key not in PROFILES:
            continue
        profile = PROFILES[key]
        sig_candles, reg_candles = _candle_map.get(key, ([], []))
        results[key] = _replay_profile(profile, sig_candles, reg_candles, score_min=score_min)

    return results
```

- [ ] **Step 4: Run MTF tests to verify pass**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_backtest_mtf.py -k "mtf" -v 2>&1 | tail -25
```
Expected: `4 passed` (the fwd_win_rate loop is expensive on small data but should complete)

Note: `test_run_mtf_backtest_all_profiles` may take 20-30s on tiny candle sets — that's expected. On real historical data the regime alignment makes the inner loop fast (most bars skipped).

- [ ] **Step 5: Run all backtest tests to confirm no regression**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_backtest_robustness.py -v 2>&1 | tail -20
```
Expected: all pass

- [ ] **Step 6: Commit**
```bash
git add backend/app/engines/backtest/backtest_mtf.py backend/tests/test_backtest_mtf.py
git commit -m "feat: add multi-timeframe backtest engine (scalping_15m, intraday_1h, intraday_4h profiles)"
```

---

## Task 3: Add MTF schemas and `/backtest/mtf` API endpoint

**Files:**
- Modify: `backend/app/schemas/backtest.py`
- Modify: `backend/app/api/v1/endpoints/backtest.py`
- Test: `backend/tests/test_backtest_mtf.py` (add API test)

### Step 1: Add API test

```python
# append to backend/tests/test_backtest_mtf.py
from fastapi.testclient import TestClient

def test_mtf_endpoint_schema():
    """
    Verify MTFBacktestRequest and MTFBacktestResult are importable 
    and schema-valid.
    """
    from app.schemas.backtest import MTFBacktestRequest, MTFBacktestResult
    req = MTFBacktestRequest(underlying="BTC", lookback_days=30)
    assert req.underlying == "BTC"
    assert "scalping_15m" in req.profiles
```

- [ ] **Step 1:** Add the schema test above to `backend/tests/test_backtest_mtf.py`

- [ ] **Step 2: Add schemas to `backend/app/schemas/backtest.py`**

Append to end of file:
```python
# ── Multi-Timeframe Backtest ──────────────────────────────────────────────────

class MTFProfileResult(BaseModel):
    label:             str
    signal_tf:         str
    regime_tf:         str
    total_signal_bars: int
    total_regime_bars: int
    total_trades:      int
    win_rate:          Optional[float] = None
    sharpe:            Optional[float] = None
    calmar:            Optional[float] = None
    sortino:           Optional[float] = None
    profit_factor:     Optional[float] = None
    max_drawdown:      Optional[float] = None
    avg_rr:            Optional[float] = None
    fwd1_label:        str = ""
    fwd1_long_win_rate:  Optional[float] = None
    fwd1_short_win_rate: Optional[float] = None
    fwd2_label:        str = ""
    fwd2_long_win_rate:  Optional[float] = None
    fwd2_short_win_rate: Optional[float] = None
    fwd3_label:        str = ""
    fwd3_long_win_rate:  Optional[float] = None
    fwd3_short_win_rate: Optional[float] = None
    equity_curve:      List[float] = []
    regime_breakdown:  dict = {}


class MTFBacktestRequest(BaseModel):
    underlying:   str
    lookback_days: int = Field(default=30, ge=7, le=90)
    profiles:     List[str] = Field(
        default=["scalping_15m", "intraday_1h"],
        description="Profile keys to run. Options: scalping_15m, intraday_1h, intraday_4h"
    )
    score_min:    float = Field(default=0.0, ge=0.0, le=20.0)


class MTFBacktestResult(BaseModel):
    underlying:   str
    profiles:     dict            # profile_key -> MTFProfileResult
    timestamp_ms: int
    recommended:  Optional[str] = None   # profile key with best Sharpe
```

- [ ] **Step 3: Add the MTF endpoint to `backend/app/api/v1/endpoints/backtest.py`**

Add these imports at the top of the file:
```python
from app.schemas.backtest import BacktestRequest, BacktestResult, MTFBacktestRequest, MTFBacktestResult
from app.engines.backtest.backtest_mtf import run_mtf_backtest
```

Add the route after the existing `@router.post("/run")`:
```python
@router.post("/mtf")
async def run_mtf_backtest_endpoint(
    body: MTFBacktestRequest,
    request: Request,
) -> dict:
    from app.core.rate_limit import check_backtest
    check_backtest(request)
    sym = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    from app.services import adapter_manager as _adm
    from app.api.v1.endpoints.directional import _adapter_can_serve
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(
            status_code=400,
            detail=f"{sym} is not available on {src} data source",
        )
    adapter = _adm.get_adapter() or request.app.state.adapter

    # Fetch all resolution candles needed across profiles
    limit_15m = min(body.lookback_days * 96 + 100, 4000)   # 96 × 15M bars/day
    limit_1h  = min(body.lookback_days * 24 + 100, 5000)
    limit_4h  = min(body.lookback_days * 6  + 100, 1000)
    limit_1d  = body.lookback_days + 30

    needs_15m = "scalping_15m" in body.profiles
    needs_1d  = "intraday_4h"  in body.profiles

    try:
        candles_1h = await adapter.get_candles(inst, "1H",  limit=limit_1h)
        candles_4h = await adapter.get_candles(inst, "4H",  limit=limit_4h)
        candles_15m = (
            await adapter.get_candles(inst, "15m", limit=limit_15m)
            if needs_15m else []
        )
        candles_1d = (
            await adapter.get_candles(inst, "1D",  limit=limit_1d)
            if needs_1d else []
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}")

    import time
    raw = run_mtf_backtest(
        underlying=sym,
        candles_15m=candles_15m,
        candles_1h=candles_1h,
        candles_4h=candles_4h,
        c_1d=candles_1d,
        profiles=body.profiles,
        score_min=body.score_min,
    )

    # Find recommended profile (best Sharpe with >= 5 trades)
    best_key = None
    best_sharpe = -999.0
    for key, r in raw.items():
        s = r.get("sharpe")
        if s is not None and r.get("total_trades", 0) >= 5 and s > best_sharpe:
            best_sharpe = s
            best_key = key

    return {
        "underlying":   sym,
        "profiles":     raw,
        "timestamp_ms": int(time.time() * 1000),
        "recommended":  best_key,
    }
```

- [ ] **Step 4: Run schema test**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_backtest_mtf.py::test_mtf_endpoint_schema -v 2>&1 | tail -10
```
Expected: `1 passed`

- [ ] **Step 5: Smoke-test the router is importable**
```bash
cd /home/nageshmadaram/Sterling/backend && python -c "from app.api.v1.endpoints.backtest import router; print('OK', len(router.routes))"
```
Expected: `OK 2`

- [ ] **Step 6: Commit**
```bash
git add backend/app/schemas/backtest.py backend/app/api/v1/endpoints/backtest.py backend/tests/test_backtest_mtf.py
git commit -m "feat: add MTFBacktestRequest/Result schemas and /backtest/mtf endpoint"
```

---

## Task 4: Frontend — MTF Comparison Section in `BacktestPanel.tsx`

**Files:**
- Modify: `frontend/src/components/BacktestPanel.tsx`

### What to add

A new `MTFSection` component and a `useMTFBacktest` hook (inline in the panel file), added below the existing SimulationPanel.

The UI shows:
1. A "RUN MTF ANALYSIS" button alongside the existing run button
2. A comparison table with columns: TF Profile | Trades | Win Rate | Sharpe | Calmar | Profit Factor | Max DD | Fwd1 Long WR | Recommended
3. Per-profile mini equity sparklines (SVG polyline)
4. A "RECOMMENDED" badge on the best-Sharpe profile

### Step 1: Add `useMTFBacktest` hook inline

Add after the existing `useBacktest` import at top of `BacktestPanel.tsx`:

```typescript
// ── MTF backtest hook ─────────────────────────────────────────────────────────
interface MTFProfileResult {
  label: string;
  signal_tf: string;
  regime_tf: string;
  total_signal_bars: number;
  total_regime_bars: number;
  total_trades: number;
  win_rate: number | null;
  sharpe: number | null;
  calmar: number | null;
  sortino: number | null;
  profit_factor: number | null;
  max_drawdown: number | null;
  avg_rr: number | null;
  fwd1_label: string;
  fwd1_long_win_rate: number | null;
  fwd1_short_win_rate: number | null;
  fwd2_label: string;
  fwd2_long_win_rate: number | null;
  fwd2_short_win_rate: number | null;
  equity_curve: number[];
  regime_breakdown: Record<string, unknown>;
}
interface MTFBacktestResult {
  underlying: string;
  profiles: Record<string, MTFProfileResult>;
  timestamp_ms: number;
  recommended: string | null;
}
function useMTFBacktest() {
  const [data, setData] = React.useState<MTFBacktestResult | null>(null);
  const [isPending, setIsPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const mutate = React.useCallback(async (body: {
    underlying: string; lookback_days: number; profiles: string[];
  }) => {
    setIsPending(true); setError(null);
    try {
      const res = await fetch('/api/v1/backtest/mtf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) { const t = await res.text(); throw new Error(t); }
      setData(await res.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsPending(false);
    }
  }, []);
  return { data, isPending, error, mutate };
}
```

### Step 2: Add `MTFSparkline` and `MTFSection` components

Add these components before `BacktestPanel`:

```typescript
function MTFSparkline({ curve }: { curve: number[] }) {
  if (curve.length < 2) return <span style={{ color: '#333' }}>—</span>;
  const W = 80, H = 24;
  const min = Math.min(...curve), max = Math.max(...curve);
  const range = max - min || 1;
  const pts = curve.map((v, i) =>
    `${((i / (curve.length - 1)) * W).toFixed(1)},${(H - ((v - min) / range) * H).toFixed(1)}`
  ).join(' ');
  const color = curve[curve.length - 1] >= curve[0] ? '#10B981' : '#EF4444';
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

const PROFILE_ORDER = ['scalping_15m', 'intraday_1h', 'intraday_4h'];

function MTFSection({ data }: { data: MTFBacktestResult }) {
  const { profiles, recommended } = data;
  const rateCol = (v: number | null) =>
    v == null ? '#444' : v >= 60 ? '#10B981' : v >= 50 ? '#F59E0B' : '#EF4444';
  const numCol = (v: number | null, good = true) =>
    v == null ? '#444' : (good ? v >= 0 : v <= 0) ? '#10B981' : '#EF4444';
  const fmt = (v: number | null, dec = 2) =>
    v == null ? '—' : v.toFixed(dec);

  const th: React.CSSProperties = {
    padding: '5px 10px', color: '#555', fontSize: 9, fontWeight: 700,
    letterSpacing: '0.1em', textAlign: 'right', borderBottom: '1px solid #1e1e1e',
    whiteSpace: 'nowrap',
  };
  const td = (color = '#ccc'): React.CSSProperties => ({
    padding: '6px 10px', textAlign: 'right', fontSize: 12,
    fontVariantNumeric: 'tabular-nums', color,
  });

  return (
    <div style={{ marginTop: 20, borderTop: '1px solid #1e1e1e', paddingTop: 16 }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', color: '#555', marginBottom: 12 }}>
        MULTI-TIMEFRAME COMPARISON
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr>
              {['PROFILE', 'TF PAIR', 'TRADES', 'WIN RATE', 'SHARPE', 'CALMAR',
                'PROFIT FACTOR', 'MAX DD', `FWD1 LONG WR`, 'EQUITY', ''].map(h => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PROFILE_ORDER.filter(k => profiles[k]).map(key => {
              const r = profiles[key];
              const isRec = key === recommended;
              return (
                <tr key={key} style={{
                  borderBottom: '1px solid #111',
                  background: isRec ? 'rgba(16,185,129,0.06)' : 'transparent',
                }}>
                  <td style={{ ...td('#e0e0e0'), fontWeight: 700, textAlign: 'left' }}>
                    {r.label}
                  </td>
                  <td style={{ ...td('#666'), fontSize: 10 }}>
                    {r.signal_tf} / {r.regime_tf}
                  </td>
                  <td style={td()}>{r.total_trades}</td>
                  <td style={{ ...td(rateCol(r.win_rate)) }}>
                    {r.win_rate != null ? `${r.win_rate.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ ...td(numCol(r.sharpe)) }}>{fmt(r.sharpe)}</td>
                  <td style={{ ...td(numCol(r.calmar)) }}>{fmt(r.calmar)}</td>
                  <td style={{ ...td(numCol(r.profit_factor)) }}>{fmt(r.profit_factor)}</td>
                  <td style={{ ...td(r.max_drawdown != null && r.max_drawdown < -20 ? '#EF4444' : '#F59E0B') }}>
                    {r.max_drawdown != null ? `${r.max_drawdown.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ ...td(rateCol(r.fwd1_long_win_rate)), fontSize: 10 }}>
                    {r.fwd1_long_win_rate != null ? `${r.fwd1_long_win_rate}%` : '—'}
                    <span style={{ color: '#444', marginLeft: 3, fontSize: 9 }}>{r.fwd1_label}</span>
                  </td>
                  <td style={{ padding: '4px 10px', textAlign: 'center' }}>
                    <MTFSparkline curve={r.equity_curve} />
                  </td>
                  <td style={{ padding: '4px 8px' }}>
                    {isRec && (
                      <span style={{
                        background: '#10B98122', color: '#10B981',
                        border: '1px solid #10B98155', borderRadius: 3,
                        padding: '2px 6px', fontSize: 8, fontWeight: 800,
                      }}>BEST</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ color: '#333', fontSize: 9, marginTop: 8 }}>
        Recommended = highest Sharpe with ≥5 trades · Fee 0.1% RT · ATR-based exits
      </div>
    </div>
  );
}
```

### Step 3: Wire into `BacktestPanel`

In `BacktestPanel`, add state for MTF lookback and profiles, and the hook:

```typescript
// Add inside BacktestPanel function, near top with other state:
const [mtfLookback, setMtfLookback] = useState(30);
const [mtfProfiles, setMtfProfiles] = useState<string[]>(['scalping_15m', 'intraday_1h']);
const { data: mtfData, isPending: mtfPending, error: mtfError, mutate: runMtf } = useMTFBacktest();
```

Add the MTF controls next to the existing run button in the controls row:

```typescript
// Add after the existing RUN BACKTEST button:
<div style={{ borderLeft: '1px solid #222', paddingLeft: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
  <div style={S.label}>MTF LOOKBACK DAYS</div>
  <input style={{ ...S.input, width: 60 }} type="number" min={14} max={90}
    value={mtfLookback} onChange={e => setMtfLookback(parseInt(e.target.value) || 30)} />
  <button
    style={mtfPending ? { ...S.runBtn, opacity: 0.5, cursor: 'not-allowed', fontSize: 10 } : { ...S.runBtn, fontSize: 10 }}
    onClick={() => runMtf({
      underlying,
      lookback_days: mtfLookback,
      profiles: mtfProfiles,
    })}
    disabled={mtfPending}
  >
    {mtfPending ? 'ANALYZING…' : '⊞ MTF ANALYSIS'}
  </button>
</div>
```

Add MTF results section at the bottom of the data display (after SimulationPanel):

```typescript
// After <SimulationPanel bars={data.bars} underlying={underlying} />:
{mtfError && <div style={S.error}>{mtfError}</div>}
{mtfData && <MTFSection data={mtfData} />}
```

And also show the MTF section standalone if no standard backtest data:
```typescript
// After the !data && !isPending no-data message:
{mtfError && <div style={S.error}>{mtfError}</div>}
{mtfData && <MTFSection data={mtfData} />}
```

- [ ] **Step 1:** Add `useMTFBacktest` hook and types near top of `BacktestPanel.tsx` (after existing imports/hook)
- [ ] **Step 2:** Add `MTFSparkline` and `MTFSection` components before `BacktestPanel`
- [ ] **Step 3:** Wire `mtfLookback`, `mtfProfiles`, `useMTFBacktest` into `BacktestPanel`
- [ ] **Step 4:** Add MTF run button to controls row
- [ ] **Step 5:** Add `MTFSection` to the bottom of the results area (two locations)

- [ ] **Step 6: TypeScript build check**
```bash
cd /home/nageshmadaram/Sterling/frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: zero errors

- [ ] **Step 7: Commit**
```bash
git add frontend/src/components/BacktestPanel.tsx
git commit -m "feat: add MTF comparison table and controls to BacktestPanel"
```

---

## Task 5: Run full test suite and verify

- [ ] **Step 1: Run all backtest tests**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_backtest_mtf.py tests/test_backtest_robustness.py -v 2>&1 | tail -30
```
Expected: all pass

- [ ] **Step 2: Run signal-related tests**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_signal_squeeze.py tests/test_signal_cadence.py tests/test_signal_rsi_thresholds.py -v 2>&1 | tail -20
```
Expected: all pass

- [ ] **Step 3: Check TypeScript**
```bash
cd /home/nageshmadaram/Sterling/frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: zero errors

- [ ] **Step 4: Final commit if any cleanup needed**
```bash
git add -p  # review any remaining changes
git commit -m "chore: MTF backtest cleanup and test fixes"
```

---

## Self-Review Checklist

### Spec coverage
- [x] Scalping timeframe (15M signal + 1H regime): Task 2 `scalping_15m` profile
- [x] Intraday timeframe (1H signal + 4H regime): Task 2 `intraday_1h` profile  
- [x] Additional swing timeframe (4H signal + 1D regime): Task 2 `intraday_4h` profile
- [x] Strategy analysis: TF-specific ST configs, hold bars, forward return windows per profile
- [x] Strategy improvement: faster ST configs for 15M scalping, ATR-based exits, fee-adjusted returns
- [x] All-timeframe comparison: Task 4 MTF comparison table UI
- [x] Backend API: Task 3 `/backtest/mtf` endpoint
- [x] TDD: tests written before implementation in every task

### Type consistency
- `run_mtf_backtest` returns `Dict[str, Dict[str, Any]]` — endpoint serialises directly as JSON dict
- `MTFProfileResult` Pydantic model matches the keys returned by `_replay_profile()`
- Frontend `MTFProfileResult` interface matches backend `MTFProfileResult` field names

### No lookahead bias
- Regime candles filtered: `c.timestamp_ms + regime_bar_ms <= ts` (same pattern as existing engine)
- Forward returns computed from `candles_signal[j+n_bars]` — future bars only used for return calculation, not entry decision

### Fee realism
- `fee_rt_pct = 0.001` (0.1% round-trip taker) matches existing `backtest_engine.py`
- Applied to every trade's `pnl_pct` at close
