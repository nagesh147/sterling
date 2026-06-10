# Funding-Carry Sleeve Spike — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test whether a funding-rate positioning-tilt sleeve adds *independent* information past the correlation wall that capped the conviction book at DSR 0.166 — measured through the existing `simulate_idx`/`portfolio_equity_sized`/`deflated_sharpe_ratio` harness, with a pre-registered kill/fold bar.

**Architecture:** Two new isolated modules under `backend/study/` (research-only, nothing wired live). `funding_pipeline.py` fetches Binance USDⓈ-M perp funding history (stdlib urllib, same shape as `ohlcv_pipeline.py`). `funding_sleeve.py` turns funding into a leak-free contrarian z-score signal, runs it through the **existing** `simulate_idx` fill engine with the real funding cash-flow added per held bar, then pools its trades with the conviction book's trades into the **existing** per-trade book machinery so combined Sharpe/DSR stay directly comparable to the book's 1.15 / 0.166.

**Tech Stack:** Python 3, pandas, numpy, pytest. Reuses `study.sim.simulate_idx`, `study.regime_book.{merge_portfolio, portfolio_equity_sized, select_conviction_book, _spearman}`, `app.engines.edge.robustness.deflated_sharpe_ratio`, `study.ohlcv_pipeline.load_universe`.

**Run convention:** from `backend/`. Tests: `PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_*.py -q`. Network steps gated behind `STERLING_NET_TESTS=1`.

---

## Combination model (reconciliation with the spec)

