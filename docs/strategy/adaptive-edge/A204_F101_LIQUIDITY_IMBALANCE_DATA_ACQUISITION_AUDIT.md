# A204: F-101 LiquidityImbalance Data Acquisition Audit

---

> [!WARNING]
> **AUDIT STATUS: DATA ACQUISITION AUDIT ONLY**
> - **Formula ID**: `F-101` (`Feature normalization / feature score`)
> - **Formula Registry Status**: `LOCKED` (`FormulaStatus.LOCKED`)
> - **Execution Gate**: `BLOCKED`
> - **Implementation Status**: **NOT AUTHORIZED**
> - **A196 Strategy Decision Matrix**: subset later superseded by **A206 C-DV** (DV removed). LI retained. **UNCHANGED** as this LI audit.
> - **A201 DeltaVelocity Audit**: **PARKED** (`DeltaVelocity` = `UNAVAILABLE FROM TRUEDATA`)
> - **A202 Remaining Feature Audit**: **UNCHANGED**
> - **A203 VolatilityRatio Audit**: **UNCHANGED**
> - **Final Verdict**: **`BLOCKED`**
> - **Purpose**: Governance and canonical-contract audit of LiquidityImbalance historical acquisition. Does **NOT** authorize F-101 implementation, calibration, hyperparameter selection, parameter freeze, or execution.

Provider documentation source of truth: `truedata-docs/`  
(primary: `TrueData Market Data API Documentation v 2.6.pdf` / extract `v2.6.txt`).

---

## 1. Executive Verdict

```text
Final Verdict:               BLOCKED
Entitled-window acquisition: IMPLEMENTED (NIFTY-I, ~7 trading days)
A197-scale LI history:       UNAVAILABLE on this TrueData entitlement
F-101 / ExecutionGate:       LOCKED / BLOCKED
A196 / A201 / A202 / A203:   UNCHANGED
Calibration:                 NOT STARTED
```

This audit **did** demonstrate live `GET /getticks?bidask=1` and `GET /getlastnticks?bidask=1` against the active SQLite credential (`TD-6037DD0DD3`, hint `Tr****96`) in `backend/sterling_paper.db`.

This audit **did not** obtain a 6-month tick dataset. On this entitlement, that dataset is **not available** from the documented REST tick history interface.

Do not treat the earlier A204 draft verdict `READY FOR DATA ACQUISITION` as current. That draft used undocumented date formats, the wrong rate-limit figure, an IST→UTC claim the adapter does not implement, and no live tick evidence.

---

## 2. Classification Key

| Label | Meaning |
|---|---|
| `[CANONICAL]` | Strategy specification |
| `[DOCUMENTED]` | Stated in `truedata-docs/` |
| `[VERIFIED]` | Observed in a read-only live probe on 2026-08-14 |
| `[IMPLEMENTED]` | Present in Sterling client/adapter |
| `[PROPOSED]` | Design, not authorized |
| `[UNFROZEN]` | Not yet decided |
| `[NOT VERIFIED]` | Not demonstrated |
| `[BLOCKED]` | Machine or governance block |

---

## 3. Canonical Formula

`[CANONICAL]` `adaptive-edge/Exact Mathematical Operator Specification.md` §5 and `Adaptive Order-Flow Options Scalping and Intraday Strategy.md`:

\[
LQ_t = Q^B_t + Q^A_t
\]

If \(LQ_t > 0\):

\[
LI_t = \frac{Q^B_t - Q^A_t}{LQ_t} = \frac{\mathrm{bidqty}_t - \mathrm{askqty}_t}{\mathrm{bidqty}_t + \mathrm{askqty}_t} \in [-1, +1]
\]

The specification **does not define** \(LI_t\) when \(LQ_t = 0\).  
A202’s “default to 0.0” is **not** restated here as canonical. That case is `[UNFROZEN]`.

\(LI_t\) is a snapshot-level state variable at decision time \(t_k\), not a directional trading rule.

---

## 4. Documented TrueData Tick Contract

Source: `truedata-docs/v2.6.txt` “Tick Data History” (PDF v2.6).

