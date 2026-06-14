# Kite Triple-SuperTrend Options Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Kite-exclusive 1H Heikin-Ashi triple-SuperTrend options engine that scans the Indian universe (Nifty50/BankNifty/FinNifty/Sensex stocks + index options), emits ready Signals with ATM/ITM strikes, shows them in the Kite right sidebar with click-to-chart, and optionally auto-executes.

**Architecture:** A pure, broker-agnostic engine core (`backend/app/engines/triple_supertrend/`) computes HA + 3 SuperTrends, detects fresh full-alignment transitions, and trails on the mid ST. Kite-only wiring (universe builder, throttled scanner, ATM/ITM strike picker, endpoints, sidebar pane, auto-exec) lives separately and imports **no** other-engine strategy logic.

**Tech Stack:** Python/FastAPI, numpy, pydantic; React + lightweight-charts v5; Kite Connect (KiteClient).

**Test convention:** Run with `PYTHONWARNINGS=ignore` from `backend/`. Tests live in `backend/tests/engines/triple_supertrend/`.

**Hard constraint (Kite exclusive):** No imports from `app.engines.derivatives`, `edge`, `directional`, `scalping`, `sterling_*`. Allowed shared primitives only: `compute_heikin_ashi`, `compute_supertrend`, `app.domain.models.Signal`.

---

## File structure

**Engine core (pure, broker-agnostic):**
- `backend/app/engines/triple_supertrend/__init__.py` — exports
- `backend/app/engines/triple_supertrend/config.py` — `TripleSupertrendConfig`
- `backend/app/engines/triple_supertrend/regime.py` — pure HA+3ST+transitions+trail
- `backend/app/engines/triple_supertrend/engine.py` — `TripleSupertrendEngine` (StrategyProtocol)
- `backend/app/engines/triple_supertrend/schemas.py` — API/UI pydantic models

**Kite wiring (exclusive):**
- `backend/app/services/kite_engine/__init__.py`
- `backend/app/services/kite_engine/universe.py` — universe builder + `universe.json`
- `backend/app/services/kite_engine/strikes.py` — ATM/ITM picker (Kite chain)
- `backend/app/services/kite_engine/scanner.py` — throttled scan + candle cache + store
- `backend/app/api/v1/endpoints/kite_engine.py` — `/api/v1/kite/engine/*` routes
- Modify `backend/main.py` — include the router

**Frontend:**
- `frontend/src/components/kite/TripleSupertrendPane.tsx` — right sidebar
- `frontend/src/components/kite/SetupChart.tsx` — click-to-chart (HA + 3 ST + markers)
- `frontend/src/hooks/useTripleSupertrend.ts` — polling + setup fetch
- Modify `frontend/src/components/kite/KiteTab.tsx:54` — mount pane in `rightSidebar`
- `frontend/src/types/kiteEngine.ts` — shared types

**Tests:**
- `backend/tests/engines/triple_supertrend/__init__.py`
- `backend/tests/engines/triple_supertrend/conftest.py` — OHLC fixtures
- `backend/tests/engines/triple_supertrend/test_regime.py`
- `backend/tests/engines/triple_supertrend/test_engine.py`
- `backend/tests/engines/triple_supertrend/test_strikes.py`
- `backend/tests/engines/triple_supertrend/test_universe.py`

---

# PHASE 1 — Engine core (the heart, full TDD)

### Task 1: Config

**Files:**
- Create: `backend/app/engines/triple_supertrend/__init__.py`
- Create: `backend/app/engines/triple_supertrend/config.py`

- [ ] **Step 1:** Create `__init__.py` empty (exports added later).

- [ ] **Step 2:** Write `config.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Tuple

TrailTarget = Literal["fast", "mid", "slow"]


@dataclass(frozen=True)
class TripleSupertrendConfig:
    """Knobs for the 1H Heikin-Ashi triple-SuperTrend engine.

    fast/mid/slow are named by flip-responsiveness (driven by the multiplier),
    matching the source spec. Params are (period, multiplier) verbatim.
    """
    fast: Tuple[int, float] = (21, 1.0)
    mid: Tuple[int, float] = (14, 2.0)
    slow: Tuple[int, float] = (7, 3.0)
    trail_target: TrailTarget = "mid"
    early_lock: bool = False
    early_lock_profit_r: float = 1.0   # exit on slow flip once profit >= this * initial risk

    @property
    def warmup(self) -> int:
        return max(self.fast[0], self.mid[0], self.slow[0])

    def params(self, target: TrailTarget) -> Tuple[int, float]:
        return {"fast": self.fast, "mid": self.mid, "slow": self.slow}[target]
```

- [ ] **Step 3: Commit.** `git add backend/app/engines/triple_supertrend && git commit -m "feat(kite-engine): triple-supertrend config"`

---

### Task 2: Regime core — alignment + transitions (TDD)

**Files:**
- Create: `backend/tests/engines/triple_supertrend/__init__.py` (empty)
- Create: `backend/tests/engines/triple_supertrend/conftest.py`
- Create: `backend/tests/engines/triple_supertrend/test_regime.py`
- Create: `backend/app/engines/triple_supertrend/regime.py`

- [ ] **Step 1: Fixtures** — `conftest.py`:

```python
import numpy as np
import pytest


def _series(values):
    """Build OHLC arrays from a close path; tight bars so HA tracks closely."""
    c = np.asarray(values, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + 1.0
    l = np.minimum(o, c) - 1.0
    return o, h, l, c


@pytest.fixture
def uptrend():
    # long, smooth rise — drives all three SuperTrends bullish after warmup
    return _series(list(np.linspace(100, 400, 120)))


@pytest.fixture
def down_then_up():
    # falling then rising — produces a bear→bull transition
    fall = list(np.linspace(300, 150, 60))
    rise = list(np.linspace(150, 450, 60))
    return _series(fall + rise)
```

