# Adaptive Edge — production readiness

**Assessed 2026-08-27, against a live Kite session (token valid to 06:00 IST 2026-08-28).**

**Verdict: the engine is production-ready as software. The strategy is not
production-ready as a trade.** Those are different claims and the difference is
the whole of this document.

---

## What changed today

A live session exposed four bugs that ~4,600 unit tests and every mock had
missed. All four failed *silently* — the scan reported a plausible-sounding skip
rather than an error, so the engine looked like it was running while it made no
decision at all. This is the failure mode this codebase keeps rediscovering.

| # | Bug | Reported as | Reality |
|---|-----|-------------|---------|
| 1 | `fetch_bars` read `payload["data"]["candles"]` | *"only 0 bars of history"* | Kite returns `candles` at the **top level**. Zero bars on every call, all day. |
| 2 | Spot key built by string formatting | *"spot unavailable"* | BANKNIFTY options track an index named **`NIFTY BANK`**. `NSE:BANKNIFTY` does not resolve. |
| 3 | Direction filter ran **before** quoting | *"no contract passed the liquidity filters"* | The IV reading prices an ATM **straddle** — it needs the CE *and* PE. One leg was always missing, so the reading returned `None` on every scan. |
| 4 | Filter compared against `call`/`put` | *"no PE passed the liquidity filters"* | `tradeable_contracts()` normalises to `CE`/`PE`. Every contract was discarded *after* passing every check. |

Each is now pinned by a guard test, and each test was mutation-checked: the bug
was re-introduced and the test confirmed red before the fix was restored.

A fifth issue was structural rather than a bug — see *The gate cannot fill*.

## What now works, verified on live data

```
underlyings 1 · chains_read 1 · listed 25 · tradeable 11
candidates 11 · signals 11 · volatility_recorded 1
```

Instrument dump → chain → spot → expiry/strike windows → quotes → liquidity
filters → strategy decision → ranking → candidates → signals → evidence store.
No skips, no errors. A real implied-versus-realised reading was measured and
persisted.

Backend suite: **4603 passed, 0 failed**.

---

## What blocks production

### 1. The only validated signal is magnitude, not direction

The volatility forecast is genuinely validated — 119/120 instruments, OOS rank
correlation +0.2906. It predicts *how far* price moves.

The 11 signals a scan emits come from the **directional** decision path, and
direction was tested repeatedly across every horizon with realistic fills and
**has no edge**. The engine will happily produce eleven confident-looking
signals per scan built on the half of the model that does not work.

### 2. The gate cannot fill — the horizon and the expiry do not match

The evidence gate demands **400 observations across 20 sessions** before it
arms. An observation needs a *priced structure*, and `from_quotes()` correctly
refuses to price premium collection it cannot hold to settlement:

> contract has 1875 minutes left but the hold is 15 bars

With a 0–7 DTE window and a 30-bar hold, that condition is satisfiable only in
the **final ~31 minutes before expiry** — roughly 31 minutes *per week*. The
20-session requirement means 20 distinct expiry days.

**The gate is ~5 months from opening.** The refusal is correct; the mismatch it
exposes is real. Short-vol harvesting and a minutes-long horizon are not the
same strategy, and one of the two has to give before this trades.

The measurement archive now fills every scan regardless (fixed today), so the
IV/RV premise is at least being *observed* while this is resolved. First live
reading: ratio **0.80** — below parity, against the 1.912 historical median.
That is a post-close artifact on stale quotes and must be re-measured during
market hours before it means anything.

### 3. Nothing has been tested during market hours

Every run in this assessment was at ~16:45 IST, after close, on settlement
quotes. Spreads, depth, and the IV/RV ratio are all materially different intraday.

### 4. No order has ever been placed

`arm()` → broker is written and unit-tested. It has never been exercised against
the live broker — not once, not on paper.

### 5. The configured account is LIVE

`is_paper=False`. Before anything runs unattended this must be flipped to paper.

---

## What would have to be true to go live

1. Flip the account to paper.
2. Run a full session during market hours; confirm the scan stays clean and the
   measurement archive fills.
3. Re-measure the IV/RV ratio on live intraday quotes — the 1.912 premise either
   survives or the strategy does not.
4. Resolve the horizon/expiry mismatch (§2). Either hold to expiry, or stop
   describing the trade as premium collection.
5. Either validate direction or remove the directional path and trade the
   magnitude signal alone.
6. Place one paper order end to end and reconcile it.
7. Let the gate reach its own threshold on real readings.

Until at minimum 1–4 are done, this runs in **observation mode only**.