| Item | Documented value |
|---|---|
| URL | `https://history.truedata.in/getticks` |
| Method | GET |
| Auth | `Authorization: bearer <token>` after `POST https://auth.truedata.in/token` |
| `grant_type` | literal `passoword` |
| `symbol` | e.g. `NIFTY-I`, `RELIANCE` |
| `bidask` | `0` or `1`; `1` requests bid/ask fields |
| `from` / `to` | **`yymmddTHH:mm:ss`** |
| `response` | `csv` (recommended) or `json` |
| CSV columns when `bidask=1` | `timestamp,ltp,volume,oi,bid,bidqty,ask,askqty` |
| Sample timestamp | `2021-02-24T09:15:00` (no timezone) |
| Empty-range message | `No Data exists for <Symbol>` |
| Last-N ticks | `/getlastnticks` `nticks=1..200` `interval=tick` `bidask` allowed |
| Last-N note | “bid, bid_qty, ask, ask_qty only comes if requested & enabled” |

### 4.1 Documented rate-limit conflict

`[DOCUMENTED]` two statements exist in the same v2.6 package:

1. Historical REST overview: tick history **5 / second, 300 / minute, 18000 / hour**; bar history **10 / second**.
2. Per-endpoint error text for `/getticks`, `/getbars`, `/getlastnbars`, `/getlastnticks`: **“maximum admitted 1 per Second.”**

`[IMPLEMENTED]` `TrueDataHistoricalClient` uses the overview numbers (`TICK_PER_SECOND = 5`, `BAR_PER_SECOND = 10`).

`[VERIFIED]` a burst of 6 `/getlastnticks` calls in ≈0.5 s all succeeded. The live 1/s error was **not** observed on this account for that endpoint. Treat the live ceiling as **at least 5/s for last-N ticks**, still `[NOT VERIFIED]` for sustained `/getticks` at calibration volume.

### 4.2 Request format that actually works

`[VERIFIED]` `from=260813T09:15:00&to=260813T09:16:00` returns ticks.

`[VERIFIED]` `from=2026-08-13 09:15:00` (draft A204 format) returned **empty** (`n=0`), not an HTTP error.

Do not use `YYYY-MM-DD` for `/getticks`.

---

## 5. Sterling Implementation Status

| Component | Path | Status |
|---|---|---|
| Historical client `get_ticks()` | `backend/app/services/market_data/truedata.py` | `[IMPLEMENTED]` passes `bidask`, `from`, `to` through |
| `get_last_ticks()` | same | `[IMPLEMENTED]` `/getlastnticks` |
| Tick → event | `TrueDataMarketDataAdapter.create_tick_event()` | `[IMPLEMENTED]` |
| Credential store | `truedata_credentials` in SQLite | `[IMPLEMENTED]` |
| **Active credential DB** | `backend/sterling_paper.db` | `[VERIFIED]` account `TD-6037DD0DD3` |
| Repo-root `sterling_paper.db` | empty `truedata_credentials` | do not use for probes |
| Tick cache / warehouse | none | **NOT IMPLEMENTED** |
| F-101 LI feature | none | `[LOCKED]` |

### 5.1 Adapter gaps that affect LI replay

`[IMPLEMENTED]` / `[NOT VERIFIED]` as correct:

1. **Timezone.** `format_iso_timestamp()` tags naive provider strings as **UTC** (`+00:00`). v2.6 does not state a timezone. Sample session times (`09:15`) match NSE IST. Live last ticks at `2026-08-14T14:32:14` occurred during the IST cash session. Treating them as UTC would shift decision time by +5:30. **Timezone is unresolved; do not assume UTC.**
2. **`record_id` collisions.** Hash is `symbol + event_time + str(sequence)`. If `sequence` is omitted, same-second ticks collapse. Live `NIFTY 50` 1-minute window: 268 ticks / 61 unique timestamps. `CanonicalEventSequence` would drop extras. LI snapshot at \(t_k\) must define a last-tick rule **and** a unique record identity before replay can be bitwise.
3. **Empty CSV.** `_raise_history_error` only raises `TrueDataNoDataError` when the body starts with `No Data exists for`. Empty CSV (`n=0`) is returned as `[]` and is indistinguishable from “not entitled / out of retention” without another signal.

---

## 6. Live Probe Evidence (2026-08-14)

Read-only. No secrets logged. Credential: SQLite `TD-6037DD0DD3` / hint `Tr****96`. Auth against `https://auth.truedata.in/token`: **SUCCESS**.

### 6.1 `/getlastnticks?bidask=1` (`nticks=5`)