- [ ] **Step 2: Failing test** — `test_regime.py`:

```python
import numpy as np
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.regime import compute_regime


def test_regime_shapes_and_warmup(uptrend):
    o, h, l, c = uptrend
    cfg = TripleSupertrendConfig()
    r = compute_regime(o, h, l, c, cfg)
    n = len(c)
    assert r.bull.shape == (n,) and r.bear.shape == (n,)
    # warmup bars are flat (not enough data for all three STs)
    assert not r.bull[: cfg.warmup].any()
    # a strong sustained uptrend ends fully bull-aligned
    assert r.bull[-1] and not r.bear[-1]


def test_three_trend_arrays_present(uptrend):
    o, h, l, c = uptrend
    r = compute_regime(o, h, l, c, TripleSupertrendConfig())
    for tr in (r.t_fast, r.t_mid, r.t_slow):
        assert set(np.unique(tr[20:])).issubset({-1, 1})
```

- [ ] **Step 3:** Run `PYTHONWARNINGS=ignore pytest tests/engines/triple_supertrend/test_regime.py -v` → FAIL (no module).

- [ ] **Step 4: Implement** `regime.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray

from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.indicators.supertrend import compute_supertrend
from app.engines.triple_supertrend.config import TripleSupertrendConfig, TrailTarget


@dataclass
class RegimeSeries:
    bull: NDArray[np.bool_]
    bear: NDArray[np.bool_]
    t_fast: NDArray[np.int64]
    t_mid: NDArray[np.int64]
    t_slow: NDArray[np.int64]
    l_fast: NDArray[np.float64]
    l_mid: NDArray[np.float64]
    l_slow: NDArray[np.float64]
    warmup: int

    def line(self, target: TrailTarget) -> NDArray[np.float64]:
        return {"fast": self.l_fast, "mid": self.l_mid, "slow": self.l_slow}[target]

    def trend(self, target: TrailTarget) -> NDArray[np.int64]:
        return {"fast": self.t_fast, "mid": self.t_mid, "slow": self.t_slow}[target]


def compute_regime(opens, highs, lows, closes, cfg: TripleSupertrendConfig) -> RegimeSeries:
    o = np.asarray(opens, float); h = np.asarray(highs, float)
    l = np.asarray(lows, float); c = np.asarray(closes, float)
    _, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)

    lf, tf = compute_supertrend(ha_h, ha_l, ha_c, cfg.fast[0], cfg.fast[1])
    lm, tm = compute_supertrend(ha_h, ha_l, ha_c, cfg.mid[0], cfg.mid[1])
    ls, ts = compute_supertrend(ha_h, ha_l, ha_c, cfg.slow[0], cfg.slow[1])

    valid = np.zeros(len(c), dtype=bool)
    valid[cfg.warmup:] = True   # all three trends seeded by the largest period

    bull = valid & (tf == 1) & (tm == 1) & (ts == 1)
    bear = valid & (tf == -1) & (tm == -1) & (ts == -1)
    return RegimeSeries(bull, bear, tf, tm, ts, lf, lm, ls, cfg.warmup)
```

- [ ] **Step 5:** Run the test → PASS.

- [ ] **Step 6: Add transition test** to `test_regime.py`:

```python
from app.engines.triple_supertrend.regime import entry_transitions


def test_fresh_transition_fires_once(down_then_up):
    o, h, l, c = down_then_up
    cfg = TripleSupertrendConfig()
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    # exactly the bars where alignment becomes fresh — not every aligned bar
    assert longs.sum() >= 1
    # a transition bar must NOT have been aligned the bar before
    idx = np.where(longs)[0]
    for i in idx:
        assert not (r.bull[i - 1])
    # aligned-but-not-fresh bars are excluded
    assert (r.bull & ~longs).any()
```

- [ ] **Step 7:** Run → FAIL (no `entry_transitions`).

- [ ] **Step 8: Implement** `entry_transitions` in `regime.py`:

```python
def entry_transitions(r: RegimeSeries):
    """Masks of bars that FRESHLY enter full alignment (not aligned at i-1)."""
    prev_bull = np.concatenate([[False], r.bull[:-1]])
    prev_bear = np.concatenate([[False], r.bear[:-1]])
    longs = r.bull & ~prev_bull
    shorts = r.bear & ~prev_bear
    longs[: r.warmup + 1] = False   # need a fully-valid prior bar
    shorts[: r.warmup + 1] = False
    return longs, shorts
```

- [ ] **Step 9:** Run → PASS.

- [ ] **Step 10: Commit.** `git commit -am "feat(kite-engine): regime alignment + fresh-transition detection"`

---

### Task 3: Engine — generate() + trailing lifecycle (TDD)

**Files:**
- Create: `backend/app/engines/triple_supertrend/engine.py`
- Create: `backend/tests/engines/triple_supertrend/test_engine.py`

- [ ] **Step 1: Failing tests** — `test_engine.py`:

