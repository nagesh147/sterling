# Real-Time IV Stream — Component ① (IV Stream Manager) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A start-gated WebSocket client that streams Delta Exchange India `mark_price`
IV/Greeks for all listed option chains (≤45 DTE) and exposes the latest per-strike IV in memory.

**Architecture:** Module singleton `DeltaIVManager` mirroring `delta_l2_socket.DeltaL2Manager`.
A pure parse/handle core (`IVTick`, `_parse_symbol`, `_dte`, `_handle_message`, `_subs_from_products`)
is unit-tested without a socket; the async `_listen`/`discover_subscriptions` do network I/O and
are started only when `STERLING_IV_STREAM=1`.

**Tech Stack:** Python asyncio, `websockets` 16.0, `httpx` (REST discovery), `pytest` (`asyncio_mode=auto`).

**Working dir:** all paths relative to `backend/`. Run pytest from `backend/` via `.venv/bin/python -m pytest`.

---

### Task 1: `IVTick`, symbol parser, DTE helper (pure core)

**Files:**
- Create: `app/services/delta_iv_socket.py`
- Test: `tests/test_delta_iv_socket.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_delta_iv_socket.py
import datetime as dt
from app.services.delta_iv_socket import _parse_symbol, _dte, ParsedSym


def test_parse_symbol_call_and_put():
    assert _parse_symbol("C-BTC-105000-270625") == ParsedSym("call", "BTC", 105000.0, "270625")
    assert _parse_symbol("P-ETH-3200-280625") == ParsedSym("put", "ETH", 3200.0, "280625")
    assert _parse_symbol("MARK:C-BTC-105000-270625") == ParsedSym("call", "BTC", 105000.0, "270625")


def test_parse_symbol_rejects_bad():
    assert _parse_symbol("BTCUSD") is None
    assert _parse_symbol("X-BTC-100-270625") is None
    assert _parse_symbol("") is None


def test_dte_ddmmyy():
    # 27 Jun 2025 from a reference date of 20 Jun 2025 -> 7 days
    ref = dt.date(2025, 6, 20)
    assert _dte("270625", today=ref) == 7
    assert _dte("200625", today=ref) == 0
    assert _dte("130625", today=ref) == -7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -q`
Expected: FAIL — `ImportError: cannot import name '_parse_symbol'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/delta_iv_socket.py
import asyncio
import datetime as dt
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx
import websockets

log = logging.getLogger(__name__)

_BASE = "https://api.india.delta.exchange"
_WS = "wss://socket.india.delta.exchange"
MAX_DTE = 45


@dataclass(frozen=True)
class ParsedSym:
    option_type: str   # "call" | "put"
    underlying: str
    strike: float
    expiry: str        # "DDMMYY"


def _parse_symbol(symbol: str) -> Optional[ParsedSym]:
    if not symbol:
        return None
    s = symbol.split(":", 1)[1] if symbol.startswith("MARK:") else symbol
    parts = s.split("-")
    if len(parts) != 4 or parts[0] not in ("C", "P"):
        return None
    try:
        return ParsedSym(
            "call" if parts[0] == "C" else "put",
            parts[1],
            float(parts[2]),
            parts[3],
        )
    except (ValueError, IndexError):
        return None


def _dte(expiry_ddmmyy: str, today: Optional[dt.date] = None) -> int:
    today = today or dt.datetime.utcnow().date()
    try:
        d = int(expiry_ddmmyy[0:2]); m = int(expiry_ddmmyy[2:4]); y = 2000 + int(expiry_ddmmyy[4:6])
        return (dt.date(y, m, d) - today).days
    except (ValueError, IndexError):
        return -1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/delta_iv_socket.py tests/test_delta_iv_socket.py
git commit -m "feat(iv-stream): IVTick symbol parser + DTE helper"
```

---

### Task 2: `IVTick` + `_handle_message` (parse a live tick into latest state)