| Symbol | n | Keys include bidqty/askqty | Sample LQ |
|---|---|---|---|
| `NIFTY 50` | 5 `[VERIFIED]` | yes | `bidqty=0`, `askqty=0` |
| `NIFTY-I` | 5 `[VERIFIED]` | yes | `bidqty=2600`, `askqty=195` |

### 6.2 `/getticks?bidask=1` one-minute windows

| Symbol | Window | n | unique timestamps | `LQ=0` |
|---|---|---|---|---|
| `NIFTY 50` | 2026-08-13 09:15–09:16 | 268 | 61 | **268 / 268** |
| `NIFTY 50` | 2026-08-13 11:00–11:01 | 244 | — | **244 / 244** |
| `NIFTY 50` | 2026-08-14 10:00–10:01 | 242 | — | **242 / 242** |
| `NIFTY-I` | 2026-08-13 09:15–09:16 | 40 | 37 | **0 / 40** |
| `NIFTY-I` | 2026-08-13 11:00–11:01 | 13 | — | **0 / 13** |
| `NIFTY-I` | 2026-08-14 10:00–10:01 | 15 | — | **0 / 15** |

15-minute `NIFTY 50`: 3684 ticks in 0.52 s.  
15-minute `NIFTY-I`: 444 ticks in 0.08 s.

### 6.3 Instrument conclusion for LI

`[VERIFIED]` `NIFTY 50` (index) tick records **include** `bidqty`/`askqty` columns but they are **identically zero** at open, midday, and the current session. \(LQ_t=0\) always ⇒ \(LI_t\) is undefined under the canonical formula.

`[VERIFIED]` `NIFTY-I` (current-month futures) carries non-zero top-of-book quantities. This is the only live-verified LI source in this probe.

`[NOT VERIFIED]` option-contract ticks. Guessed symbols (`NIFTY26AUG24500CE`, …) returned empty. `getOptionChain` with `expiry=yyyymmdd` returned `status=Success` and `Records=[]` for 20260821 / 20260827 / 20260828 / 20260924. `get_all_symbols(segment=fo, search=NIFTY)` returned 20 rows, first `NIFTY-I`. Option tick entitlement is unresolved.

### 6.4 Historical tick retention vs bar retention

Weekday `/getticks?bidask=1` on `NIFTY-I` 09:15–09:16:

| Date | Result |
|---|---|
| 2026-08-14 (Fri, today) | ticks present |
| 2026-08-13 (Thu) | ticks present |
| 2026-08-12 (Wed) | ticks present |
| 2026-08-11 (Tue) | ticks present |
| 2026-08-07 (Fri) | ticks present |
| 2026-08-06 (Thu) | ticks present |
| 2026-08-05 (Wed) and earlier weekdays through 2026-06-26 | **empty** |

`[VERIFIED]` usable futures tick history on this account is **2026-08-06 through 2026-08-14** (about **6–7 trading days**).

`[VERIFIED]` 1-minute **bars** for `NIFTY 50` exist at least back to **2025-02-14** (15 bars returned for 09:15–09:30). Bar history satisfies A197 depth. Tick history does not.

Empty `/getticks` responses were `n=0`, not `TrueDataNoDataError`. Retention vs “no trades” vs “wrong symbol” cannot be separated from the body alone.

---

## 7. Calibration-Scale Feasibility

A197 asks for ~120 trading days / ~45,000 1-minute bars **and** derived `LiquidityImbalance` over that window.

| Requirement | Status |
|---|---|
| Documented `/getticks?bidask=1` | `[DOCUMENTED]` + `[VERIFIED]` |
| `bidqty`/`askqty` enabled | `[VERIFIED]` on futures; present-but-zero on index |
| Day-level chunking | `[PROPOSED]` operational pattern; 1-min and 15-min windows succeeded |
| 120-day tick archive on this account | **NO** — ~7 trading days only `[VERIFIED]` |
| Local tick warehouse | **NOT IMPLEMENTED** |
| Volume estimate if 120 days existed | `NIFTY-I` ≈ 15–45 ticks/min × 375 min × 120 d ≈ 0.7–2.0M ticks; `NIFTY 50` ≈ 90k ticks/day but unusable for LI |
| Rate-limit wall-clock if 120 days existed | 120 day-chunks at 1–5 req/s is seconds-to-minutes, **not** the blocker |
| **Actual blocker** | **Provider retention / entitlement**, not client throughput |