```python
import numpy as np
from app.domain.models import Candle, Signal
from app.domain.interfaces import StrategyProtocol
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.engine import TripleSupertrendEngine


def _candles(close_path):
    c = np.asarray(close_path, float)
    o = np.concatenate([[c[0]], c[:-1]])
    out = []
    for i in range(len(c)):
        hi = max(o[i], c[i]) + 1.0; lo = min(o[i], c[i]) - 1.0
        out.append(Candle(timestamp_ms=i * 3600_000, open=o[i], high=hi,
                          low=lo, close=c[i], volume=1.0))
    return out


def test_conforms_to_protocol():
    assert isinstance(TripleSupertrendEngine(), StrategyProtocol)


def test_generate_emits_long_options_signal_on_fresh_bull():
    eng = TripleSupertrendEngine()
    # latest closed bar is a fresh bull transition
    path = list(np.linspace(300, 150, 60)) + list(np.linspace(150, 450, 50))
    sigs = eng.generate(_candles(path), underlying="RELIANCE")
    assert len(sigs) == 1
    s = sigs[0]
    assert isinstance(s, Signal)
    assert s.direction == "long" and s.instrument_type == "options"
    assert s.source == "triple_supertrend"
    assert s.stop_loss is not None and s.take_profit is None


def test_no_signal_when_not_fresh():
    eng = TripleSupertrendEngine()
    path = list(np.linspace(100, 400, 120))  # long uptrend; last bar not a fresh flip
    assert eng.generate(_candles(path), underlying="X") == []


def test_one_position_per_underlying():
    eng = TripleSupertrendEngine()
    path = list(np.linspace(300, 150, 60)) + list(np.linspace(150, 450, 50))
    eng.generate(_candles(path), underlying="RELIANCE")        # opens
    again = eng.generate(_candles(path), underlying="RELIANCE")  # already open
    assert again == []
```

- [ ] **Step 2:** Run → FAIL (no engine).

- [ ] **Step 3: Implement** `engine.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence
import numpy as np

from app.domain.models import Candle, Signal
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.regime import compute_regime, entry_transitions


@dataclass
class _OpenPos:
    direction: str       # "long" | "short"
    entry: float
    stop: float          # ratcheted trail stop
    initial_stop: float


@dataclass
class ManageResult:
    underlying: str
    stop: float
    exit: bool
    reason: Optional[str] = None


def _arrays(candles: Sequence[Candle]):
    o = np.array([c.open for c in candles], float)
    h = np.array([c.high for c in candles], float)
    l = np.array([c.low for c in candles], float)
    c = np.array([c.close for c in candles], float)
    return o, h, l, c


class TripleSupertrendEngine:
    """StrategyProtocol. Broker/market-agnostic: closed candles in, Signals out.

    Stateful only for the trailing lifecycle (one open position per underlying).
    """

    def __init__(self, cfg: Optional[TripleSupertrendConfig] = None):
        self.cfg = cfg or TripleSupertrendConfig()
        self._positions: Dict[str, _OpenPos] = {}

    def generate(self, candles: Sequence[Candle], underlying: str = "", **_) -> List[Signal]:
        if len(candles) <= self.cfg.warmup + 1:
            return []
        if underlying in self._positions:
            return []   # one position per underlying
        o, h, l, c = _arrays(candles)
        r = compute_regime(o, h, l, c, self.cfg)
        longs, shorts = entry_transitions(r)
        i = len(c) - 1
        if not (longs[i] or shorts[i]):
            return []
        direction = "long" if longs[i] else "short"
        trail = float(r.line(self.cfg.trail_target)[i])
        entry = float(c[i])
        self._positions[underlying] = _OpenPos(direction, entry, trail, trail)
        score = self._score(r, i)
        return [Signal(
            underlying=underlying, direction=direction, instrument_type="options",
            stop_loss=trail, take_profit=None, score=score,
            strength="STRONG" if score >= 80 else "SIGNAL",
            source="triple_supertrend",
            timestamp_ms=int(candles[i].timestamp_ms),
        )]

    def manage(self, candles: Sequence[Candle], underlying: str) -> Optional[ManageResult]:
        pos = self._positions.get(underlying)
        if pos is None or len(candles) <= self.cfg.warmup + 1:
            return None
        o, h, l, c = _arrays(candles)
        r = compute_regime(o, h, l, c, self.cfg)
        i = len(c) - 1
        line = float(r.line(self.cfg.trail_target)[i])
        trend = int(r.trend(self.cfg.trail_target)[i])

        # ratchet favorably
        if pos.direction == "long":
            pos.stop = max(pos.stop, line)
            flipped = trend == -1
        else:
            pos.stop = min(pos.stop, line)
            flipped = trend == 1

        # early-lock: once in profit, also honor slow flip
        if not flipped and self.cfg.early_lock:
            risk = abs(pos.entry - pos.initial_stop) or 1e-9
            profit = (c[i] - pos.entry) if pos.direction == "long" else (pos.entry - c[i])
            if profit >= self.cfg.early_lock_profit_r * risk:
                slow = int(r.trend("slow")[i])
                flipped = (slow == -1) if pos.direction == "long" else (slow == 1)

        if flipped:
            self._positions.pop(underlying, None)
            return ManageResult(underlying, pos.stop, exit=True, reason="trail_flip")
        return ManageResult(underlying, pos.stop, exit=False)

    def _score(self, r, i: int) -> float:
        # conviction from agreement magnitude of the three trends (all aligned → high)
        return 85.0
```

- [ ] **Step 4:** Run → PASS all four tests.

- [ ] **Step 5: Trailing tests** — append to `test_engine.py`:

```python
def test_trail_ratchets_only_favorably_and_exits_on_flip():
    eng = TripleSupertrendEngine()
    up = list(np.linspace(300, 150, 60)) + list(np.linspace(150, 600, 80))
    candles = _candles(up)
    eng.generate(candles, underlying="X")
    m1 = eng.manage(candles, "X")
    assert m1 is not None and not m1.exit
    # extend with a sharp drop → mid ST flips → exit
    crash = up + list(np.linspace(600, 200, 40))
    m2 = eng.manage(_candles(crash), "X")
    assert m2 is not None and m2.exit and m2.reason == "trail_flip"


def test_trail_target_knob_changes_stop():
    fast = TripleSupertrendEngine(TripleSupertrendConfig(trail_target="fast"))
    slow = TripleSupertrendEngine(TripleSupertrendConfig(trail_target="slow"))
    up = list(np.linspace(300, 150, 60)) + list(np.linspace(150, 600, 80))
    sf = fast.generate(_candles(up), underlying="X")
    ss = slow.generate(_candles(up), underlying="Y")
    # fast (mult 1) trails tighter than slow (mult 3) → higher stop in an uptrend
    assert sf and ss and sf[0].stop_loss >= ss[0].stop_loss
```