**Files:**
- Modify: `app/services/delta_iv_socket.py`
- Test: `tests/test_delta_iv_socket.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_delta_iv_socket.py
import datetime as dt
from app.services.delta_iv_socket import DeltaIVManager

SAMPLE = {
    "type": "mark_price",
    "symbol": "MARK:C-BTC-105000-270625",
    "price": "3910.088012",
    "implied_volatility": "0.6523",
    "bid_iv": "0.6480", "ask_iv": "0.6560",
    "best_bid": "3890.00", "best_ask": "3930.00",
    "delta": "0.42", "gamma": "0.0003", "theta": "-45.20",
    "vega": "180.50", "rho": "12.30",
    "timestamp": 1671867039712836,
}


def test_handle_message_stores_latest_tick():
    m = DeltaIVManager(today=dt.date(2025, 6, 20))
    m._handle_message(SAMPLE)
    t = m.get("C-BTC-105000-270625")
    assert t is not None
    assert t.underlying == "BTC" and t.option_type == "call" and t.strike == 105000.0
    assert t.mark_iv == 0.6523 and t.bid_iv == 0.6480 and t.ask_iv == 0.6560
    assert t.delta == 0.42 and t.theta == -45.20 and t.vega == 180.50
    assert t.ts_exchange == 1671867039712836 / 1e6
    assert m.last_update_ts("BTC") == t.ts_local


def test_handle_message_ignores_non_markprice_and_garbage():
    m = DeltaIVManager()
    m._handle_message({"type": "l2_orderbook", "symbol": "BTCUSD"})
    m._handle_message({"type": "mark_price", "symbol": "NONSENSE"})
    assert m.get("BTCUSD") is None
    assert m.chain("BTC") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -q`
Expected: FAIL — `ImportError: cannot import name 'DeltaIVManager'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to app/services/delta_iv_socket.py

@dataclass
class IVTick:
    option_symbol: str
    underlying: str
    option_type: str
    strike: float
    expiry: str
    dte: int
    mark_iv: float
    bid_iv: float
    ask_iv: float
    mark_price: float
    best_bid: float
    best_ask: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    ts_exchange: float
    ts_local: float


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


class DeltaIVManager:
    def __init__(self, today: Optional[dt.date] = None, max_dte: int = MAX_DTE):
        self.ticks: Dict[str, IVTick] = {}
        self._last_update: Dict[str, float] = {}
        self._subs: List[str] = []
        self._today = today
        self.max_dte = max_dte
        self._running = False
        self._task = None

    def _handle_message(self, data: dict) -> None:
        if not isinstance(data, dict) or data.get("type") != "mark_price":
            return
        parsed = _parse_symbol(data.get("symbol", ""))
        if parsed is None:
            return
        sym = data["symbol"].split(":", 1)[1] if str(data["symbol"]).startswith("MARK:") else data["symbol"]
        now = time.time()
        tick = IVTick(
            option_symbol=sym, underlying=parsed.underlying, option_type=parsed.option_type,
            strike=parsed.strike, expiry=parsed.expiry, dte=_dte(parsed.expiry, self._today),
            mark_iv=_f(data.get("implied_volatility")), bid_iv=_f(data.get("bid_iv")),
            ask_iv=_f(data.get("ask_iv")), mark_price=_f(data.get("price")),
            best_bid=_f(data.get("best_bid")), best_ask=_f(data.get("best_ask")),
            delta=_f(data.get("delta")), gamma=_f(data.get("gamma")), theta=_f(data.get("theta")),
            vega=_f(data.get("vega")), rho=_f(data.get("rho")),
            ts_exchange=_f(data.get("timestamp")) / 1e6, ts_local=now,
        )
        self.ticks[sym] = tick
        self._last_update[parsed.underlying] = now

    def get(self, option_symbol: str) -> Optional[IVTick]:
        return self.ticks.get(option_symbol)

    def chain(self, underlying: str) -> List[IVTick]:
        u = underlying.upper()
        return [t for t in self.ticks.values() if t.underlying == u]

    def last_update_ts(self, underlying: str) -> Optional[float]:
        return self._last_update.get(underlying.upper())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/delta_iv_socket.py tests/test_delta_iv_socket.py
git commit -m "feat(iv-stream): IVTick + _handle_message latest-tick store"
```