**Conclusion:** A197-scale LI calibration **cannot** start from this account’s REST tick history. Acquiring “everything available” yields about one week of `NIFTY-I` snapshots.

---

## 8. Timestamp, Causality, Replay

### 8.1 Tick-to-decision-time

`[CANONICAL]` at decision time \(t_k\), consume only the latest quote with \(t_{\mathrm{quote}} \le t_k\).

`[PROPOSED]` for 1-minute bar close \(t_k\): last `/getticks` record at or before \(t_k\) on the LI instrument (`NIFTY-I`). Time-weighted / volume-weighted bar aggregation of \(LI\) remains `[UNFROZEN]` (same as draft A204 §K).

### 8.2 Timezone

`[IMPLEMENTATION ASSUMPTION]` Naive TrueData timestamps are now interpreted as `Asia/Kolkata` and converted to UTC by `TrueDataMarketDataAdapter.format_iso_timestamp()`.

This is **not** stated in `truedata-docs/` v2.6 (samples are timezone-naive; the word IST does not appear as a timestamp contract). Canonical event contracts require timezone-aware timestamps at the boundary (`A200`), not a specific provider zone.

Empirical support only: session prints `09:15` / `14:43` match NSE hours. **Do not treat IST as a documented provider fact.**

### 8.3 Deterministic replay

Required before any LI series can be a calibration input:

- persist raw ticks with provider timestamp **as received**
- assign a unique `record_id` (include row ordinal within the response, not only timestamp)
- sort `(event_time, record_id)`
- SHA-256 the canonical sequence
- sample last tick \(\le t_k\) only after that identity is stable

A raw `TickStore` now exists (`backend/data/truedata_ticks.sqlite`). It is an **acquisition cache**, not a calibration dataset. See §15.4. It cannot overcome the 7-day retention gap.

---

## 9. Missing Data and Zero Denominator

| Case | Canonical | This audit |
|---|---|---|
| Missing / non-numeric `bidqty` or `askqty` | fail-closed | `[PROPOSED]` `FeatureStatus.MISSING`, `value=None` |
| Negative quantities | not defined | `[PROPOSED]` `MISSING` |
| \(LQ_t = 0\) | **undefined** (`Exact Math Spec` §5; Variable Registry `STATE-008`) | Implementation maps to `FeatureStatus.MISSING`. That is fail-closed, **not** A202’s `0.0`, and is **not** a new numerical definition. A202 remains unchanged and is non-canonical on this point. |
| `NIFTY 50` live | — | `[VERIFIED]` \(LQ_t=0\) on every sampled tick |
| `NIFTY-I` live sampled minutes | — | `[VERIFIED]` \(LQ_t>0\) on every tick |

---

## 10. Persistence Status

`TickStore` is implemented as a local SQLite acquisition cache. Inspected file `backend/data/truedata_ticks.sqlite` (2026-08-14): **41,313** `NIFTY-I` rows, `2026-08-06T09:15:00` … `2026-08-14T14:43:50` (naive provider strings).

It stores raw quote fields + request window. It does **not** store `event_time`, `available_at`, `record_id`, or `CanonicalEventSequence.sequence_hash`. **Not a calibration dataset.**

---

## 11. What A204 Does Not Authorize

- F-101 implementation or unlock
- ExecutionGate change
- Kite integration
- Arbitrary `W_short` / `W_long`
- DeltaVelocity proxies
- Silent rewrite of A196 (LI stays in the proposed subset)
- Treating 7 days of `NIFTY-I` ticks as an A197 calibration dataset
- Treating `NIFTY 50` index ticks as LI

---

## 12. Remaining Blockers After A204

| ID | Blocker | Status |
|---|---|---|
| A204-R1 | Tick retention ~7 trading days vs A197 120 days | `[VERIFIED]` insufficient |
| A204-R2 | `NIFTY 50` index quotes unusable for LI | `[VERIFIED]` |
| A204-R3 | Option tick symbols / entitlement | `[NOT VERIFIED]` |
| A204-R4 | Provider timestamp timezone | `[IMPLEMENTATION ASSUMPTION]` Asia/Kolkata; not documented |
| A204-R5 | Tick `record_id` | Hash includes ordinal; unique if ordinals unique |
| A204-R6 | \(LQ_t=0\) | Canonical **undefined**; code uses `MISSING` (fail-closed) |
| A204-R7 | Tick warehouse | Acquisition cache only; not A197-grade |