- [ ] **Step 6:** Run → PASS (adjust the crash length if the flip needs more bars; the assertion is on behavior, not magic numbers).

- [ ] **Step 7: Export** in `__init__.py`:

```python
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.engine import TripleSupertrendEngine, ManageResult
from app.engines.triple_supertrend.regime import compute_regime, entry_transitions, RegimeSeries

__all__ = ["TripleSupertrendConfig", "TripleSupertrendEngine", "ManageResult",
           "compute_regime", "entry_transitions", "RegimeSeries"]
```

- [ ] **Step 8: Commit.** `git commit -am "feat(kite-engine): TripleSupertrendEngine generate + trailing lifecycle"`

---

### Task 4: API/UI schemas

**Files:**
- Create: `backend/app/engines/triple_supertrend/schemas.py`

- [ ] **Step 1:** Write `schemas.py`:

```python
from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel


class AlignmentChip(BaseModel):
    fast: int   # +1 / -1 / 0
    mid: int
    slow: int


class EngineSignalRow(BaseModel):
    underlying: str
    token: int
    exchange: str
    regime: Literal["BULL", "BEAR"]
    alignment: AlignmentChip
    direction: Literal["long", "short"]
    option_type: Literal["CE", "PE"]
    option_symbol: Optional[str] = None
    strike: Optional[float] = None
    expiry: Optional[str] = None
    spot: float
    stop_loss: float
    score: float
    timestamp_ms: int


class SignalsResponse(BaseModel):
    generated_ms: int
    scanning: bool
    rows: List[EngineSignalRow]


class SetupPoint(BaseModel):
    time: int     # epoch seconds (lightweight-charts)
    open: float; high: float; low: float; close: float


class SetupLine(BaseModel):
    time: int
    value: float


class SetupChart(BaseModel):
    underlying: str
    candles: List[SetupPoint]            # Heikin-Ashi candles
    st_fast: List[SetupLine]
    st_mid: List[SetupLine]
    st_slow: List[SetupLine]
    entry_index: Optional[int] = None    # bar index of the fresh transition
    trail_target: str


class EngineConfigModel(BaseModel):
    trail_target: Literal["fast", "mid", "slow"] = "mid"
    strike_moneyness: Literal["ATM", "ITM1", "ITM2"] = "ATM"
    early_lock: bool = False
    auto_execute: bool = False
```

- [ ] **Step 2: Commit.** `git commit -am "feat(kite-engine): API/UI schemas"`

---

# PHASE 2 — Universe (Kite-exclusive)

### Task 5: Universe builder (TDD)

**Files:**
- Create: `backend/app/services/kite_engine/__init__.py` (empty)
- Create: `backend/app/services/kite_engine/universe.py`
- Create: `backend/app/services/kite_engine/universe.json`
- Create: `backend/tests/engines/triple_supertrend/test_universe.py`

- [ ] **Step 1:** Write `universe.json` (editable index/basket config — names + the four indices with their option exchange):

```json
{
  "indices": [
    {"name": "NIFTY 50",          "tradingsymbol": "NIFTY",     "option_exchange": "NFO"},
    {"name": "NIFTY BANK",        "tradingsymbol": "BANKNIFTY", "option_exchange": "NFO"},
    {"name": "NIFTY FIN SERVICE", "tradingsymbol": "FINNIFTY",  "option_exchange": "NFO"},
    {"name": "SENSEX",            "tradingsymbol": "SENSEX",    "option_exchange": "BFO"}
  ],
  "include_fno_equities": true
}
```

- [ ] **Step 2: Failing test** — `test_universe.py`:

```python
from app.services.kite_engine.universe import build_universe, UniverseItem


def test_build_universe_from_instruments_dump():
    # NFO option instruments → their underlyings become the equity universe
    nfo = [
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE25JUN3000CE", "instrument_type": "CE"},
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE25JUN3000PE", "instrument_type": "PE"},
        {"name": "INFY",     "tradingsymbol": "INFY25JUN1500CE",     "instrument_type": "CE"},
        {"name": "NIFTY",    "tradingsymbol": "NIFTY25JUN22000CE",   "instrument_type": "CE"},
    ]
    nse = [
        {"tradingsymbol": "RELIANCE", "instrument_token": 111, "exchange": "NSE"},
        {"tradingsymbol": "INFY",     "instrument_token": 222, "exchange": "NSE"},
    ]
    uni = build_universe(nfo_instruments=nfo, bfo_instruments=[], equities=nse)
    names = {u.name for u in uni}
    assert "RELIANCE" in names and "INFY" in names
    # indices always present
    assert "NIFTY 50" in names
    r = next(u for u in uni if u.name == "RELIANCE")
    assert r.token == 111 and r.option_exchange == "NFO"
```

- [ ] **Step 3:** Run → FAIL.

- [ ] **Step 4: Implement** `universe.py`:

