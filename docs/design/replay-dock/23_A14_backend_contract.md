# A14 — Backend contract

**Files:**
`backend/app/api/v1/endpoints/simulation.py` (109 lines)
`backend/app/services/simulation.py` (1261 lines)
**Fixes:** D1 (friction is fictional), D2 (contract/spot missing), D5 (polling),
D14 (`/available-dates` unused and partly synthetic), D15 (unsurfaced status)

> **This document is Phase 0 of the migration.** Several frontend artifacts have a
> "Version A / Version B" fork that depends on whether the work here lands. Doing the UI
> first and the backend later produces exactly the class of defect this redesign exists
> to remove.

---

## 1. Streaming — `GET /simulation/stream`

### 1.1 Why

The frontend polls `GET /status` every 150 ms and receives the **entire**
`stats.events` and `stats.trades` arrays each time (D5). A 400-signal session re-sends
400 objects 6.7 times a second, and every response replaces the whole client store.

### 1.2 Endpoint

```python
@router.get("/stream")
async def stream_sim(request: Request):
    async def gen():
        async for evt in simulation_runner.subscribe():
            if await request.is_disconnected():
                break
            yield f"event: {evt.kind}\ndata: {evt.json()}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

Four event kinds:

| `event:` | Payload | Cadence |
|---|---|---|
| `state` | `{state, status_message, config}` | on every transition |
| `frame` | `{t, pct, bars_played, bars_total, elapsed_real_s, pnl, wins, losses, signals_fired, trades_open}` | throttled to **max 10 Hz**, and to **max 2 Hz when `speed >= 100`** |
| `signal` | one `SimSignalEvent` | once per signal |
| `trade` | one `SimTradeEvent` (open **and** on close, keyed by `trade_id`) | once per event |

`SimulationRunner` gains an `asyncio.Queue` fan-out with a bounded size (say 512) that
**drops `frame` events under back-pressure but never drops `signal`/`trade`/`state`**.
A dropped frame costs a progress tick; a dropped signal corrupts the ledger.

### 1.3 Delta polling — the fallback path

Keep `GET /status` and add two query parameters so the fallback poller is not O(session)
either:

```
GET /simulation/status?since_events=120&since_trades=8
→ stats.events / stats.trades contain only items at index >= the given offsets,
  plus `events_total` / `trades_total` so the client can detect a reset.