---

### Task 3: Read API — `atm_iv` + `is_fresh`

**Files:**
- Modify: `app/services/delta_iv_socket.py`
- Test: `tests/test_delta_iv_socket.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_delta_iv_socket.py
import time as _time


def _mk(m, sym, iv):
    msg = dict(SAMPLE); msg["symbol"] = sym; msg["implied_volatility"] = str(iv)
    m._handle_message(msg)


def test_atm_iv_picks_nearest_expiry_then_strike():
    m = DeltaIVManager(today=dt.date(2025, 6, 20))
    _mk(m, "C-BTC-100000-270625", 0.50)   # dte 7, strike 100k
    _mk(m, "C-BTC-110000-270625", 0.70)   # dte 7, strike 110k
    _mk(m, "C-BTC-100000-040725", 0.99)   # dte 14, strike 100k
    # spot 101000, target dte 7 -> expiry 270625, nearest strike 100000 -> iv 0.50
    assert m.atm_iv("BTC", dte=7, spot=101000) == 0.50
    # target dte 13 -> nearest expiry is 14 (040725) -> 0.99
    assert m.atm_iv("BTC", dte=13, spot=100000) == 0.99
    assert m.atm_iv("ETH", dte=7, spot=3000) is None


def test_is_fresh():
    m = DeltaIVManager(today=dt.date(2025, 6, 20))
    assert m.is_fresh("BTC") is False
    _mk(m, "C-BTC-100000-270625", 0.50)
    assert m.is_fresh("BTC", max_age_s=10) is True
    m._last_update["BTC"] = _time.time() - 100
    assert m.is_fresh("BTC", max_age_s=10) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -k "atm_iv or is_fresh" -q`
Expected: FAIL — `AttributeError: 'DeltaIVManager' object has no attribute 'atm_iv'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add methods to DeltaIVManager
    def atm_iv(self, underlying: str, dte: int, spot: float) -> Optional[float]:
        cohort = [t for t in self.chain(underlying) if t.mark_iv > 0]
        if not cohort:
            return None
        target_dte = min({t.dte for t in cohort}, key=lambda d: abs(d - dte))
        same_exp = [t for t in cohort if t.dte == target_dte]
        best = min(same_exp, key=lambda t: abs(t.strike - spot))
        return best.mark_iv

    def is_fresh(self, underlying: str, max_age_s: float = 10.0) -> bool:
        ts = self._last_update.get(underlying.upper())
        return ts is not None and (time.time() - ts) <= max_age_s
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/delta_iv_socket.py tests/test_delta_iv_socket.py
git commit -m "feat(iv-stream): atm_iv (nearest expiry+strike) + is_fresh staleness"
```

---

### Task 4: Subscription discovery from `/v2/products`

**Files:**
- Modify: `app/services/delta_iv_socket.py`
- Test: `tests/test_delta_iv_socket.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_delta_iv_socket.py
from app.services.delta_iv_socket import _subs_from_products


def test_subs_from_products_filters_dte_and_dedups():
    today = dt.date(2025, 6, 20)
    products = [
        {"symbol": "C-BTC-100000-270625"},   # dte 7   keep
        {"symbol": "P-BTC-90000-270625"},    # dte 7   keep (same expiry -> dedup to BTC-270625)
        {"symbol": "C-ETH-3000-040725"},     # dte 14  keep
        {"symbol": "C-BTC-100000-200825"},   # dte 61  drop (>45)
        {"symbol": "BTCUSD"},                # not an option  drop
    ]
    subs = _subs_from_products(products, max_dte=45, today=today)
    assert subs == ["BTC-270625", "ETH-040725"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -k subs_from_products -q`