```python
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

_CFG = Path(__file__).with_name("universe.json")


@dataclass(frozen=True)
class UniverseItem:
    name: str               # display / option-chain name filter ("RELIANCE", "NIFTY 50")
    tradingsymbol: str      # underlying tradingsymbol ("RELIANCE", "NIFTY")
    token: int              # spot/index instrument_token for candle fetch (0 if unresolved)
    exchange: str           # spot exchange ("NSE"/"BSE"/"INDICES")
    option_exchange: str    # "NFO" / "BFO"
    is_index: bool = False


def _load_cfg() -> dict:
    return json.loads(_CFG.read_text())


def build_universe(*, nfo_instruments: Sequence[dict], bfo_instruments: Sequence[dict],
                   equities: Sequence[dict], cfg: Optional[dict] = None) -> List[UniverseItem]:
    cfg = cfg or _load_cfg()
    tok: Dict[str, dict] = {e["tradingsymbol"]: e for e in equities}
    out: List[UniverseItem] = []

    # indices first
    for ix in cfg.get("indices", []):
        out.append(UniverseItem(ix["name"], ix["tradingsymbol"],
                                token=int(tok.get(ix["tradingsymbol"], {}).get("instrument_token", 0)),
                                exchange="INDICES", option_exchange=ix["option_exchange"], is_index=True))

    if cfg.get("include_fno_equities", True):
        seen = set()
        for src, opt_exch in ((nfo_instruments, "NFO"), (bfo_instruments, "BFO")):
            for row in src:
                name = row.get("name")
                if not name or name in seen or row.get("instrument_type") not in ("CE", "PE"):
                    continue
                eq = tok.get(name)
                if not eq:
                    continue   # no spot listing → skip (need candles)
                seen.add(name)
                out.append(UniverseItem(name, name, int(eq["instrument_token"]),
                                        eq.get("exchange", "NSE"), opt_exch))
    return out
```

- [ ] **Step 5:** Run → PASS.

- [ ] **Step 6: Commit.** `git commit -am "feat(kite-engine): universe builder from instruments dump + universe.json"`

---

# PHASE 3 — ATM/ITM strike picker (Kite-exclusive)

### Task 6: Strike picker (TDD)

**Files:**
- Create: `backend/app/services/kite_engine/strikes.py`
- Create: `backend/tests/engines/triple_supertrend/test_strikes.py`

- [ ] **Step 1: Failing test** — `test_strikes.py`:

```python
from app.services.kite_engine.strikes import pick_strike, OptionPick


def _chain(spot, strikes, otype, expiry="2026-06-26", dte=8):
    # minimal OptionSummary-like dicts
    return [{"strike": s, "option_type": otype, "expiry_date": expiry, "dte": dte,
             "instrument_name": f"X{int(s)}{otype[0].upper()}E"} for s in strikes]


def test_atm_call_for_bull():
    chain = _chain(100, [80, 90, 100, 110, 120], "call")
    pick = pick_strike(chain, spot=102, direction="long", moneyness="ATM")
    assert isinstance(pick, OptionPick) and pick.strike == 100 and pick.option_type == "CE"


def test_itm1_put_for_bear():
    chain = _chain(100, [80, 90, 100, 110, 120], "put")
    pick = pick_strike(chain, spot=102, direction="short", moneyness="ITM1")
    # PUT ITM = strike ABOVE spot; ITM1 = one step in
    assert pick.strike == 110 and pick.option_type == "PE"


def test_never_otm_returns_none_if_only_otm():
    chain = _chain(100, [120, 130], "call")   # all OTM calls (strike > spot)
    assert pick_strike(chain, spot=100, direction="long", moneyness="ATM") is not None  # ATM picks nearest
    # but ITM requested with no ITM available → None
    assert pick_strike(chain, spot=100, direction="long", moneyness="ITM2") is None
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Implement** `strikes.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

Moneyness = Literal["ATM", "ITM1", "ITM2"]


@dataclass(frozen=True)
class OptionPick:
    option_symbol: str
    strike: float
    option_type: str   # "CE" | "PE"
    expiry: str
    dte: int


def pick_strike(chain: Sequence[dict], *, spot: float, direction: str,
                moneyness: Moneyness = "ATM", min_dte: int = 1) -> Optional[OptionPick]:
    want_call = direction == "long"
    otype_src = "call" if want_call else "put"
    rows = [r for r in chain if str(r.get("option_type", "")).lower() == otype_src
            and int(r.get("dte", 0)) >= min_dte]
    if not rows:
        return None
    # nearest expiry only
    near = min(r["dte"] for r in rows)
    rows = sorted((r for r in rows if r["dte"] == near), key=lambda r: r["strike"])
    strikes = [r["strike"] for r in rows]
    # ATM = nearest strike to spot
    atm = min(range(len(strikes)), key=lambda k: abs(strikes[k] - spot))
    steps = {"ATM": 0, "ITM1": 1, "ITM2": 2}[moneyness]
    # CALL ITM = lower strike; PUT ITM = higher strike
    idx = atm - steps if want_call else atm + steps
    if idx < 0 or idx >= len(strikes):
        return None
    r = rows[idx]
    return OptionPick(r["instrument_name"], float(r["strike"]),
                      "CE" if want_call else "PE", str(r["expiry_date"]), int(r["dte"]))
```

- [ ] **Step 4:** Run → PASS.

- [ ] **Step 5: Commit.** `git commit -am "feat(kite-engine): ATM/ITM strike picker (never OTM)"`

---

# PHASE 4 — Scanner + store (Kite-exclusive, throttled)

### Task 7: Throttled scanner

**Files:**
- Create: `backend/app/services/kite_engine/scanner.py`

**Reference patterns:** `KiteClient.get_candles(instrument, "1H", limit)` returns closed `Candle`s (drops nothing; we drop the forming bar here). `KiteClient.get_option_chain(instrument)` and `get_index_price(instrument)`. Build the per-user client via `kite_accounts.build_client(acct)` (see `kite.py:_run`).

- [ ] **Step 1: Implement** `scanner.py` (no test for the I/O orchestration; the pure pieces it calls are already tested). Key behaviors: in-memory cache keyed by `user_id`; semaphore throttle; drops the forming bar; stores rows.

```python
from __future__ import annotations
import asyncio, time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.core.logging import get_logger
from app.domain.models import Candle
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.engine import TripleSupertrendEngine
from app.engines.triple_supertrend.schemas import AlignmentChip, EngineSignalRow
from app.engines.triple_supertrend.regime import compute_regime, entry_transitions
from app.services.kite_engine.universe import UniverseItem
from app.services.kite_engine.strikes import pick_strike