```

Omitting the parameters returns today's full payload, so nothing existing breaks.

### 1.4 Do not remove the poller path

Reverse proxies in front of this app may buffer SSE. The client must keep the fallback,
and the backend must keep `/status` correct. Both paths are supported indefinitely.

---

## 2. Execution friction — implement or remove (D1)

`SimConfig.friction_mode` is declared at `simulation.py:37` and read **nowhere**. The
frontend ships a config section describing spread percentages, a KPI card, a table
column and two sub-line readouts against it. All of it is inert.

### 2.1 Option A — implement (preferred)

Add to `SimConfig`:

```python
friction_mode: str = "realistic"          # "realistic" | "ideal"
index_spread_pct: float = 0.50
stock_spread_pct: float = 1.50
slippage_pct: float = 0.25
```

Add to `SimTradeEvent`:

```python
raw_entry: Optional[float] = None         # theoretical signal price
raw_exit:  Optional[float] = None
slippage:  Optional[float] = None         # total INR drag on this trade
```

Add to `SimStats`:

```python
slippage_total: Optional[float] = None    # None when friction_mode == "ideal"
```

Model, at the point where the runner opens and closes a position
(`simulation.py:~1054–1086`):

- **Entry (buy):** fill at `raw_entry * (1 + half_spread + slippage_pct/100)`.
- **Exit (sell):** fill at `raw_exit * (1 - half_spread - slippage_pct/100)`.
- `half_spread = (index_spread_pct if underlying is an index else stock_spread_pct) / 200`.
- `slippage = (fill_entry - raw_entry) * qty + (raw_exit - fill_exit) * qty`, always ≥ 0.
- `pnl_usd` is computed from the **fills**, not the raw prices.
- `friction_mode == "ideal"` → `raw_* == fill_*`, `slippage = 0.0`, and
  `slippage_total = None` (not `0.0`) so the UI can distinguish "modelled as zero" from
  "not modelled".

**Echo the applied values back** in `SimStatus.config` so the config sheet can verify
what the engine actually used (A09 §2.4). An echo that differs from the request is the
check that catches the next silently-ignored field.

### 2.2 Option B — remove

Delete `friction_mode` from `SimConfig`. Then the frontend must delete: the execution
section, the `SLIPPAGE DRAG` metric, the trades `Slippage` column, the `raw ₹` sub-lines,
the `slippage`/`raw_entry`/`raw_exit` TS fields, and `frictionMode` from the store.

Either is acceptable. **Leaving it as-is is not**, because a user reading `₹0.00` of
slippage concludes their strategy has no execution cost.

Record the choice in the PR description.

---

## 3. Contract and spot on signals (D2)

The frontend's `SimSignalEvent` declares `contract?: string; spot?: number` and renders
a contract name with a `Spot ₹…` badge. The backend model
(`simulation.py:40–49`) has neither field and the construction site
(`:983–993`) sets neither, so `response_model=SimStatus` strips them and the branch is
permanently dead.

The runner already selects an option contract for the trade it opens (it produces
`symbol`, `strike`, `opt_type` on `SimTradeEvent`). Surface the same selection on the
signal:

```python
class SimSignalEvent(BaseModel):
    ...
    contract: Optional[str] = None      # e.g. "NIFTY26SEP24500CE"
    spot: Optional[float] = None        # underlying price at signal time
    strike: Optional[float] = None
    opt_type: Optional[str] = None      # "CE" | "PE"
```

Populate them where the contract is chosen. Where no contract applies (a pure spot
signal), leave them `None` and let the UI fall back to `instrument` — which is the
branch it already has.

If this is not implemented, A07 §2 requires **deleting** the branch, not keeping it.

---

## 4. Absolute seek (D-timeline)

`POST /seek` currently accepts `bars_offset` (relative) and `action` in
`{"jump_start", "jump_end", "step"}`. Timeline scrubbing (A04 §4) needs an absolute
target so a drag commits as one request:

```python
class SeekBody(BaseModel):
    bars_offset: Optional[int] = None
    bar_index:   Optional[int] = None       # NEW — absolute
    to_pct:      Optional[float] = None     # NEW — 0..100
    to_time:     Optional[str]   = None     # NEW — "HH:MM:SS" IST
    action:      Optional[str]   = None
```

Precedence: `action` → `bar_index` → `to_pct` → `to_time` → `bars_offset`. Clamp to
`[0, bars_total-1]` and return the resulting `SimStatus` as today.

Until this lands, the client converts a scrub target to a relative offset from
`bars_played`. That is exact, so this endpoint change is an ergonomics improvement, not
a blocker.

---

## 5. `/available-dates` — make it honest (D14)

The endpoint (`simulation.py:73–108`) reads the OHLCV store and, **if it finds nothing,
invents 90 business days**. The frontend does not call it at all today. Before wiring it
up (A05 §1.4) it must say which case it is in:

```python
class AvailableDatesResponse(BaseModel):
    dates: List[str]
    instrument: str
    resolution: str
    source: Literal["store", "fallback"]     # NEW
    earliest: Optional[str] = None           # NEW
    latest: Optional[str] = None             # NEW