None of these unlock F-101.

---

## 13. Next Step

No A205 document is required; this section is the readiness reassessment.

Strategy Lead must choose one of: shorter LI sample than A197, provider tick-history upgrade, or defer LI. **Do not calibrate on 7 days of futures ticks as if it were A197.** Do not rewrite A196.

---

## 14. Safety Declaration

```text
F-101 Status:             LOCKED
Execution Gate:           BLOCKED
A196:                     UNCHANGED
A201:                     PARKED
A202:                     UNCHANGED
A203:                     UNCHANGED
Calibration:              NOT STARTED
Parameter freeze:         NOT CREATED
Live / Kite execution:    DISCONNECTED
Secrets in this file:     NONE
```

- F-101 not implemented. ExecutionGate not opened. Kite disconnected.
- No calibration performed. No `f101_parameters_v1.json`.
- A196 / A201 / A202 / A203 unchanged.

---

## 15. Post-implementation governance audit (2026-08-14)

Audit of the shipped acquisition path. No new implementation in this section.

Inspected: `adapter.py`, `tick_history.py`, `tick_store.py`, `liquidity_imbalance.py`, `replay.py` `CanonicalEventSequence`, `test_tick_history.py` (10 tests), `backend/data/truedata_ticks.sqlite`, `truedata-docs/v2.6.txt`, `Exact Mathematical Operator Specification.md` §5, `Canonical Variable Registry.md` `STATE-008` / `V-MKT-005/006`, `Adaptive Order-Flow Options Scalping and Intraday Strategy.md` §11, `A196`, `A197`, `A200`, `A201`–`A203`, `TRUE DATA SOURCE-CONTRACT RECONCILIATION.md` §45/§52.

### 15.1 Timestamp interpretation

| Claim | Classification |
|---|---|
| Naive provider strings interpreted as `Asia/Kolkata`, then converted to UTC | `[IMPLEMENTATION ASSUMPTION]` |
| TrueData v2.6 documents IST/Kolkata as the timestamp zone | **False.** Samples are naive (`2021-02-24T09:15:00`). No timezone contract. |
| Canonical boundary requires timezone-aware `event_time` / `available_at` | `[CANONICAL]` via `A200` / `event_boundary.py` |
| Empirical NSE-session match (`09:15` open, `14:43` afternoon) | `[VERIFIED]` consistent with the assumption; **not** a provider specification |

**Verdict:** IST is an adapter assumption, not a documented TrueData fact. Canonical contract is only “aware timestamps + `available_at >= event_time`.”

### 15.2 Tick identity

Construction: `TD-TICK-{symbol}-{sha256(symbol\|event_time_utc\|ordinal)[:12]}` with `ordinal = sequence or 0`.

| Property | Result |
|---|---|
| Same-second ticks unique when ordinals differ | `[VERIFIED]` by test + live cache (e.g. 4 rows at `2026-08-14T09:15:00`) |
| Compatible with `CanonicalEventSequence` | Yes: dedupe by `record_id`, sort `(event_time, record_id)`, SHA-256 payload |
| Provider sequence number | **Not used.** Ordinal is local `enumerate()` of the HTTP response / store chunk |
| Re-fetch remapping risk | Same `(symbol, provider_timestamp, row_ordinal)` PK; overlapping re-acquire can REPLACE rows |

### 15.3 Historical acquisition

| Item | Result |
|---|---|
| `GET /getticks?bidask=1` | `[DOCUMENTED]` v2.6 + `[IMPLEMENTED]` |
| `from`/`to` `yymmddTHH:mm:ss` | `[DOCUMENTED]` + `[VERIFIED]` |
| Session chunks 09:15–15:30 IST, weekdays | `[PROPOSED]` operational. v2.6 example uses `09:00` and may span midnight. Not a documented required chunk. |
| Spacing `1 / TICK_PER_SECOND` = **0.2 s (5/s)** | `[IMPLEMENTED]` from REST **overview** (v2.6: 5/s ticks). Same PDF error text says **1/s**. |
| Hidden 1/s violation | 9 live day-chunks succeeded. Burst risk remains if many symbols are requested at 5/s. Not proven safe at scale. |

### 15.4 Local persistence (`backend/data/truedata_ticks.sqlite`)