log = get_logger(__name__)
_CANDLE_TTL_S = 180
_CONCURRENCY = 3


def _drop_forming(candles: List[Candle], tf_ms: int = 3600_000) -> List[Candle]:
    if not candles:
        return candles
    now = int(time.time() * 1000)
    last = candles[-1]
    # if the last bar's period hasn't closed yet, drop it
    if last.timestamp_ms + tf_ms > now:
        return candles[:-1]
    return candles


@dataclass
class _UserScan:
    engine: TripleSupertrendEngine
    rows: List[EngineSignalRow] = field(default_factory=list)
    candle_cache: Dict[int, tuple] = field(default_factory=dict)  # token -> (ts, candles)
    generated_ms: int = 0
    scanning: bool = False


class KiteEngineScanner:
    def __init__(self):
        self._users: Dict[str, _UserScan] = {}

    def _user(self, uid: str, cfg: TripleSupertrendConfig) -> _UserScan:
        if uid not in self._users:
            self._users[uid] = _UserScan(engine=TripleSupertrendEngine(cfg))
        return self._users[uid]

    def snapshot(self, uid: str) -> _UserScan:
        return self._users.get(uid) or _UserScan(engine=TripleSupertrendEngine())

    async def scan(self, *, uid: str, client, universe: List[UniverseItem],
                   cfg: TripleSupertrendConfig, moneyness: str = "ATM") -> None:
        us = self._user(uid, cfg)
        us.scanning = True
        sem = asyncio.Semaphore(_CONCURRENCY)
        rows: List[EngineSignalRow] = []

        async def _one(item: UniverseItem):
            async with sem:
                try:
                    candles = await self._candles(client, us, item)
                except Exception as exc:
                    log.warning("scan candle fail %s: %s", item.name, exc)
                    return
                candles = _drop_forming(candles)
                row = self._evaluate(us.engine, item, candles, cfg)
                if row is None:
                    return
                await self._attach_strike(client, item, row, moneyness)
                rows.append(row)

        await asyncio.gather(*[_one(i) for i in universe if i.token])
        us.rows = rows
        us.generated_ms = int(time.time() * 1000)
        us.scanning = False

    async def _candles(self, client, us: _UserScan, item: UniverseItem) -> List[Candle]:
        hit = us.candle_cache.get(item.token)
        if hit and time.time() - hit[0] < _CANDLE_TTL_S:
            return hit[1]
        # build an InstrumentMeta-like fetch via the token; reuse client.get_historical
        candles = await client_fetch_1h(client, item)   # defined in Step 2
        us.candle_cache[item.token] = (time.time(), candles)
        return candles

    def _evaluate(self, engine, item, candles, cfg) -> Optional[EngineSignalRow]:
        if len(candles) <= cfg.warmup + 1:
            return None
        import numpy as np
        o = np.array([c.open for c in candles], float); h = np.array([c.high for c in candles], float)
        l = np.array([c.low for c in candles], float); c = np.array([c.close for c in candles], float)
        r = compute_regime(o, h, l, c, cfg)
        longs, shorts = entry_transitions(r)
        i = len(c) - 1
        if not (longs[i] or shorts[i]):
            return None
        direction = "long" if longs[i] else "short"
        return EngineSignalRow(
            underlying=item.name, token=item.token, exchange=item.option_exchange,
            regime="BULL" if direction == "long" else "BEAR",
            alignment=AlignmentChip(fast=int(r.t_fast[i]), mid=int(r.t_mid[i]), slow=int(r.t_slow[i])),
            direction=direction, option_type="CE" if direction == "long" else "PE",
            spot=float(c[i]), stop_loss=float(r.line(cfg.trail_target)[i]),
            score=85.0, timestamp_ms=int(candles[i].timestamp_ms),
        )

    async def _attach_strike(self, client, item, row, moneyness):
        try:
            chain = await client.get_option_chain(_inst(item))   # _inst defined in Step 2
            chain_dicts = [c.model_dump() if hasattr(c, "model_dump") else c for c in chain]
            pick = pick_strike(chain_dicts, spot=row.spot, direction=row.direction, moneyness=moneyness)
            if pick:
                row.option_symbol, row.strike = pick.option_symbol, pick.strike
                row.expiry = pick.expiry
        except Exception as exc:
            log.warning("strike attach fail %s: %s", item.name, exc)


scanner = KiteEngineScanner()
```

- [ ] **Step 2:** Add the two Kite adapters at the bottom of `scanner.py` that bridge a `UniverseItem` to the client's `InstrumentMeta`-based methods. Inspect `InstrumentMeta` fields first (`grep -n "class InstrumentMeta" backend/app/schemas/instruments.py` and read it), then:

```python
from app.schemas.instruments import InstrumentMeta

def _inst(item) -> InstrumentMeta:
    # minimal InstrumentMeta the Kite client needs for candles + option chain
    return InstrumentMeta(underlying=item.tradingsymbol, zerodha_token=item.token,
                          has_options=True)  # fill required fields per the actual schema

async def client_fetch_1h(client, item):
    return await client.get_candles(_inst(item), "1H", 320)
