# Real-Time IV Streaming (Delta Exchange) — Design

_Date: 2026-06-01 · Status: approved (Component ① detailed; ②③④ roadmap) · Branch: `feat/realtime-iv-stream`_

## Goal & context

Bring **real implied-volatility / Greeks** into Sterling from Delta Exchange India's
`mark_price` WebSocket channel (`wss://socket.india.delta.exchange`). Today the
derivatives engine consumes IV only via REST polling (`delta_india.get_option_chain`
→ `OptionSummary.mark_iv`), and the offline options backtest
(`backend/deriv_fut_opt_metrics.py`) has **no real IV at all** — it proxies IV from the
underlying's trailing realized vol.

**Key constraint:** the WS stream is *live-only*. It cannot retro-fill the 2024→2026
history the backtest replays. Real IV therefore reaches the backtest in two ways: a
**current-chain snapshot** (④) applied to historical price paths, and a **forward
recorder** (②) that accrues a true historical IV surface from now on.

The user selected **all four** capabilities. They decompose into one foundation plus
three consumers, to be built in this order:

| # | Component | Depends on | Notes |
|---|-----------|-----------|-------|
| **①** | **IV Stream Manager** (this spec) | — | WS client → latest per-strike IV/Greeks in memory |
| ② | Forward IV recorder | ① | persist per-strike ticks to a new DB table |
| ④ | Snapshot → backtest | ① (or REST) | fit current IV surface, re-run options backtest |
| ③ | Live engine integration | ① | feed fresh IV into `strike_picker`/`selector` |

Channel decision (settled): **`mark_price`** with **Asset-Expiry** subscription
(`BTC-270625`) — one subscription covers all strikes (calls + puts) for that expiry.

---

## Component ① — IV Stream Manager (detailed design)

**File:** `app/services/delta_iv_socket.py` (new), mirroring `delta_l2_socket.py`.

### Data model
```python
@dataclass
class IVTick:
    option_symbol: str   # "C-BTC-105000-270625"
    underlying: str      # "BTC"
    option_type: str     # "call" | "put"
    strike: float
    expiry: str          # "270625" (DDMMYY)
    dte: int
    mark_iv: float; bid_iv: float; ask_iv: float
    mark_price: float; best_bid: float; best_ask: float
    delta: float; gamma: float; theta: float; vega: float; rho: float
    ts_exchange: float   # message `timestamp` (µs → s)
    ts_local: float      # time.time() on receipt (staleness clock)
```

### Read API (the contract ②③④ depend on)
- `get(option_symbol) -> IVTick | None`
- `chain(underlying) -> list[IVTick]` — every live strike/expiry; **this is the full
  per-strike surface** ④ fits from. ① does not fit a surface itself (YAGNI).
- `atm_iv(underlying, dte, spot) -> float | None` — pick expiry nearest `dte`, then
  strike nearest `spot`, return its `mark_iv`. Primary accessor for ③ and ④.
- `is_fresh(underlying, max_age_s=10) -> bool` and `last_update_ts(underlying) -> float`
  — consumers must never trade on a dead socket.

### Data flow
```
/v2/products (REST, delta_india adapter)
   → discover (underlying, expiry, dte) ; keep dte ≤ 45
   → subscription symbols  ["BTC-270625", "ETH-270625", …]   (one per underlying×expiry)
   → WS subscribe  mark_price
   → ticks  "MARK:C-BTC-105000-270625"  → parse → self.ticks[option_symbol] (latest-only)
   → consumers: atm_iv / chain / get / is_fresh
```
Universe = **all listed option underlyings** discovered dynamically (skip any with no
live option products). In-memory **latest-only** (overwrite per symbol): a high tick
rate is cheap because ① stores no history — persistence is ②'s job.

### Mechanics
- `_discover_subscriptions()`: page `/v2/products?contract_types=call_options,put_options&page_size=…`,
  parse each product symbol `{C|P}-{UND}-{STRIKE}-{DDMMYY}`, compute DTE, keep `dte ≤ 45`,
  emit one `{UND}-{DDMMYY}` per (underlying, expiry). Refresh **hourly** and on every
  reconnect (expiries roll daily/weekly).
- `_listen()`: connect → send subscribe payload → `recv` loop; on `type=="mark_price"`
  parse → store latest; reconnect with **5 s backoff** (L2 pattern) and re-subscribe.
- `_handle_message(msg)`: pure function (msg dict → updates `self.ticks`); the unit-test seam.

### Lifecycle (decided)
Module singleton `iv_manager = DeltaIVManager()` that is **import-safe but start-gated**:
`start()`/`stop()` provided, and `start()` is called from FastAPI startup **only when
`STERLING_IV_STREAM=1`**. So `pytest`, CI, the recorder/backtest imports, and the offline
tools never open a socket. (Rejected: L2's import-time auto-start — fragile, opens sockets
in tests; full `app.state` service — ②/④ run outside FastAPI and need a plain importable
singleton.)

### Error handling
- WS drop → backoff + reconnect + re-subscribe (+ re-discover).
- `/v2/products` discovery failure → keep last-known subscription set; log warning.
- Malformed / unparseable message → skip + debug log (never crash the loop).
- Staleness surfaced via `ts_local` / `is_fresh`; ① never silently serves dead IV.

### Testing (all offline — no live socket in CI)
- symbol parser: `MARK:C-BTC-105000-270625` → (call, BTC, 105000.0, "270625").
- `_handle_message` on the sample `mark_price` payload from the docs → expected `IVTick`.
- `atm_iv` selection: injected ticks across 2 expiries × 3 strikes → nearest-expiry +
  nearest-strike pick.
- discovery DTE filter: synthetic product list → only `dte ≤ 45` subscriptions emitted.
- `is_fresh`: stale vs fresh `ts_local`.

### Files touched
- **new** `app/services/delta_iv_socket.py`
- **new** `tests/services/test_delta_iv_socket.py`
- **edit** app startup (FastAPI lifespan) — gated `iv_manager.start()`
- **reuse** `delta_india` adapter REST helpers for `/v2/products` discovery

---

## Roadmap (designed in their own cycles)

- **② Forward IV recorder** — new per-strike table (e.g. `option_iv_ticks(underlying,
  expiry, strike, type, mark_iv, bid_iv, ask_iv, delta, gamma, theta, vega, rho, ts)`);
  the existing `iv_history(underlying, ivr, ts)` is underlying-level IVR only, so keep it
  and *also* feed real ATM-IV/IVR into it. Downsample ticks (2 s → ~1 min / on-change) so
  the 2.7 GB DB doesn't explode.
- **④ Snapshot → backtest** — capture `chain()` once (or REST), fit ATM term-structure +
  skew, re-run `deriv_fut_opt_metrics.py` options leg on real IV instead of realized-vol.
- **③ Live integration** — `strike_picker`/`selector` read `iv_manager.atm_iv/chain`
  (fallback to REST `get_option_chain`); gate trading on `is_fresh`.

## Risks / open items
- Message volume for *all* underlyings × strikes at 2 s could be heavy → ① is latest-only
  (cheap); revisit a per-underlying allowlist if CPU/bandwidth is an issue in ②.
- Delta product-symbol format assumed `{C|P}-{UND}-{STRIKE}-{DDMMYY}`; validated against a
  live `/v2/products` sample during implementation before trusting the parser.