Inspected: size 6,602,752 bytes; table `truedata_tick_quotes`; PK `(symbol, provider_timestamp, row_ordinal)`; **41,313** `NIFTY-I` rows; zero PK dups; `ZERO_LQ=0`; `NULL_QTY=0`; min `2026-08-06T09:15:00`; max `2026-08-14T14:43:50`.

| Requirement | Present? |
|---|---|
| Raw `provider_timestamp` | Yes (naive) |
| `bidqty` / `askqty` | Yes |
| `source` / `source_version` | Yes (defaults) |
| Request window | `request_from` / `request_to` |
| `event_time` / `available_at` / `record_id` | **No** |
| `CanonicalEventSequence.sequence_hash` | **No** (store hash ≠ sequence hash) |
| Fold / embargo / instrument class | **No** |

`dataset_sha256` hashes JSON of `load()` rows. Suitable as an **acquisition cache**. **Not** an A197 calibration dataset.

### 15.5 Canonical mapping

`ticks_to_canonical_sequence` → `create_tick_event` → `CanonicalEventSequence.from_events`.

- `event_time` = naive stamp interpreted as IST, emitted UTC.
- `available_at` = `receipt_time_iso` or `event_time`; clamped so `available_at >= event_time`.
- Historical replay without receipt therefore sets `available_at == event_time` (zero modeled latency).
- `last_quote_at_or_before` keeps only `event_type==tick` with `available_at <= decision_time`. **No future quote** in that function. `[CANONICAL]` causality; the last-tick tie-break is `[PROPOSED]`.

### 15.6 LiquidityImbalance calculation

Implemented: \((bidqty - askqty) / (bidqty + askqty)\) when depth \(> 0\).

| Behavior | Classification |
|---|---|
| Numerator / denominator | `[CANONICAL]` Exact Math Spec §5; strategy §11; Variable Registry `STATE-008` |
| \(LQ_t=0\) | Canonical = **undefined**. Code = `MISSING` / `None`. Fail-closed mapping. **Not** A202’s `0.0`. A202 unchanged; A202 is wrong vs `STATE-008`. |
| Missing / negative qty | Code = `MISSING`. Canonical silent except formula gated on \(LQ_t>0\). Fail-closed `[PROPOSED]`. |
| Last quote with `available_at <= t_k` | **Implementation / causal sampling choice**, not a frozen operator. |

### 15.7 What LiquidityImbalance is (from artifacts, not from code)

Do not infer from the implementation.

| Source | What it says |
|---|---|
| Exact Math Spec §5 | State variable \(LI_t\) from contemporaneous \(Q^B_t, Q^A_t\) |
| Variable Registry `STATE-008` | `LI = (BidQty-AskQty)/(BidQty+AskQty)`; undefined if denom 0; **FIXED** |
| `V-MKT-005/006` | Quantity at the **canonical bid/ask observation** |
| Strategy §11 | Liquidity **state** to maintain (`BidQty`, `AskQty`, `LiquidityImbalance`) |
| A196 (proposed) | Causal availability = **Quote Event** (not Bar End) |
| A202 (unchanged audit) | “1 valid quote snapshot at decision time \(t\)”; contemporaneous TOB |
| TrueData source-contract | Must distinguish **tick event** vs **1-second snapshot**; `HistoricalTick = LIMITED` |

**Classification:** point-in-time **quote-state** feature, evaluated at a decision time from the then-available bid/ask observation.

It is **not** specified as:

- a bar OHLCV aggregate,
- a time-weighted / volume-weighted 1-minute average,
- or a mandatory every-tick emitted feature series.

Bar-close sampling and last-tick-in-bar rules remain `[UNFROZEN]` except for the causal constraint: no quote with `available_at > t`.

### 15.8 Are 41,313 ticks / 10 calendar days enough?

**No.**

| Contract | Requirement | This cache | Sufficient? |
|---|---|---|---|
| A197 `[PROPOSED]` F-101 dataset | 6 calendar months ≈ **120 trading days** / ~45,000 **1-minute bars**, plus derived \(LI_t\) over that window | ~**7 trading days** of futures ticks (10 calendar days; 9 sessions) | **No** |
| A203 | \(N_{\min}=W_{\text{long}}+1\) **bars** for first VR; windows `[UNFROZEN]` | VR uses `/getbars` (bars exist ≥18 months). A203 is not met *or* blocked by this tick cache. Tick count is irrelevant to A203. | Tick cache does not satisfy or replace A203 |
| F-101 calibration | A197 dataset + A196 subset including LI + walk-forward | LI span too short; DV still parked; no freeze file | **No** |
| Walk-forward | TRAIN → PURGE → VAL → EMBARGO → TEST | 7 sessions cannot host those folds under A197 coverage | **No** |