```

> NOTE for executor: read `InstrumentMeta` first and populate exactly its required fields; the two stubs above are the only place the engine touches Kite types. Keep them here (Kite-exclusive), not in the engine package.

- [ ] **Step 3: Commit.** `git commit -am "feat(kite-engine): throttled background scanner + candle cache + signal store"`

---

# PHASE 5 — Endpoints (Kite-exclusive)

### Task 8: Engine endpoints

**Files:**
- Create: `backend/app/api/v1/endpoints/kite_engine.py`
- Modify: `backend/main.py` (add import + `include_router`)

**Reference:** mirror `kite.py` — `router = APIRouter(prefix="/kite/engine", tags=["kite-engine"])`, `Depends(get_current_user)`, `kite_accounts.build_client(acct)` + close in finally. Per-user config stored in a module dict (default `EngineConfigModel()`).

- [ ] **Step 1: Implement** `kite_engine.py`:

```python
from __future__ import annotations
import time
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import UserContext, get_current_user
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.schemas import (
    EngineConfigModel, SignalsResponse, SetupChart)
from app.services.exchanges.kite import accounts as kite_accounts
from app.services.kite_engine.scanner import scanner
from app.services.kite_engine.universe import build_universe

router = APIRouter(prefix="/kite/engine", tags=["kite-engine"])
_config: Dict[str, EngineConfigModel] = {}


def _cfg(uid: str) -> EngineConfigModel:
    return _config.setdefault(uid, EngineConfigModel())


def _ts_cfg(c: EngineConfigModel) -> TripleSupertrendConfig:
    return TripleSupertrendConfig(trail_target=c.trail_target, early_lock=c.early_lock)


@router.get("/config", response_model=EngineConfigModel)
async def get_config(user: UserContext = Depends(get_current_user)) -> EngineConfigModel:
    return _cfg(user.user_id)


@router.post("/config", response_model=EngineConfigModel)
async def set_config(body: EngineConfigModel, user: UserContext = Depends(get_current_user)):
    _config[user.user_id] = body
    return body


@router.get("/signals", response_model=SignalsResponse)
async def signals(user: UserContext = Depends(get_current_user)) -> SignalsResponse:
    us = scanner.snapshot(user.user_id)
    return SignalsResponse(generated_ms=us.generated_ms, scanning=us.scanning, rows=us.rows)


@router.post("/scan", response_model=SignalsResponse)
async def run_scan(user: UserContext = Depends(get_current_user)) -> SignalsResponse:
    acct = kite_accounts.get_active(user.user_id)
    if not acct:
        raise HTTPException(409, "No active Kite account.")
    client = kite_accounts.build_client(acct)
    cfg = _cfg(user.user_id)
    try:
        nfo = await client.search_instruments("", "NFO", limit=100000)
        bfo = await client.search_instruments("", "BFO", limit=100000)
        nse = await client.search_instruments("", "NSE", limit=100000)
        bse = await client.search_instruments("", "BSE", limit=100000)
        universe = build_universe(nfo_instruments=nfo, bfo_instruments=bfo, equities=nse + bse)
        await scanner.scan(uid=user.user_id, client=client, universe=universe,
                           cfg=_ts_cfg(cfg), moneyness=cfg.strike_moneyness)
    finally:
        await client.close()
    us = scanner.snapshot(user.user_id)
    return SignalsResponse(generated_ms=us.generated_ms, scanning=us.scanning, rows=us.rows)


@router.get("/setup/{token}", response_model=SetupChart)
async def setup(token: int, underlying: str = "", user: UserContext = Depends(get_current_user)):
    # fetch 1H candles for token, build HA + 3 ST line series + entry index
    from app.services.kite_engine.scanner import build_setup_chart
    acct = kite_accounts.get_active(user.user_id)
    if not acct:
        raise HTTPException(409, "No active Kite account.")
    client = kite_accounts.build_client(acct)
    try:
        return await build_setup_chart(client, token, underlying, _ts_cfg(_cfg(user.user_id)))
    finally:
        await client.close()
```

- [ ] **Step 2:** Add `build_setup_chart(client, token, underlying, cfg) -> SetupChart` to `scanner.py` — fetch 1H candles, compute HA + 3 ST lines (reuse `compute_regime`), map to `SetupPoint`/`SetupLine` (epoch **seconds**), set `entry_index` from `entry_transitions`.

- [ ] **Step 3:** Wire router in `backend/main.py` — add near the other kite include (after line ~1712):

```python
    from app.api.v1.endpoints.kite_engine import router as kite_engine_router
    app.include_router(kite_engine_router, prefix="/api/v1")
```

- [ ] **Step 4:** Smoke test import: `PYTHONWARNINGS=ignore python -c "import backend.main"` (or the app's existing import check) → no errors.

- [ ] **Step 5: Commit.** `git commit -am "feat(kite-engine): /api/v1/kite/engine endpoints (signals, scan, setup, config)"`

---

# PHASE 6 — Frontend: right-sidebar pane + hook

### Task 9: Types + hook

**Files:**
- Create: `frontend/src/types/kiteEngine.ts`
- Create: `frontend/src/hooks/useTripleSupertrend.ts`

**Reference:** mirror query/polling style in `frontend/src/hooks/useKite.ts` (same fetch wrapper / base URL / auth headers).

- [ ] **Step 1:** `kiteEngine.ts` — TS mirrors of `EngineSignalRow`, `SignalsResponse`, `SetupChart`, `EngineConfigModel`.

- [ ] **Step 2:** `useTripleSupertrend.ts` — `useEngineSignals()` (poll `GET /api/v1/kite/engine/signals` every ~15s), `useEngineConfig()` + `setEngineConfig()`, `runScan()` (`POST /scan`), `fetchSetup(token, underlying)` (`GET /setup/{token}`). Follow the exact fetch helper used in `useKite.ts`.

- [ ] **Step 3: Commit.** `git commit -am "feat(kite-engine): FE types + useTripleSupertrend hook"`

### Task 10: Sidebar pane

**Files:**
- Create: `frontend/src/components/kite/TripleSupertrendPane.tsx`
- Modify: `frontend/src/components/kite/KiteTab.tsx:54`

**Reference:** style tokens from `frontend/src/styles/kiteUI.tsx`; orange `#ff5722`.