Reading the harness showed the book's Sharpe (1.15) and DSR (0.166) are **per-trade** quantities (`portfolio_equity_sized` → `_sharpe` → `deflated_sharpe_ratio`). To keep the combined numbers directly comparable, the combination pools both sleeves' trades into the **same per-trade machinery** rather than blending per-period return series (the spec's looser phrasing). Concretely:

- Book trades keep names `BTCUSD/ETHUSD/SOLUSD`; funding trades get distinct names `BTC_FUND/ETH_FUND/SOL_FUND`.
- **Combined** = pool(book_oos_trades + funding_oos_trades) → `merge_portfolio(cap=6)` → `portfolio_equity_sized`. Cap 6 lets both 3-name books run in parallel, so the combined book *contains all the book's trades plus funding's* — the comparison "combined DSR vs book-alone DSR" is then a clean marginal-contribution test.
- **DSR penalty** uses the conservative total trial count `len(book_grid) + len(funding_grid) = 36 + 8 = 44` (stricter than the spec's "8"; being more conservative is always allowed). The funding-only (8) number is reported too.
- **ρ** (independent-info diagnostic) = correlation of the two sleeves' per-bar exit-bucketed realized pnl over the OOS span.

Task 0 edits the committed spec's Measurement section to match this.

---

### Task 0: Reconcile spec to the per-trade pooling combination

**Files:**
- Modify: `docs/superpowers/specs/2026-06-10-funding-sleeve-spike-design.md`

- [ ] **Step 1: Replace the "Combined" bullet in the Measurement section**

Find in the spec the bullet starting "**Combined:** equal-weight (rebalanced) combination of the two sleeves' net per-period **return streams**" and its sub-bullets, and replace the whole `2. **Combined:** ...` block with:

```markdown
2. **Combined:** pool the chosen book's OOS trades (`select_conviction_book`'s
   `chosen["oos_trades"]`) with the chosen funding sleeve's OOS trades into one
   list and run it through the existing `merge_portfolio(max_concurrent=6)` +
   `portfolio_equity_sized` — book names (`BTCUSD/…`) and funding names
   (`BTC_FUND/…`) are distinct, so cap 6 lets both 3-name books run in parallel
   and the combined book *contains all the book's trades plus funding's*. Report,
   in the per-trade convention so they are directly comparable to the book's
   1.15 / 0.166:
   - **combined Sharpe** (`_sharpe` on the pooled contributions);
   - **combined DSR**, penalized by the **total trials** `len(book_grid) +
     len(funding_grid) = 36 + 8 = 44` (conservative; funding-only=8 also reported);
   - **pairwise ρ** = correlation of the two sleeves' per-bar exit-bucketed
     realized pnl over the OOS span.
```

- [ ] **Step 2: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add docs/superpowers/specs/2026-06-10-funding-sleeve-spike-design.md
git commit -m "docs(study): reconcile funding-sleeve spec to per-trade pooling combination

Combined book pools both sleeves' trades into the existing
portfolio_equity_sized/deflated_sharpe_ratio machinery (cap 6, parallel
3-name books) so combined Sharpe/DSR stay comparable to the book's 1.15/0.166;
DSR penalized by total trials 44 (conservative) not 8.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 1: Funding pipeline — fetch + transform + IO

**Files:**
- Create: `backend/study/funding_pipeline.py`
- Test: `backend/tests/test_funding_pipeline.py`
- Modify: `.gitignore` (add `backend/data/funding/`)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_funding_pipeline.py`:

```python
"""Binance perp funding pipeline — funding rows → 2-col parquet → Series.

Pure transform + IO round-trip tested deterministically; the live network
fetch is gated behind STERLING_NET_TESTS=1 so the suite stays offline."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from study.funding_pipeline import (
    funding_to_frame, write_funding_frame, load_funding,
)


def _row(funding_time_ms, rate):
    return {"symbol": "BTCUSDT", "fundingTime": funding_time_ms,
            "fundingRate": f"{rate}", "markPrice": "60000.0"}


def test_funding_to_frame_normalises_schema():
    raw = [_row(1703836800000, 0.0001), _row(1703865600000, -0.00005)]
    df = funding_to_frame(raw)
    assert list(df.columns) == ["time", "funding_rate"]
    assert df["time"].iloc[0] == 1703836800           # ms → unix seconds
    assert df["funding_rate"].iloc[1] == pytest.approx(-0.00005)
    assert df["funding_rate"].dtype == np.float64
    assert df["time"].dtype.kind in ("i", "u")


def test_funding_to_frame_sorts_and_dedupes():
    raw = [_row(1703865600000, -0.00005), _row(1703836800000, 0.0001),
           _row(1703865600000, 9.9)]                   # dup time
    df = funding_to_frame(raw)
    assert len(df) == 2
    assert df["time"].is_monotonic_increasing
    assert df["time"].iloc[0] == 1703836800


def test_funding_to_frame_empty_is_empty_framed():
    df = funding_to_frame([])
    assert list(df.columns) == ["time", "funding_rate"]
    assert len(df) == 0


def test_write_and_load_funding_round_trip(tmp_path):
    raw = [_row(1703836800000 + i * 28800000, 0.0001 * (i % 3 - 1))
           for i in range(10)]
    write_funding_frame(funding_to_frame(raw), "BTC", str(tmp_path))
    s = load_funding("BTC", str(tmp_path))
    assert isinstance(s, pd.Series)
    assert isinstance(s.index, pd.DatetimeIndex)
    assert len(s) == 10
    assert s.name == "funding_rate"


def test_load_funding_missing_returns_none(tmp_path):
    assert load_funding("NOPE", str(tmp_path)) is None


@pytest.mark.skipif(os.environ.get("STERLING_NET_TESTS") != "1",
                    reason="network test (set STERLING_NET_TESTS=1)")
def test_fetch_funding_live_smoke():
    from study.funding_pipeline import fetch_funding_page
    raw = fetch_funding_page("BTCUSDT", limit=3)
    assert len(raw) >= 1
    assert "fundingRate" in raw[0] and "fundingTime" in raw[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_pipeline.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'study.funding_pipeline'`.

- [ ] **Step 3: Write the implementation**

Create `backend/study/funding_pipeline.py`:

```python
"""Perpetual-funding history pipeline — the orthogonal-information source.

Funding measures crowd POSITIONING (who pays to hold the trade), not price, so it
is a candidate signal independent of the price-based sleeves that hit the
correlation wall (docs/regime_book_before_after.md). Fetches Binance USDⓈ-M perp
funding-rate history (no API key) from the public fapi endpoint, normalises it to
a 2-col unix-second schema, and writes one parquet per coin.

Stdlib-only network (urllib+json); transforms + IO are pure and unit-tested; the
live fetch is gated behind STERLING_NET_TESTS=1.

Run:  cd backend && .venv/bin/python -m study.funding_pipeline --coins BTC ETH SOL
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request

import pandas as pd

BINANCE_FUNDING = "https://fapi.binance.com/fapi/v1/fundingRate"
FUNDING_DIR = "data/funding"
FUNDING_INTERVAL_MS = 8 * 3_600_000          # Binance settles funding every 8h
_FCOLS = ["time", "funding_rate"]


def _http_get_json(url: str, retries: int = 4, pause: float = 0.5):
    """GET JSON with linear backoff. Raises after `retries` failures."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sterling-study/1"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last = e
            time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} tries: {url} ({last})")


def fetch_funding_page(symbol: str, start_ms: int | None = None,
                       end_ms: int | None = None, limit: int = 1000) -> list:
    """One Binance funding-rate request (≤1000 rows). Returns raw rows."""
    url = f"{BINANCE_FUNDING}?symbol={symbol}&limit={limit}"
    if start_ms is not None:
        url += f"&startTime={int(start_ms)}"
    if end_ms is not None:
        url += f"&endTime={int(end_ms)}"
    return _http_get_json(url)


def fetch_funding_history(symbol: str, start_ms: int, end_ms: int | None = None,
                          pause: float = 0.25) -> list:
    """Paginate forward from start_ms, stitching ≤1000-row pages into the full
    raw funding history."""
    end_ms = end_ms or int(time.time() * 1000)
    out: list = []
    cursor = int(start_ms)
    while cursor < end_ms:
        page = fetch_funding_page(symbol, start_ms=cursor, end_ms=end_ms, limit=1000)
        if not page:
            break
        out.extend(page)
        nxt = int(page[-1]["fundingTime"]) + FUNDING_INTERVAL_MS
        if nxt <= cursor:                     # no forward progress → stop
            break
        cursor = nxt
        if len(page) < 1000:                  # last page
            break
        time.sleep(pause)
    return out


def funding_to_frame(raw: list) -> pd.DataFrame:
    """Normalise raw Binance funding rows → [time(unix s, int), funding_rate
    (float)], sorted by time and de-duplicated on time."""
    if not raw:
        return pd.DataFrame({"time": pd.Series(dtype="int64"),
                             "funding_rate": pd.Series(dtype="float64")})
    df = pd.DataFrame(raw)
    df["time"] = (df["fundingTime"].astype("int64") // 1000).astype("int64")
    df["funding_rate"] = df["fundingRate"].astype("float64")
    df = df[_FCOLS].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return df


def write_funding_frame(df: pd.DataFrame, coin: str, data_dir: str = FUNDING_DIR) -> str:
    """Write a 2-col frame to {data_dir}/{coin}_funding.parquet. Returns the path."""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, f"{coin}_funding.parquet")
    df.to_parquet(path, index=False)
    return path


def load_funding(coin: str, data_dir: str = FUNDING_DIR):
    """Load one coin's funding parquet → Series of funding_rate indexed by
    tz-naive UTC timestamp. Returns None if the file is missing."""
    path = os.path.join(data_dir, f"{coin}_funding.parquet")
    if not os.path.exists(path):
        return None
    d = pd.read_parquet(path, columns=_FCOLS)
    d["time"] = pd.to_datetime(d["time"], unit="s")
    return d.set_index("time")["funding_rate"].sort_index()


def download_funding(coin: str, start_ms: int, data_dir: str = FUNDING_DIR) -> dict:
    """Fetch full funding history for one coin and persist it. Coverage dict."""
    raw = fetch_funding_history(f"{coin}USDT", start_ms)
    df = funding_to_frame(raw)
    path = write_funding_frame(df, coin, data_dir)
    span = (None, None)
    if len(df):
        span = (pd.to_datetime(df["time"].iloc[0], unit="s").date().isoformat(),
                pd.to_datetime(df["time"].iloc[-1], unit="s").date().isoformat())
    return {"coin": coin, "rows": len(df), "start": span[0], "end": span[1],
            "path": path}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download Binance perp funding history.")
    ap.add_argument("--coins", nargs="*", default=["BTC", "ETH", "SOL"])
    ap.add_argument("--start", default="2023-12-29", help="YYYY-MM-DD history start")
    ap.add_argument("--data-dir", default=FUNDING_DIR)
    args = ap.parse_args(argv)

    start_ms = int(pd.Timestamp(args.start, tz="UTC").timestamp() * 1000)
    print(f"Downloading funding · {len(args.coins)} coins · from {args.start}"
          f" → {args.data_dir}\n")
    print(f"{'coin':>5} {'rows':>6}  {'start':>10}  {'end':>10}")
    for coin in args.coins:
        try:
            r = download_funding(coin, start_ms, args.data_dir)
            print(f"{r['coin']:>5} {r['rows']:>6}  {str(r['start']):>10}  {str(r['end']):>10}")
        except Exception as e:                # one bad coin must not abort the run
            print(f"{coin:>5} {'FAIL':>6}  {e}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_pipeline.py -q`
Expected: PASS (5 passed, 1 skipped).

- [ ] **Step 5: Add the funding data dir to .gitignore**

Add under the existing `backend/data/ohlcv/` line in `.gitignore`:

```
backend/data/funding/
```

- [ ] **Step 6: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/study/funding_pipeline.py backend/tests/test_funding_pipeline.py .gitignore
git commit -m "feat(study): Binance perp funding-rate history pipeline

Stdlib fetch (fapi/v1/fundingRate) + pure transform + IO, mirroring
ohlcv_pipeline. Funding = crowd-positioning signal, the orthogonal-information
candidate for the conviction book. Tests offline; live smoke net-gated.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Download real funding data (one-off network step)

**Files:** none (writes gitignored `backend/data/funding/*.parquet`).

- [ ] **Step 1: Run the pipeline against the live endpoint**

Run: `cd backend && .venv/bin/python -m study.funding_pipeline --coins BTC ETH SOL --start 2023-12-29`
Expected: three rows printed, each with `rows` in the low thousands (≈ 3/day × ~2.4y ≈ 2,600) and `end` near today (2026-06-10). If a coin prints `FAIL`, retry once; Binance fapi is occasionally rate-limited.

- [ ] **Step 2: Verify the parquets loaded back**

Run: `cd backend && .venv/bin/python -c "from study.funding_pipeline import load_funding; [print(c, None if (s:=load_funding(c)) is None else (len(s), s.index.min(), s.index.max())) for c in ('BTC','ETH','SOL')]"`
Expected: each coin prints a count and a date span spanning 2023-12 → 2026-06. No commit (data is gitignored).

---

### Task 3: Funding alignment + leak-free z-score signal

**Files:**
- Create: `backend/study/funding_sleeve.py`
- Test: `backend/tests/test_funding_sleeve.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_funding_sleeve.py`:

```python
"""Funding sleeve — alignment, leak-free z-score signal, cash-flow, trades."""
from __future__ import annotations

import numpy as np
import pandas as pd

from study.funding_sleeve import align_funding, funding_signal


def _bars(start="2024-01-01 00:00", n=24, freq="4h"):
    idx = pd.date_range(start, periods=n, freq=freq)
    px = 100.0 * (1 + 0.001 * np.arange(n))
    return pd.DataFrame({"open": px, "high": px * 1.01, "low": px * 0.99,
                         "close": px * 1.002, "volume": 1.0,
                         "atr": px * 0.02}, index=idx)


def _funding(start="2024-01-01 00:00", n=8, freq="8h", rates=None):
    idx = pd.date_range(start, periods=n, freq=freq)
    if rates is None:
        rates = [0.0001] * n
    return pd.Series(rates, index=idx, name="funding_rate")


def test_align_funding_lands_events_on_bar_opens():
    bars = _bars(n=6)                       # 00,04,08,12,16,20
    f = _funding(n=2)                       # 00:00, 08:00
    a = align_funding(f, bars.index)
    assert len(a) == len(bars)
    assert a.loc["2024-01-01 00:00"] == 0.0001
    assert a.loc["2024-01-01 08:00"] == 0.0001
    assert a.loc["2024-01-01 04:00"] == 0.0   # no settlement on this 4h bar


def test_funding_signal_is_leak_free():
    # signal at bar t must use only funding events with time <= t.
    bars = _bars(n=24)
    f = _funding(n=8, rates=[0.0, 0.0, 0.0, 0.0, 0.01, 0.01, 0.01, 0.01])
    sig = funding_signal(f, bars.index, window=3, thr=1.0)
    assert len(sig) == len(bars)
    # The early bars (before any high-funding events accrue) cannot be short.
    assert sig.iloc[0] == 0
    # Truncating future funding must not change earlier signal values.
    sig_trunc = funding_signal(f.iloc[:5], bars.index, window=3, thr=1.0)
    common = sig.index.intersection(sig_trunc.index)
    early = common[common <= f.index[4]]
    assert (sig.loc[early].fillna(0) == sig_trunc.loc[early].fillna(0)).all()


def test_funding_signal_sign_convention():
    # Richly POSITIVE funding (crowd long) => contrarian SHORT (sig == -1).
    bars = _bars(n=24)
    rates = [0.0] * 4 + [0.02] * 4          # jump to very positive
    f = _funding(n=8, rates=rates)
    sig = funding_signal(f, bars.index, window=3, thr=1.0)
    assert sig.min() == -1                  # produced a short
    assert sig.max() <= 1
    # Deeply NEGATIVE funding (crowd short) => contrarian LONG (sig == +1).
    f2 = _funding(n=8, rates=[0.0] * 4 + [-0.02] * 4)
    sig2 = funding_signal(f2, bars.index, window=3, thr=1.0)
    assert sig2.max() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_sleeve.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'study.funding_sleeve'`.

- [ ] **Step 3: Write the implementation (alignment + signal only)**

Create `backend/study/funding_sleeve.py`:

```python
"""Funding-rate positioning-tilt sleeve — the orthogonal-information spike.

Turns Binance perp funding into a leak-free CONTRARIAN directional signal (richly
positive funding = over-leveraged longs → short bias; deeply negative → long),
runs it through the existing study.sim.simulate_idx fill engine with the real
funding cash-flow added per held bar, then pools its trades with the conviction
book's trades into the existing per-trade book machinery so combined Sharpe/DSR
stay comparable to the book's 1.15 / 0.166.

RESEARCH TOOL — not wired into anything live. Spec:
docs/superpowers/specs/2026-06-10-funding-sleeve-spike-design.md

Run:  cd backend && .venv/bin/python -m study.funding_sleeve
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from study.sim import simulate_idx, sharpe as _sharpe

FEE_RT = 0.001
MAX_HOLD = 200
_SL, _TP = 1.5, 4.5          # Aggressive bracket — same as the MR sleeve


def align_funding(funding: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Reindex 8h funding settlements onto the 4h bar grid: each settlement
    (00/08/16 UTC) lands on the bar whose open == the settlement time; bars with
    no settlement are 0.0. Used for per-bar cash-flow accrual."""
    return funding.reindex(index).fillna(0.0)


def funding_signal(funding: pd.Series, index: pd.DatetimeIndex,
                   window: int, thr: float) -> pd.Series:
    """Leak-free contrarian signal on the bar grid, in {-1, 0, +1}.

    The z-score is computed over the rolling window of the last `window` funding
    EVENTS (not bars), using only events with time <= the event itself; the
    resulting per-event signal is forward-filled onto bars, so the signal at bar
    t reflects only the most recent funding event with time <= t. No lookahead.

    Sign: z > +thr (funding richly positive, crowd long) → -1 (contrarian SHORT);
          z < -thr (funding deeply negative, crowd short) → +1 (contrarian LONG).
    """
    f = funding.sort_index()
    mean = f.rolling(window).mean()
    std = f.rolling(window).std()
    z = (f - mean) / std.replace(0.0, np.nan)
    sig_event = pd.Series(
        np.where(z > thr, -1, np.where(z < -thr, 1, 0)), index=f.index
    ).fillna(0).astype(int)
    return sig_event.reindex(index, method="ffill").fillna(0).astype(int)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_sleeve.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/study/funding_sleeve.py backend/tests/test_funding_sleeve.py
git commit -m "feat(study): funding sleeve — alignment + leak-free contrarian z-signal

Funding settlements aligned to 4h bars; z-score over rolling funding EVENTS,
ffilled onto bars (signal at t uses only events <= t — unit-tested leak-free).
Sign: rich-positive funding -> short, deep-negative -> long.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Funding cash-flow accrual + bracket-exit trade builder

**Files:**
- Modify: `backend/study/funding_sleeve.py`
- Test: `backend/tests/test_funding_sleeve.py`

- [ ] **Step 1: Write the failing test (append to test_funding_sleeve.py)**

Append:

```python
from study.funding_sleeve import funding_cashflow, build_funding_trades


def test_funding_cashflow_sign_and_magnitude():
    # held from bar 1 to bar 4; settlements on bars 2 and 4 are 0.01 each.
    f_bar = pd.Series([0.0, 0.0, 0.01, 0.0, 0.01, 0.0])
    # SHORT collects positive funding: +0.02 over the two settlements after entry.
    assert funding_cashflow(f_bar, 1, 4, "short") == pytest.approx(0.02)
    # LONG pays it: -0.02.
    assert funding_cashflow(f_bar, 1, 4, "long") == pytest.approx(-0.02)
    # The entry bar's own settlement (bar 1) is excluded; exit bar (4) included.
    assert funding_cashflow(f_bar, 0, 2, "short") == pytest.approx(0.01)


def test_build_funding_trades_tags_and_adds_cashflow():
    bars = _bars(n=40)
    rates = [0.0] * 4 + [0.02] * 16         # sustained rich funding => shorts
    f = _funding(start="2024-01-01 00:00", n=20, rates=rates)
    trades = build_funding_trades("BTC", bars, f, window=3, thr=1.0,
                                  exit_mode="bracket")
    assert trades, "expected at least one funding trade"
    t = trades[0]
    assert t["symbol"] == "BTC_FUND"
    assert t["sleeve"] == "funding"
    assert t["direction"] in ("long", "short")
    assert {"entry_time", "exit_time", "pnl_pct", "stop_dist_pct"} <= set(t)
    assert t["stop_dist_pct"] > 0
```

Add `import pytest` at the top of the test file if not already present (it is, from Task 1's sibling file — confirm this file has it; if not, add `import pytest`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_sleeve.py -q`
Expected: FAIL — `ImportError: cannot import name 'funding_cashflow'`.

- [ ] **Step 3: Add the implementation to funding_sleeve.py**

Append to `backend/study/funding_sleeve.py`:

```python
def funding_cashflow(f_bar: pd.Series, entry_bar: int, exit_bar: int,
                     direction: str) -> float:
    """Funding cash-flow (as a fraction of notional) accrued holding from
    entry_bar to exit_bar. Entry is at the entry bar's close (after that bar's
    settlement), so settlements strictly after entry up to and including exit
    count: bars [entry_bar+1 .. exit_bar]. A SHORT collects positive funding; a
    LONG pays it."""
    if exit_bar <= entry_bar:
        return 0.0
    accrued = float(f_bar.iloc[entry_bar + 1: exit_bar + 1].sum())
    return accrued if direction == "short" else -accrued


def build_funding_trades(coin: str, df: pd.DataFrame, funding: pd.Series,
                         window: int, thr: float, exit_mode: str = "bracket"
                         ) -> list[dict]:
    """Build funding-sleeve trades for one symbol. The contrarian z-signal enters
    longs/shorts through the existing simulate_idx (bracket) fill engine; the real
    funding cash-flow is added to each trade's pnl. Trades are tagged with a
    distinct `{coin}_FUND` name + stop_dist_pct (for vol-target sizing)."""
    sig = funding_signal(funding, df.index, window, thr).to_numpy()
    f_bar = align_funding(funding, df.index)
    close = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    out: list[dict] = []
    for target, direction in ((1, "long"), (-1, "short")):
        sigs = (sig == target)
        if exit_mode == "bracket":
            raw = simulate_idx(df, sigs, _SL, _TP, direction=direction,
                               fee_rt=FEE_RT, max_hold=MAX_HOLD)
        else:                                # hold-to-flip
            raw = simulate_hold_to_flip(df, sig, target, fee_rt=FEE_RT,
                                        max_hold=MAX_HOLD)
        for t in raw:
            e = close[t["entry_bar"]]
            a = atr[t["entry_bar"]]
            fpnl = funding_cashflow(f_bar, t["entry_bar"], t["exit_bar"], direction)
            out.append({
                "symbol": f"{coin}_FUND", "sleeve": "funding", "direction": direction,
                "entry_time": df.index[t["entry_bar"]],
                "exit_time": df.index[t["exit_bar"]],
                "pnl_pct": t["pnl_pct"] + fpnl,
                "stop_dist_pct": (_SL * a / e) if e > 0 else 0.0,
            })
    return out
```

> Note: `build_funding_trades` references `simulate_hold_to_flip` for the
> non-bracket branch; it is added in Task 5. The bracket test above does not
> exercise that branch, so this task's tests pass without it.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_sleeve.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/study/funding_sleeve.py backend/tests/test_funding_sleeve.py
git commit -m "feat(study): funding cash-flow accrual + bracket trade builder

Real funding cash-flow (short collects positive funding, long pays) added to
each simulate_idx trade's price pnl; trades tagged {coin}_FUND + stop_dist_pct
for vol-target sizing. Settlements counted (entry+1..exit].

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Hold-to-flip exit simulator

**Files:**
- Modify: `backend/study/funding_sleeve.py`
- Test: `backend/tests/test_funding_sleeve.py`

- [ ] **Step 1: Write the failing test (append)**

```python
from study.funding_sleeve import simulate_hold_to_flip


def test_hold_to_flip_exits_when_signal_leaves_target():
    # sig holds target=+1 for bars 2..5 then drops to 0 → exit at bar 6.
    idx = pd.date_range("2024-01-01", periods=10, freq="4h")
    px = np.array([100, 100, 100, 101, 102, 103, 104, 104, 104, 104], float)
    df = pd.DataFrame({"open": px, "high": px, "low": px, "close": px,
                       "volume": 1.0, "atr": 2.0}, index=idx)
    sig = np.array([0, 0, 1, 1, 1, 1, 0, 0, 0, 0])
    raw = simulate_hold_to_flip(df, sig, target=1, fee_rt=0.0, max_hold=200)
    assert len(raw) == 1
    t = raw[0]
    assert t["entry_bar"] == 2 and t["exit_bar"] == 6
    # long pnl over 100 -> 104, no fee:
    assert t["pnl_pct"] == pytest.approx(0.04)


def test_hold_to_flip_short_direction_and_fee():
    idx = pd.date_range("2024-01-01", periods=8, freq="4h")
    px = np.array([100, 100, 100, 98, 96, 96, 96, 96], float)
    df = pd.DataFrame({"open": px, "high": px, "low": px, "close": px,
                       "volume": 1.0, "atr": 2.0}, index=idx)
    sig = np.array([0, 0, -1, -1, 0, 0, 0, 0])
    raw = simulate_hold_to_flip(df, sig, target=-1, fee_rt=0.001, max_hold=200)
    assert len(raw) == 1
    t = raw[0]
    assert t["entry_bar"] == 2 and t["exit_bar"] == 4
    # short 100 -> 96 = +0.04 price, minus 0.001 fee:
    assert t["pnl_pct"] == pytest.approx(0.039)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_sleeve.py -k hold_to_flip -q`
Expected: FAIL — `ImportError: cannot import name 'simulate_hold_to_flip'`.

- [ ] **Step 3: Add the implementation to funding_sleeve.py**

Append:

```python
def simulate_hold_to_flip(df: pd.DataFrame, sig, target: int,
                          fee_rt: float = FEE_RT, max_hold: int = MAX_HOLD
                          ) -> list[dict]:
    """Signal-driven exit (NOT a simulate_idx bracket): enter at close on each bar
    where sig == target with no open position; exit at close of the first later
    bar where sig != target (or after max_hold / at the series end). Same fee
    model as simulate_idx. Returns {pnl_pct, entry_bar, exit_bar}."""
    close = df["close"].to_numpy(float)
    sig = np.asarray(sig)
    n = len(close)
    direction = "long" if target > 0 else "short"
    out: list[dict] = []
    i = 0
    while i < n - 1:
        if sig[i] != target:
            i += 1
            continue
        e = close[i]
        end = min(i + max_hold, n - 1)
        xi = end
        for j in range(i + 1, end + 1):
            if sig[j] != target:
                xi = j
                break
        xp = close[xi]
        pnl = (xp / e - 1.0) if direction == "long" else (1.0 - xp / e)
        out.append({"pnl_pct": pnl - fee_rt, "entry_bar": int(i),
                    "exit_bar": int(xi)})
        i = xi + 1                            # no overlapping positions
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_sleeve.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/study/funding_sleeve.py backend/tests/test_funding_sleeve.py
git commit -m "feat(study): hold-to-flip signal-driven exit for funding sleeve

Separate small exit path (not simulate_idx brackets): hold until the funding
signal leaves its target, then exit at close. Same fee model. Own unit tests.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Grid select (8 cells, IS-selected) + funding DSR

**Files:**
- Modify: `backend/study/funding_sleeve.py`
- Test: `backend/tests/test_funding_sleeve.py`

- [ ] **Step 1: Write the failing test (append)**

```python
from study.funding_sleeve import funding_grid, select_funding_sleeve


def test_funding_grid_is_eight_cells():
    g = funding_grid()
    assert len(g) == 8
    assert all(len(cell) == 3 for cell in g)          # (window, thr, exit_mode)
    assert {c[2] for c in g} == {"bracket", "flip"}


def test_select_funding_sleeve_is_lookahead_free_and_shaped():
    # Two synthetic symbols with sustained funding regimes so trades exist.
    import numpy as np
    frames, fundings = {}, {}
    for coin, base in (("BTC", 100.0), ("ETH", 50.0)):
        bars = _bars(start="2024-01-01", n=400)
        bars["close"] = base * (1 + 0.0005 * np.arange(400))
        bars["high"] = bars["close"] * 1.01
        bars["low"] = bars["close"] * 0.99
        bars["atr"] = bars["close"] * 0.02
        frames[f"{coin}USD"] = bars
        rates = ([0.0] * 100 + [0.03] * 100 + [0.0] * 100 + [-0.03] * 100)
        fundings[coin] = _funding(start="2024-01-01", n=200,
                                  rates=[rates[i] for i in range(0, 400, 2)])
    res = select_funding_sleeve(frames, fundings, oos_start=0.5)
    assert set(res) >= {"chosen", "scored", "dsr", "n_grid", "is_oos_corr"}
    assert res["n_grid"] == 8
    assert 0.0 <= res["dsr"] <= 1.0
    assert "oos_trades" in res["chosen"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_sleeve.py -k "funding_grid or select_funding" -q`
Expected: FAIL — `ImportError: cannot import name 'funding_grid'`.

- [ ] **Step 3: Add the implementation to funding_sleeve.py**

Append (the imports at the top of the module must also gain `split` helpers from regime_book and the DSR fn — add these to the import block near the top):

```python
# add near the top imports:
from study.regime_book import (
    merge_portfolio, portfolio_equity_sized, _spearman,
)
from app.engines.edge.robustness import deflated_sharpe_ratio
```

then append:

```python
def funding_grid():
    """(window, thr, exit_mode) pre-registered 8-cell search grid. window is in
    funding EVENTS (8h): 30≈10d, 90≈30d. Frozen — the DSR penalty assumes this
    fixed trial count."""
    import itertools
    return list(itertools.product([30, 90], [1.0, 2.0], ["bracket", "flip"]))


def split_funding_book(frames: dict, fundings: dict, window: int, thr: float,
                       exit_mode: str, oos_start: float = 0.5):
    """Build the funding sleeve across all symbols and split each symbol's trades
    at oos_start into (in_sample, out_of_sample) by entry time. `frames` keyed by
    `{COIN}USD`; `fundings` keyed by `{COIN}`."""
    is_t, oos_t = [], []
    for sym, df in frames.items():
        coin = sym.replace("USD", "")
        funding = fundings.get(coin)
        if funding is None:
            continue
        t0, t1 = df.index[0], df.index[-1]
        cut = t0 + (t1 - t0) * oos_start
        for t in build_funding_trades(coin, df, funding, window, thr, exit_mode):
            (oos_t if t["entry_time"] >= cut else is_t).append(t)
    return is_t, oos_t


def select_funding_sleeve(frames: dict, fundings: dict, grid=None,
                          oos_start: float = 0.5, risk_per_trade: float = 0.015,
                          max_leverage: float = 3.0, max_concurrent: int = 3) -> dict:
    """No-lookahead selection: score every grid cell by IN-SAMPLE Sharpe, pick the
    best, report its OUT-OF-SAMPLE result deflated by the grid size. Also returns
    the grid-wide Spearman IS→OOS Sharpe rank correlation (the overfit detector:
    the project's cut strategies had it negative)."""
    grid = grid or funding_grid()
    scored = []
    for window, thr, exit_mode in grid:
        is_t, oos_t = split_funding_book(frames, fundings, window, thr,
                                         exit_mode, oos_start)
        ie = portfolio_equity_sized(is_t, 500.0, risk_per_trade, max_leverage,
                                    max_concurrent, 1.0)
        oe = portfolio_equity_sized(oos_t, 500.0, risk_per_trade, max_leverage,
                                    max_concurrent, 1.0)
        scored.append({"params": (window, thr, exit_mode),
                       "is_sharpe": ie["sharpe"], "oos": oe, "oos_trades": oos_t})
    chosen = max(scored, key=lambda s: s["is_sharpe"])
    wp = chosen["oos"]["weighted_pnls"]
    dsr = deflated_sharpe_ratio(wp, num_trials=len(grid)) if wp else 0.0
    is_oos_corr = _spearman([s["is_sharpe"] for s in scored],
                            [s["oos"]["sharpe"] for s in scored])
    return {"chosen": chosen, "scored": scored, "dsr": round(dsr, 4),
            "n_grid": len(grid), "is_oos_corr": round(is_oos_corr, 4)}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_sleeve.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/study/funding_sleeve.py backend/tests/test_funding_sleeve.py
git commit -m "feat(study): funding sleeve grid-select (8 cells, IS-chosen) + DSR

Pre-registered 8-cell grid (window{30,90} x thr{1,2} x exit{bracket,flip});
IS-Sharpe selection, OOS report deflated by grid size, grid-wide Spearman
IS->OOS corr (overfit detector). Reuses portfolio_equity_sized + DSR.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Combine with the conviction book + ρ diagnostic

**Files:**
- Modify: `backend/study/funding_sleeve.py`
- Test: `backend/tests/test_funding_sleeve.py`

- [ ] **Step 1: Write the failing test (append)**

```python
from study.funding_sleeve import returns_by_bar, combine_books


def test_returns_by_bar_buckets_pnl_on_exit():
    idx = pd.date_range("2024-01-01", periods=5, freq="4h")
    trades = [
        {"exit_time": idx[1], "pnl_pct": 0.02},
        {"exit_time": idx[1], "pnl_pct": -0.01},   # two exits same bar → summed
        {"exit_time": idx[3], "pnl_pct": 0.05},
    ]
    s = returns_by_bar(trades, idx)
    assert len(s) == 5
    assert s.iloc[1] == pytest.approx(0.01)
    assert s.iloc[3] == pytest.approx(0.05)
    assert s.iloc[0] == 0.0


def test_combine_books_pools_and_reports_corr_and_dsr():
    idx = pd.date_range("2024-01-01", periods=20, freq="4h")
    book = [{"symbol": "BTCUSD", "entry_time": idx[i], "exit_time": idx[i + 1],
             "pnl_pct": 0.01, "stop_dist_pct": 0.03} for i in range(0, 10, 2)]
    fund = [{"symbol": "BTC_FUND", "entry_time": idx[i], "exit_time": idx[i + 1],
             "pnl_pct": 0.008, "stop_dist_pct": 0.03} for i in range(1, 11, 2)]
    res = combine_books(book, fund, idx, book_trials=36, funding_trials=8)
    assert set(res) >= {"combined", "rho", "dsr_total", "dsr_funding_only", "n"}
    assert res["combined"]["n"] == len(book) + len(fund)
    assert -1.0 <= res["rho"] <= 1.0
    assert 0.0 <= res["dsr_total"] <= 1.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_sleeve.py -k "returns_by_bar or combine_books" -q`
Expected: FAIL — `ImportError: cannot import name 'returns_by_bar'`.

- [ ] **Step 3: Add the implementation to funding_sleeve.py**

Append:

```python
def returns_by_bar(trades: list[dict], index: pd.DatetimeIndex) -> pd.Series:
    """Per-bar realized pnl: each trade's pnl_pct bucketed onto its exit bar
    (summed when several exit the same bar); 0.0 elsewhere. The independent-info
    diagnostic basis for the sleeve-vs-book correlation."""
    s = pd.Series(0.0, index=index)
    for t in trades:
        if t["exit_time"] in s.index:
            s.loc[t["exit_time"]] += t["pnl_pct"]
    return s


def combine_books(book_trades: list[dict], funding_trades: list[dict],
                  index: pd.DatetimeIndex, book_trials: int = 36,
                  funding_trials: int = 8, risk_per_trade: float = 0.015,
                  max_leverage: float = 3.0) -> dict:
    """Pool the book's OOS trades with the funding sleeve's OOS trades into the
    existing per-trade book machinery at cap 6 (both 3-name books run in
    parallel), so the combined book contains all the book's trades plus
    funding's. Returns the combined equity stats, the combined DSR penalized by
    the TOTAL trial count (conservative), the funding-only DSR, and the per-bar
    correlation ρ between the two sleeves."""
    pooled = list(book_trades) + list(funding_trades)
    combined = portfolio_equity_sized(pooled, 500.0, risk_per_trade,
                                      max_leverage, max_concurrent=6, leverage=1.0)
    wp = combined["weighted_pnls"]
    dsr_total = deflated_sharpe_ratio(wp, num_trials=book_trials + funding_trials) \
        if wp else 0.0
    dsr_funding_only = deflated_sharpe_ratio(wp, num_trials=funding_trials) \
        if wp else 0.0
    rb = returns_by_bar(book_trades, index)
    rf = returns_by_bar(funding_trades, index)
    mask = (rb != 0.0) | (rf != 0.0)
    if mask.sum() >= 3 and rb[mask].std() > 0 and rf[mask].std() > 0:
        rho = float(np.corrcoef(rb[mask], rf[mask])[0, 1])
    else:
        rho = 0.0
    return {"combined": combined, "rho": round(rho, 4),
            "dsr_total": round(dsr_total, 4),
            "dsr_funding_only": round(dsr_funding_only, 4),
            "n": combined["n"]}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_sleeve.py -q`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/study/funding_sleeve.py backend/tests/test_funding_sleeve.py
git commit -m "feat(study): combine funding sleeve with conviction book + rho

Pools both sleeves' OOS trades into portfolio_equity_sized (cap 6, parallel
3-name books) -> combined Sharpe/DSR comparable to 1.15/0.166; DSR penalized
by total trials (44, conservative). Per-bar exit-bucketed corr = the
independent-information diagnostic.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: End-to-end runner + honest result report

**Files:**
- Modify: `backend/study/funding_sleeve.py` (add `load_frames_funding` + `main`)
- Create: `docs/funding_sleeve_result.md` (written from the run output)

- [ ] **Step 1: Add the runner to funding_sleeve.py**

Append:

```python
def load_frames_and_funding(coins=("BTC", "ETH", "SOL"), tf: str = "4h"):
    """Load the 3-coin 4h OHLCV+ATR frames (data/ohlcv) and their funding Series
    (data/funding). Returns (frames keyed {COIN}USD, fundings keyed {COIN})."""
    from study.ohlcv_pipeline import load_universe
    from study.funding_pipeline import load_funding
    universe = load_universe(tf, data_dir="data/ohlcv")
    frames = {f"{c}USD": universe[f"{c}USD"] for c in coins if f"{c}USD" in universe}
    fundings = {c: load_funding(c) for c in coins if load_funding(c) is not None}
    return frames, fundings


def main():
    from study.regime_book import select_conviction_book
    frames, fundings = load_frames_and_funding()
    print(f"frames: {list(frames)}  funding: {list(fundings)}")

    # OOS span shared by all symbols (longest common — use the min start / shared tail)
    common_index = sorted(set().union(*[df.index for df in frames.values()]))
    idx = pd.DatetimeIndex(common_index)

    # 1) Baseline conviction book (in-experiment, on the same data/ohlcv 4h frames)
    book = select_conviction_book(frames)
    bc = book["chosen"]
    book_oos = bc["oos_trades"]
    print(f"\nBOOK  IS-best {bc['params']}  OOS ret {bc['oos']['ret']*100:.1f}% "
          f"Sharpe {bc['oos']['sharpe']:.2f}  n={bc['oos']['n']}  DSR(36) {book['dsr']:.4f}")

    # 2) Funding sleeve standalone
    fund = select_funding_sleeve(frames, fundings)
    fc = fund["chosen"]
    fund_oos = fc["oos_trades"]
    print(f"FUND  IS-best {fc['params']}  OOS ret {fc['oos']['ret']*100:.1f}% "
          f"Sharpe {fc['oos']['sharpe']:.2f}  n={fc['oos']['n']}  DSR(8) {fund['dsr']:.4f} "
          f"IS→OOS corr {fund['is_oos_corr']}")

    # 3) Combined
    comb = combine_books(book_oos, fund_oos, idx,
                         book_trials=book["n_grid"], funding_trials=fund["n_grid"])
    print(f"COMB  Sharpe {comb['combined']['sharpe']:.2f}  ret {comb['combined']['ret']*100:.1f}% "
          f"n={comb['n']}  DSR(44) {comb['dsr_total']:.4f}  "
          f"DSR(8) {comb['dsr_funding_only']:.4f}  rho {comb['rho']}")

    # 4) Pre-registered disposition
    kill = (fc["oos"]["sharpe"] <= 0) or (fund["is_oos_corr"] < 0)
    fold = (comb["dsr_total"] > book["dsr"]) and \
           (comb["combined"]["sharpe"] >= 1.15) and (abs(comb["rho"]) < 0.5)
    verdict = "KILL (no standalone edge)" if kill else \
              ("FOLD IN" if fold else "HONEST NEGATIVE (no independent edge)")
    print(f"\nVERDICT: {verdict}")
    return {"book": book, "fund": fund, "comb": comb,
            "kill": kill, "fold": fold, "verdict": verdict}


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full spike on real data**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m study.funding_sleeve`
Expected: prints the BOOK / FUND / COMB lines and a `VERDICT:`. Capture the exact numbers — they go verbatim into the report. (No assertion here; this is the experiment.)

- [ ] **Step 3: Write `docs/funding_sleeve_result.md` from the captured output**

Create `docs/funding_sleeve_result.md` using the REAL numbers from Step 2, following the structure of `docs/regime_book_before_after.md`:
- **Method** (data, OOS span, harness reuse, the 8-cell grid, sign convention).
- **Results table:** BOOK (DSR 36) / FUND standalone (DSR 8, IS→OOS corr) / COMBINED (Sharpe, DSR 44 + DSR 8, ρ).
- **The pre-registered bar** (restate KILL/FOLD conditions) and the **VERDICT** the run produced.
- **Honest read:** if FOLD — the marginal DSR lift and why ρ shows independence; if NEGATIVE — that funding is correlated/insufficient (the correlation wall holds even for positioning), placed alongside breadth/XS/leverage/trailing as another documented negative.

- [ ] **Step 4: Run the whole funding test file once more (regression)**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_pipeline.py tests/test_funding_sleeve.py -q`
Expected: all green (offline tests), funding network smoke skipped.

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/study/funding_sleeve.py docs/funding_sleeve_result.md
git commit -m "feat(study): funding-sleeve end-to-end runner + honest result report

Runner loads real BTC/ETH/SOL 4h + funding, runs baseline conviction book,
funding standalone, and the combined book, then prints the pre-registered
KILL/FOLD/NEGATIVE verdict. Result documented in docs/funding_sleeve_result.md.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Regression guard — book-alone path unchanged

**Files:**
- Test: `backend/tests/test_funding_sleeve.py`

- [ ] **Step 1: Write the test (append)**

```python
def test_combine_with_no_funding_equals_book_alone():
    # With zero funding trades, the combined book must equal the book alone
    # (cap 6 vs the book's own concurrency does not change a <=3-name book).
    idx = pd.date_range("2024-01-01", periods=20, freq="4h")
    book = [{"symbol": "BTCUSD", "entry_time": idx[i], "exit_time": idx[i + 1],
             "pnl_pct": 0.01, "stop_dist_pct": 0.03} for i in range(0, 10, 2)]
    res = combine_books(book, [], idx, book_trials=36, funding_trials=8)
    from study.regime_book import portfolio_equity_sized
    book_only = portfolio_equity_sized(book, 500.0, 0.015, 3.0, 6, 1.0)
    assert res["combined"]["weighted_pnls"] == book_only["weighted_pnls"]
    assert res["rho"] == 0.0
```

- [ ] **Step 2: Run to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_sleeve.py -k "no_funding" -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/tests/test_funding_sleeve.py
git commit -m "test(study): regression — combined book == book-alone when no funding

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] Run the full funding suite: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_funding_pipeline.py tests/test_funding_sleeve.py -q` → all green.
- [ ] Confirm nothing live changed: `git grep -n "funding_sleeve\|funding_pipeline" backend/app` returns nothing (research-only isolation holds).
- [ ] `docs/funding_sleeve_result.md` states the verdict with the real numbers.
- [ ] Report the verdict to the user (FOLD IN / HONEST NEGATIVE / KILL) — this gates whether Phase 2 packaging wraps "book + funding" or "book alone".

---

## Self-review notes

- **Spec coverage:** pipeline (T1–2), leak-free signal (T3), cash-flow + bracket (T4), hold-to-flip (T5), 8-cell IS-select + DSR + IS→OOS corr (T6), combine + ρ (T7), runner + report + pre-registered verdict (T8), regression (T9). All spec requirements mapped.
- **No placeholders:** every code/test step is complete; the only deferred reference (`simulate_hold_to_flip` in T4) is explicitly flagged and supplied in T5, and T4's tests don't exercise it.
- **Type consistency:** trade dicts use `symbol/sleeve/direction/entry_time/exit_time/pnl_pct/stop_dist_pct` throughout; `select_*` return `chosen["oos_trades"]` + `chosen["oos"]["weighted_pnls"]` matching `select_conviction_book`; `combine_books` keys (`combined/rho/dsr_total/dsr_funding_only/n`) match the runner's usage.