Expected: FAIL — `ImportError: cannot import name '_subs_from_products'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to app/services/delta_iv_socket.py (module level)
def _subs_from_products(products: list, max_dte: int, today: Optional[dt.date] = None) -> List[str]:
    subs = set()
    for p in products:
        parsed = _parse_symbol(str(p.get("symbol", "")))
        if parsed is None:
            continue
        d = _dte(parsed.expiry, today)
        if 0 <= d <= max_dte:
            subs.add(f"{parsed.underlying}-{parsed.expiry}")
    return sorted(subs)


async def _fetch_option_products() -> list:
    """Page all live option products from Delta India public REST."""
    out: list = []
    params = {"contract_types": "call_options,put_options", "page_size": 200}
    async with httpx.AsyncClient(base_url=_BASE, timeout=10.0) as c:
        after = None
        for _ in range(50):  # hard page cap
            q = dict(params)
            if after:
                q["after"] = after
            r = await c.get("/v2/products", params=q)
            r.raise_for_status()
            body = r.json()
            out.extend(body.get("result") or [])
            after = (body.get("meta") or {}).get("after")
            if not after:
                break
    return out
```

```python
# add method to DeltaIVManager
    async def discover_subscriptions(self) -> List[str]:
        try:
            products = await _fetch_option_products()
            self._subs = _subs_from_products(products, self.max_dte, self._today)
        except Exception as e:  # keep last-known subs on failure
            log.warning("IV discover failed, keeping %d subs: %s", len(self._subs), e)
        return self._subs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/delta_iv_socket.py tests/test_delta_iv_socket.py
git commit -m "feat(iv-stream): /v2/products discovery -> dte<=45 chain subscriptions"
```

---

### Task 5: Listener loop + start/stop lifecycle + singleton

**Files:**
- Modify: `app/services/delta_iv_socket.py`
- Test: `tests/test_delta_iv_socket.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_delta_iv_socket.py
import asyncio
from app.services.delta_iv_socket import iv_manager


def test_singleton_exists_and_not_started_on_import():
    assert isinstance(iv_manager, DeltaIVManager)
    assert iv_manager._running is False   # import must NOT open a socket


def test_start_stop_toggles_running():
    async def run():
        m = DeltaIVManager()
        # monkeypatch _listen to a no-op so no real socket opens
        async def _noop():
            while m._running:
                await asyncio.sleep(0.01)
        m._listen = _noop
        m.start()
        assert m._running is True
        await asyncio.sleep(0.02)
        m.stop()
        assert m._running is False
    asyncio.run(run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -k "singleton or start_stop" -q`
Expected: FAIL — `ImportError: cannot import name 'iv_manager'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add methods to DeltaIVManager
    async def _listen(self) -> None:
        while self._running:
            try:
                await self.discover_subscriptions()
                if not self._subs:
                    log.warning("IV stream: no option subscriptions discovered; retrying")
                    await asyncio.sleep(30)
                    continue
                async with websockets.connect(_WS, ping_interval=20) as ws:
                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "payload": {"channels": [{"name": "mark_price", "symbols": self._subs}]},
                    }))
                    log.info("IV stream subscribed to %d expiries", len(self._subs))
                    last_refresh = time.time()
                    while self._running:
                        msg = await asyncio.wait_for(ws.recv(), timeout=60)
                        self._handle_message(json.loads(msg))
                        if time.time() - last_refresh > 3600:
                            new = await self.discover_subscriptions()
                            await ws.send(json.dumps({
                                "type": "subscribe",
                                "payload": {"channels": [{"name": "mark_price", "symbols": new}]},
                            }))
                            last_refresh = time.time()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("Delta IV socket error: %s", e)
                await asyncio.sleep(5)

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._listen())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()


# module singleton — NOT auto-started (started by FastAPI lifespan when STERLING_IV_STREAM=1)
iv_manager = DeltaIVManager()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/delta_iv_socket.py tests/test_delta_iv_socket.py
git commit -m "feat(iv-stream): listener loop + start/stop + non-auto-start singleton"
```