**Exact missing requirement:** ~**113 additional trading days** of LI-capable quote history (to reach A197’s ~120), on an instrument with non-zero \(LQ_t\) (currently `NIFTY-I`, not `NIFTY 50` index). Also still missing A196’s `DeltaVelocity` (A201 parked).

### 15.9 Required historical depth for F-101 calibration

Governing F-101 contract number (A197, `[PROPOSED DESIGN]`, not a canonical numeric constant in `adaptive-edge/`):

```text
6 calendar months ≈ 120 trading days ≈ 45,000 1-minute bars
+ derived LogReturn, LiquidityImbalance, VolatilityRatio
(+ DeltaVelocity in A196, which is UNAVAILABLE FROM TRUEDATA)
```

A203 adds: first valid VR needs \(W_{\text{long}}+1\) bars; \(W_{\text{long}}\) unfrozen.

### 15.10 Can this implementation acquire that depth?

**No.** Live weekday `/getticks` on `NIFTY-I` is empty before **2026-08-06**. The client can only persist what the provider returns. Day-chunking and 5/s spacing do not extend retention.

### 15.11 The 10 new tests — what they prove / do not prove

File: `backend/tests/services/providers/truedata/test_tick_history.py`

| Test | Proves | Does not prove |
|---|---|---|
| `test_naive_truedata_timestamp_is_asia_kolkata_not_utc` | Adapter maps `09:15:00` naive → `03:45:00+00:00` | That TrueData documents IST |
| `test_explicit_offset_timestamp_is_preserved` | Offset input is accepted (allows **either** keep-offset or UTC) | A single required offset policy |
| `test_same_second_ticks_get_unique_record_ids` | Different `sequence` → different `record_id` | Provider sequence existence; rematch after re-fetch |
| `test_missing_bidask_fields_map_to_none` | Absent keys → `None` | Live missing-field rates |
| `test_compute_li_valid_and_zero_and_missing` | Formula, `LQ=0`→MISSING, null/negative→MISSING | Canonical authorization of MISSING vs undefined |
| `test_last_quote_at_or_before_is_causal` | Quote after \(t_k\) excluded; last eligible used | That last-tick sampling is the canonical LI definition |
| `test_format_history_timestamp_matches_v26` | `yymmddTHH:mm:ss` formatter | Live server rejects other formats (that was a prior live probe, not this test) |
| `test_nse_session_chunks_are_ist_sessions` | Weekday 09:15–15:30 chunker | That TrueData requires those bounds |
| `test_tick_store_round_trip_and_hash` | SQLite upsert/load + stable SHA-256 on 1 row | 41k-row integrity; calibration-dataset completeness |
| `test_acquirer_uses_documented_from_to_and_bidask` | Mocked `/getticks` URL has `bidask=1` and documented `from`/`to`; sequence hash stable; F-101 still LOCKED | Live entitlement; **rate limit** (`min_interval_seconds=0.0`); 120-day depth |

### 15.12 Immutable / do-not-touch check

`git diff` vs HEAD is empty for:

- `formula_registry.py` (F-101 `LOCKED`)
- `execution_gate.py` (`BLOCKED`)
- `A196`, `A201`, `A202`, `A203`

No `f101_parameters_v1.json`. No Kite Adaptive Edge wiring in this change set. `liquidity_imbalance.py` computes the primitive only; it does not register or unlock F-101.

### 15.13 Final state

```text
Verdict:                     BLOCKED
F-101:                       LOCKED
ExecutionGate:               BLOCKED
A196:                        UNCHANGED
A201:                        PARKED
A202:                        UNCHANGED
A203:                        UNCHANGED
Calibration:                 NOT_STARTED
Hyperparameter selection:    NOT_STARTED
Parameter freeze:            NOT_CREATED
Kite:                        DISCONNECTED
Entitled LI tick window:     ~7 trading days (NIFTY-I)
A197 LI depth:               NOT AVAILABLE
```