```

The UI copy branches on `source`:
- `store` → *"No stored candles for this date."*
- `fallback` → *"Candle store is empty; dates are unverified."*

Also: the current implementation iterates day-by-day between `earliest` and `latest`
skipping weekends but **not NSE holidays**, while the frontend's preset logic does check
holidays (`isNseClosed`). Two different definitions of "trading day" in one feature will
eventually disagree. Either pass the dates through the same holiday calendar, or state in
the response that holidays are not filtered.

---

## 6. Capability advertisement

Add to `SimStatus`:

```python
class SimCapabilities(BaseModel):
    friction: bool = False
    contract_on_signal: bool = False
    absolute_seek: bool = False
    stream: bool = False
    delta_status: bool = False
    resolutions: List[str] = ["5m"]

class SimStatus(BaseModel):
    ...
    capabilities: SimCapabilities = SimCapabilities()
```

The frontend renders optional columns, sections and controls off `capabilities` rather
than off the presence of a value in one sample row. This is the structural fix for the
whole D1/D2 class: **the UI asks what the backend can do instead of assuming.**

---

## 7. Smaller corrections

| # | Item | Change |
|---|---|---|
| B1 | `pause`/`resume` raise `HTTPException(400)` on a wrong state (`endpoints:32–43`) | Keep, but return a machine-readable `{"code": "not_running"}` detail so the client can pick copy instead of showing a raw string. |
| B2 | `/start` on an already-running sim | Currently the client blind-retries after `/stop` (D18). Make `/start` idempotent-ish: if running, return `409` with `{"code": "already_running"}` so the client can offer *"A replay is already running — restart it?"* |
| B3 | `status_message` | Ensure it is populated for the empty-session case (`no candles for {date}`) — that is the message A02 §4 surfaces. |
| B4 | `speed` | `SimConfig.speed` is `float` but the UI's ladder is integers. Accept any float; the client snaps its own display. Do not reject `250`. |
| B5 | Multi-day ranges | `SimConfig.end_date` exists. Confirm whether the runner honours it; if it does, `current_time_iso` must include the date, or the timeline (A04 §3) cannot place bars. If it does not, reject `end_date != date` with a clear error rather than silently replaying one day. |
| B6 | `elapsed_real_s` | Already populated; no change. Just noting it is now consumed (A02, A06, A10). |

---

## 8. Acceptance criteria

- [ ] `GET /simulation/stream` emits the four event kinds; `frame` is throttled per §1.2.
- [ ] `signal` / `trade` / `state` are never dropped under back-pressure; `frame` may be.
- [ ] `GET /status?since_events&since_trades` returns deltas plus totals; omitting them
      returns the full payload unchanged.
- [ ] Friction: either implemented per §2.1 with `slippage_total = None` in ideal mode,
      or removed per §2.2. `grep -rn "friction_mode" backend/` proves which.
- [ ] `SimSignalEvent` carries `contract`/`spot`, or the frontend branch is deleted.
- [ ] `POST /seek` accepts `bar_index` / `to_pct` / `to_time` and clamps.
- [ ] `/available-dates` reports `source` and its holiday-filtering behaviour is stated.
- [ ] `SimStatus.capabilities` is present and accurate.
- [ ] `end_date != date` either works end-to-end or is rejected with a clear error.

## 9. Tests

`backend/tests/api/test_simulation.py` additions:

1. `/stream` yields `state` then `frame`s; disconnect terminates the generator
2. frame throttle: at `speed=1000`, ≤ 2 frames/s
3. back-pressure: with a full queue, a `signal` still arrives; a `frame` may not
4. `/status?since_events=N` returns only newer events and correct `events_total`
5. friction ON: `fill_entry > raw_entry`, `fill_exit < raw_exit`, `slippage > 0`,
   `pnl` computed from fills
6. friction ideal: `slippage_total is None` (**not** `0.0`)
7. signal carries `contract` and `spot` when a contract was selected
8. `/seek {to_pct: 50}` lands within one bar of the midpoint; `{to_pct: 999}` clamps
9. `/available-dates` with an empty store reports `source == "fallback"`
10. `/start` while running returns `409` with `code == "already_running"`
11. `capabilities` reflects the flags actually compiled in