---

### Task 6: Gated startup wiring in FastAPI lifespan

**Files:**
- Modify: `main.py` (inside `async def lifespan`, near the other `asyncio.create_task` background starts ~line 1484)
- Test: `tests/test_delta_iv_socket.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_delta_iv_socket.py
import inspect
import main as main_mod


def test_lifespan_starts_iv_stream_only_when_env_set():
    src = inspect.getsource(main_mod.lifespan)
    assert "STERLING_IV_STREAM" in src
    assert "iv_manager.start()" in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -k lifespan -q`
Expected: FAIL — assertion error (`STERLING_IV_STREAM` not in lifespan source).

- [ ] **Step 3: Write minimal implementation**

Add inside `async def lifespan(app: FastAPI):` in `main.py`, alongside the other
`asyncio.create_task(...)` background-task starts (around line 1484):

```python
    # Real-time Delta options IV stream (Component ① of realtime-iv-stream).
    # Off by default — opt in with STERLING_IV_STREAM=1 so tests/CI/backtests
    # never open a live socket.
    if os.environ.get("STERLING_IV_STREAM") == "1":
        from app.services.delta_iv_socket import iv_manager
        iv_manager.start()
        log.info("Delta real-time IV stream started")
```

Verify `os` is imported at the top of `main.py` (it is used widely; if a linter flags it,
it is already imported). No `import os` change should be needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -q`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_delta_iv_socket.py
git commit -m "feat(iv-stream): gated iv_manager.start() in FastAPI lifespan"
```

---

### Task 7: Live smoke verification (manual, not CI)

**Files:** none (verification only)

- [ ] **Step 1: Run a 20-second live capture against the real socket**

Run from `backend/`:
```bash
.venv/bin/python - <<'PY'
import asyncio, datetime as dt
from app.services.delta_iv_socket import DeltaIVManager

async def main():
    m = DeltaIVManager(today=dt.datetime.utcnow().date())
    subs = await m.discover_subscriptions()
    print(f"discovered {len(subs)} expiry subscriptions, e.g. {subs[:5]}")
    m.start()
    await asyncio.sleep(20)
    m.stop()
    print(f"ticks captured: {len(m.ticks)}")
    for u in {t.underlying for t in m.ticks.values()}:
        spot_guess = sorted(t.strike for t in m.chain(u))[len(m.chain(u))//2]
        print(f"  {u}: chain={len(m.chain(u))} atm_iv@~{spot_guess:.0f} dte7 = {m.atm_iv(u, 7, spot_guess)}")

asyncio.run(main())
PY
```
Expected: non-empty subscription list, hundreds–thousands of ticks, and a plausible
`atm_iv` (~0.3–1.0) per underlying.

- [ ] **Step 2: If the symbol/payload format differs from assumptions, fix the parser**

If `discovered 0 subscriptions` or `ticks captured: 0`, print one raw product and one raw
WS message, compare to `_parse_symbol` / `_handle_message`, and adjust field names. Re-run
Tasks 1–2 tests after any change.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest tests/test_delta_iv_socket.py -q`
Expected: PASS (11 tests).

- [ ] **Step 4: Commit any fixes**

```bash
git add app/services/delta_iv_socket.py tests/test_delta_iv_socket.py
git commit -m "fix(iv-stream): align parser/handler with live Delta payload"
```

---

## Notes for ②③④ (next cycles, not this plan)
- **②** consumes `iv_manager.ticks` / `chain()` → downsample → new `option_iv_ticks` table.
- **④** uses `chain()` (or REST `get_option_chain`) once → fit surface → re-run `deriv_fut_opt_metrics.py`.
- **③** `strike_picker`/`selector` call `iv_manager.atm_iv` / `chain`, gated on `is_fresh`.