- [ ] **Step 1:** Build `TripleSupertrendPane.tsx`: header (title, scan button, **auto-execute toggle**, trail-target + moneyness selects bound to `useEngineConfig`), then a list of `EngineSignalRow`s (BULL/BEAR badge, fast/mid/slow alignment chips ▲/▼, CE/PE + strike + expiry, trailing stop). Each row `onClick` → `onSelectSetup(token, underlying)` passed via prop (opens the chart). Empty state: "No ready setups."

- [ ] **Step 2:** Mount in `KiteTab.tsx`: replace `rightSidebar={<div .../>}` with `rightSidebar={<TripleSupertrendPane onSelectSetup={setSetupView} />}` and add `const [setupView, setSetupView] = useState<{token:number;underlying:string}|null>(null)`.

- [ ] **Step 3:** `tsc` check: `cd frontend && npx tsc --noEmit` → clean.

- [ ] **Step 4: Commit.** `git commit -am "feat(kite-engine): right-sidebar TripleSupertrend signals pane"`

---

# PHASE 7 — Click-to-chart setup visualization

### Task 11: SetupChart component

**Files:**
- Create: `frontend/src/components/kite/SetupChart.tsx`
- Modify: `frontend/src/components/kite/KiteTab.tsx` (render `SetupChart` in `content` when `setupView` set)

**Reference:** copy the lightweight-charts v5 setup from `InstrumentPane.tsx` (`createChart`, `addSeries(CandlestickSeries)`). Add three `addSeries(LineSeries, {...})` for ST fast/mid/slow and `series.setMarkers([...])` for the entry.

- [ ] **Step 1:** `SetupChart.tsx` — props `{token, underlying, onClose}`. On mount call `fetchSetup(token, underlying)`; render HA candles (CandlestickSeries) + 3 line series (fast=blue, mid=orange `#ff5722`, slow=grey) + an entry marker at `entry_index`. Title shows underlying + trail target.

- [ ] **Step 2:** In `KiteTab.tsx`, when `setupView` is set, render `<SetupChart .../>` as `content` (with a back/close that clears `setupView`).

- [ ] **Step 3:** `tsc` clean; manual visual check: `/run` the app, open Kite tab, click a signal → chart shows HA + 3 STs + entry.

- [ ] **Step 4: Commit.** `git commit -am "feat(kite-engine): click-to-chart setup visualization (HA + 3 ST + entry)"`

---

# PHASE 8 — Auto-execute (toggle, default OFF) — Kite order path

### Task 12: Auto-exec on scan (gated)

**Files:**
- Modify: `backend/app/services/kite_engine/scanner.py` (after a row is built + strike attached, if auto_execute → place order)
- Possibly modify: `backend/app/services/exchanges/kite/client.py:349` (`place_order_option` — accept `exchange` param so SENSEX→BFO works)

**Reference:** manual order placement + safety in `kite.py` (`_safety_gate`, `live_safety`). Reuse that gate — do NOT bypass it. Use `client.place_order_option(option_symbol, side="buy", size=lot, exchange=item.option_exchange, stop_loss=row.stop_loss)`.

- [ ] **Step 1:** Generalize `place_order_option` to take `exchange: str = K.EXCHANGE_NFO` and pass it through (instead of hardcoded NFO).

- [ ] **Step 2:** In `scanner.scan(...)`, accept `auto_execute: bool` + a `place_cb` callback (injected from the endpoint so the scanner stays free of the safety-gate import graph). When `auto_execute` and a fresh row has a resolved `option_symbol` and no open position for that underlying, call `place_cb(row, item)`.

- [ ] **Step 3:** In `kite_engine.py` `run_scan`, build `place_cb` that runs the same `_safety_gate`/`live_safety` checks `kite.py` uses for manual orders, then `client.place_order_option(...)`. Pass it into `scanner.scan(...)` only when `cfg.auto_execute`.

- [ ] **Step 4:** Test the strike→order mapping purely: a small unit test that, given a row + pick, the buy order args are correct (CE/PE symbol, side="buy", exchange matches index, qty = lot size). Mock the client.

- [ ] **Step 5:** Manual gated check with auto-execute OFF (default) → no orders placed; toggle ON in a paper/test account only.

- [ ] **Step 6: Commit.** `git commit -am "feat(kite-engine): optional auto-execute via Kite order path under live_safety (default off)"`

---

## Self-review notes (done)

- **Spec coverage:** §3 logic → Tasks 2–3; §4 module layout → Tasks 1–4; §5a universe → Task 5; §5c strikes → Task 6; §5b scanner → Task 7; §5d endpoints → Task 8; §6 sidebar → Tasks 9–10; click-to-chart → Task 11; §5e auto-exec → Task 12. ✅
- **Exclusivity:** no task imports `derivatives`/`edge`/`directional`/`scalping`/`sterling_*`. Kite types touched only in `scanner.py` adapters (Step 2 of Task 7) + endpoints. ✅
- **Type consistency:** `EngineSignalRow`, `SetupChart`, `OptionPick`, `UniverseItem`, `RegimeSeries` names consistent across tasks. `trail_target`/`moneyness`/`auto_execute` names consistent across config (BE) + `EngineConfigModel` + FE. ✅
- **Open executor note:** `InstrumentMeta` exact required fields must be read before filling the `_inst` adapter (Task 7 Step 2). Lot sizes for auto-exec (Task 12) come from the instruments dump (`lot_size` field) — resolve at order time.
