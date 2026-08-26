# Adaptive Edge — AI Continuation Handover

**Document type:** continuation / project-state handover (update in place)  
**Repository:** `nageshmadaram/sterling`  
**Working branch (inspected this update):** `fix/kite-settings-review-findings`  
**HEAD at time of this update:** `cb481933` (`Decide the last five audit leads`)  
**Date of this update:** 2026-08-14 (research E2E software complete; A197 still blocked)  

This is the single authoritative handover for a new AI agent continuing Adaptive Edge.  
Do **not** create a second competing handover document.  
Do **not** create A205.

User-facing explanation of analysis, entry, exit, SL, TSL, modes, and example flows:  
`docs/strategy/adaptive-edge/ADAPTIVE_EDGE_USER_GUIDE.md`

This is a continuation task, not a new strategy-design task.

---

# 0. HOW TO READ THIS DOCUMENT

Every material claim is labeled. Do not silently promote a proposal or an implementation choice into a decision.

| Label | Meaning |
|---|---|
| `[CANONICAL]` | Frozen specification / registry / invariant. Do not invent around it. |
| `[VERIFIED]` | Confirmed against repository code, tests, or an inspected live result recorded here. |
| `[IMPLEMENTATION ASSUMPTION]` | Code does this. It is **not** a documented provider fact and **not** a frozen strategy decision. |
| `[PROPOSED]` | Research / design proposal. Not strategy truth. |
| `[LEARNED]` | Parameter that must be estimated from training information only. Not yet estimated. |
| `[HYPERPARAMETER]` | Structural choice that must be selected out-of-sample. Not yet selected. |
| `[UNFROZEN]` | Explicitly not assigned a production value. |
| `[BLOCKED]` | Machine-enforced or governance-blocked. |
| `[PARKED]` | Investigation closed for now. Do not reopen without new evidence. |
| `[NOT VERIFIED]` | Claimed, designed, or implemented, but not demonstrated at the required scope. |

**Hard rule:** the existence of a file or a working implementation does not make its contents canonical.

---

# 1. PROJECT PURPOSE

## 1.1 What Adaptive Edge is

`[CANONICAL]` Adaptive Edge is Sterling’s institutional, causal, artifact-by-artifact options scalping / intraday strategy. Authoritative strategy documents live in `adaptive-edge/`. Implementation lives under `backend/app/engines/adaptive_edge/`.

It is a distinct strategy. It must not inherit SuperTrend, Value Flow Navigator, Sterling crypto-scalper, or other engine semantics.

The current research/engineering slice is **F-101** (`Feature normalization / feature score`): the first strategy-specific formula in the locked F-101..F-114 set.

## 1.2 Current engineering / strategy objective

Build a **deterministic, causal, offline walk-forward calibration and validation pipeline** for F-101 using real historical market data.

After A204:

- F-101 remains `FormulaStatus.LOCKED` in `formula_registry.py`.
- F-101 is also **`[BLOCKED]`** for calibration: this TrueData account cannot supply A197-scale LiquidityImbalance history.
- Execution remains `[BLOCKED]`.
- No calibration has been run.

Strategy Lead decisions received (2026-08-14): **LI = A**, **DV = C-DV**. Recorded in `A206`.

- C-DV is **executed**: DeltaVelocity is removed from the F-101 subset (no proxy).
- LI = A is **authorized**. Provider stated tick-history entitlement is now enabled.
- **Trial E2E is complete** on the entitled window. It is a **TRIAL / RESEARCH HARNESS** only. Trial math / params / 5/15 windows / equal weights are **not canonical**.
- **Research E2E software is complete** (`SOFTWARE_COMPLETE: True`, label `RESEARCH_NOT_LIVE`) on the entitled cache: features → F-101 trial score → recovered opportunity gates → simulated fill → INV-ENTRY-003 one position → A126 14:45 IST opposite-fill flatten → next-day re-entry when flat → F-002/F-003 accounting → daily ledger → quality report → train-only walk-forward rescore + validation report → TEST-window holdout replay with train params → audit ledger. Production `ExecutionGate` stayed `BLOCKED`. F-101..F-114 stayed `LOCKED`.
- **A197 LI retention re-measure (2026-08-14, same account `TD-6037DD0DD3`):** `/getticks?bidask=1` on `NIFTY-I` is still **empty before 2026-08-06**. Controls on 2026-08-13 and 2026-08-06 returned rows. Every requested older window returned `n=0`. See §4.4.

F-101 remains `LOCKED`. A197 calibration remains **BLOCKED**. Research E2E (simulated fill, no Kite) is **`[VERIFIED]` software-complete** on the entitled window and is labeled `RESEARCH_NOT_LIVE`. Live promotion remains **BLOCKED — A197 LI HISTORY UNAVAILABLE**. Do **not** create A205. Do **not** invent ticks. Do **not** treat trial scores or `f101_parameters_trial.json` as a freeze.

## 1.3 TrueData’s role

`[VERIFIED]` TrueData is the current market-data provider for this work.

**Provider documentation source of truth:** `truedata-docs/`  
(absolute path: `/home/nageshmadaram/Sterling/truedata-docs`).

All TrueData interpretation **must start from these files**. Prefer the PDF over text extracts and over client constants when they disagree.

| File | Role |
|---|---|
| `TrueData Market Data API Documentation v 2.6.pdf` | **Primary** historical REST + websocket market-data spec |
| `TrueData TCP API Documentation v 2.3.pdf` | Realtime TCP spec |
| `TrueData - API endpoints list (1).pdf` | Endpoint inventory |
| `v2.6.txt` | Text extract of the v2.6 PDF (convenience; verify against PDF if conflict) |
| `tcp.txt` | Text extract of the TCP PDF |
| `endpoints.txt` | Text extract of the endpoints list |
| `README.txt` | Points to hosted ReadMe: `https://truedataapi.readme.io/reference` |
| `TD Postman Collection/` | Official Postman collections |

Documented surfaces used here:

- OAuth: `https://auth.truedata.in/token` (`grant_type` documented as the literal `passoword`)
- Historical REST: `https://history.truedata.in` (`/getticks`, `/getbars`, `/getlastnbars`, `/getlastnticks`)
- Documented realtime: `wss://push.truedata.in` / TCP `8082` — **not used for F-101 calibration**
- Config also lists `wss://replay.truedata.in` — `[CANONICAL / A201]` this is **not** in the official PDFs. Treat it as a developer placeholder.

`[DOCUMENTED in v2.6]` `/getticks?bidask=1` returns `timestamp,ltp,volume,oi,bid,bidqty,ask,askqty`. Request `from`/`to` use `yymmddTHH:mm:ss`. Sample timestamps have **no timezone**.

`[DOCUMENTED in v2.6]` two conflicting rate statements: REST overview = tick history **5 / second**; per-endpoint error text = **1 / second**.  
`[IMPLEMENTED]` acquirer spaces at `1 / TICK_PER_SECOND` = **0.2 s (5/s)**.  
`[VERIFIED]` nine live day-chunks succeeded. That does **not** prove 5/s is safe at calibration scale.

TrueData does **not** supply aggressor classification. See A201.

## 1.4 Kite’s role

`[CANONICAL]` Kite is the execution broker path.

`[VERIFIED]` Kite is deliberately disconnected from Adaptive Edge execution. `ExecutionGate` is `[BLOCKED]` while any of F-101..F-114 is not `IMPLEMENTED`.

## 1.5 What is deliberately disconnected

- Kite Adaptive Edge live / paper execution
- F-101 runtime evaluation / unlock
- F-102..F-114 runtime evaluation
- Offline calibration execution
- Hyperparameter search
- Parameter freeze file (`config/adaptive_edge/f101_parameters_v1.json` — **not created**)
- Any heuristic replacement for `DeltaVelocity`
- Silent rewrite of A196

---

# 2. ARCHITECTURE

## 2.1 End-to-end pipeline

```text
TrueData credentials (SQLite table truedata_credentials; encrypted at rest)
        |
        v
TrueData historical REST  (/getbars, /getlastnbars, /getticks?bidask=1)
        |
        v
TrueDataHistoricalClient  +  TickHistoryAcquirer (session chunks, 5/s spacing)
        |
        v
TickStore  backend/data/truedata_ticks.sqlite     [acquisition cache only]
        |
        v
TrueDataMarketDataAdapter
        |
        v
CanonicalMarketEvent      (event_time, available_at, payload, provenance)
        |
        v
CanonicalEventSequence    (dedupe record_id; sort (event_time, record_id); SHA-256)
        |
        v
deterministic replay      (sequence identity)
        |
        v
FeatureSnapshot           (causal available_at <= decision_time)
        |
        +-- liquidity_imbalance.py  primitive LI at decision time  [NOT F-101]
        +-- features_f101.py        A206 3-vector builders        [NOT an unlock]
        |
        v
F-101 trial evaluate      [IMPLEMENTED as TRIAL_NOT_A197]
                          registry still LOCKED
                          A197 calibration still BLOCKED
        |
        v
F-102 ... F-114           [LOCKED]
        |
        v
ExecutionGate             [BLOCKED]
        |
        v
Kite execution adapter    [DISCONNECTED]
```

## 2.2 Stage status

| Stage | Status | Evidence |
|---|---|---|
| TrueData credential store | `[VERIFIED]` implemented | `credentials.py`; live account `TD-6037DD0DD3` in `backend/sterling_paper.db` |
| Historical REST client | `[VERIFIED]` implemented | `truedata.py` |
| Tick acquirer | `[VERIFIED]` implemented | `tick_history.py` |
| Tick cache | `[VERIFIED]` acquisition cache only | `tick_store.py`; `backend/data/truedata_ticks.sqlite` |
| Provider adapter | `[VERIFIED]` implemented | `adapter.py` |
| `CanonicalMarketEvent` | `[VERIFIED]` implemented | `event_boundary.py` |
| `CanonicalEventSequence` | `[VERIFIED]` implemented | `replay.py` |
| LI primitive | `[VERIFIED]` implemented; **not** F-101 | `liquidity_imbalance.py` |
| Bar cache | `[VERIFIED]` acquisition cache only | `bar_store.py`; 2,577 `NIFTY-I` 1-min bars, 2026-08-06…14 |
| A206 3-vector builders | `[VERIFIED]` trial path | `features_f101.py` — no `DeltaVelocity` |
| F-101 trial evaluate | `[VERIFIED]` development only | `f101.py` + `trial_dataset.py`; rejects `FROZEN`/`PRODUCTION` |
| Research E2E | `[VERIFIED]` simulated fill; not live | opportunity + recovered entry-gate conjunction; F-102/F-103 remain SPEC_GAP; production gate stays BLOCKED |
| F-101 registry | `[LOCKED]` + A197 calibration `[BLOCKED]` | `formula_registry.py`; A204 |
| F-102..F-114 | `[LOCKED]` | `formula_registry.py` |
| `ExecutionGate` | `[BLOCKED]` | `execution_gate.py` |
| Kite Adaptive Edge execution | DISCONNECTED | gate fail-closed |

---

# 3. CREDENTIAL ARCHITECTURE

`[VERIFIED]`

1. UI: `TrueDataCredentialsPanel.tsx` via `useTrueData.ts`.
2. API under `/api/v1/truedata/credentials` and `/status`, `/bars`.
3. Passwords / session tokens encrypted with Fernet keyed by `STERLING_SECRET_KEY`.
4. Table `truedata_credentials`. **Active probe DB:** `backend/sterling_paper.db`. Repo-root `sterling_paper.db` has an empty table.
5. Responses expose only `username_hint` (e.g. `Tr****96`).
6. `TRUEDATA_USERNAME` / `TRUEDATA_PASSWORD` are fallback/dev only (`TD-ENV`). Not the production mechanism.

Never write secrets into artifacts, logs, tests, or this handover.

---

# 4. TRUEDATA VERIFICATION STATUS

## 4.1 Proven

`[VERIFIED]`

- Real OAuth against `https://auth.truedata.in/token` (`TD-6037DD0DD3`, hint `Tr****96`).
- Read-only `NIFTY 50` 1-minute bars via `/getlastnbars`.
- Live `/getticks?bidask=1` and `/getlastnticks?bidask=1`.
- Live day-chunk acquisition of **41,313** `NIFTY-I` ticks, **2026-08-06 … 2026-08-14**.
- 1-minute **bars** for `NIFTY 50` back to at least **2025-02-14**.
- `NIFTY 50` index tick `bidqty`/`askqty` are **zero** on every sampled window (unusable for LI).
- `NIFTY-I` futures ticks have \(LQ_t>0\) in the acquired cache (41,313 / 41,313).

## 4.2 Not proven / not available

`[NOT VERIFIED]` or unavailable:

- Official TrueData timestamp timezone (IST is an `[IMPLEMENTATION ASSUMPTION]`).
- 5 req/s as a safe `/getticks` ceiling at scale (docs conflict with 1/s error text).
- Multi-month / 120-day tick history (2026-08-14 remasure: empty before **2026-08-06**; §4.4).
- Option-contract tick entitlement.
- Historical WebSocket replay (`wss://replay.truedata.in` not in official PDFs).
- Aggressor / volume-delta fields (A201: unavailable).
- F-101 A197-scale feature derivation / calibration (trial E2E on ~7 days **is** implemented; it is not A197).

## 4.3 Trial E2E on the entitled window

`[VERIFIED]` 2026-08-14, account `TD-6037DD0DD3`, script `run_f101_trial_e2e.py --symbol NIFTY-I --fetch-bars --w-short 5 --w-long 15`:

| Item | Value |
|---|---|
| Tick window | 2026-08-06 09:15 IST … 2026-08-14 14:43 IST |
| Ticks | 41,313 |
| 1-min bars | 2,577 (7 session chunks, 0 empty) |
| Trial params | identity `TRIAL_NOT_A197`; equal weights; placeholder windows 5/15 |
| Valid scores | 2,562 |
| Missing scores | 15 (VR warmup = `W_long`) |
| `f101_parameters_v1.json` | not created |
| F-101 registry | still `LOCKED` |
| ExecutionGate | still `BLOCKED` |

`W_short=5`, `W_long=15` are **`TRIAL_PLACEHOLDER_WINDOWS`**, not an A203 selection.

## 4.4 A197 retention re-measure (STOP)

`[VERIFIED]` 2026-08-14 live `/getticks?bidask=1` on account `TD-6037DD0DD3` (`Tr****96`). Short windows 09:15–09:16 IST except the documented 2022 example (09:00–09:16 IST). HTTP path succeeded (`status=OK`); empty means the provider returned zero records, not an auth failure.

| Probe | Date (IST weekday) | `from` | `to` | `n` | `zero_lq` | Notes |
|---|---|---|---|---|---|---|
| CONTROL_RECENT | 2026-08-13 | `260813T09:15:00` | `260813T09:16:00` | **40** | 0 | API works on entitled window |
| CONTROL_FIRST_NONEMPTY | 2026-08-06 | `260806T09:15:00` | `260806T09:16:00` | **41** | 0 | First observed non-empty day unchanged |
| D_2026_08_05 | 2026-08-05 | `260805T09:15:00` | `260805T09:16:00` | **0** | 0 | Day immediately before entitlement |
| D_2026_07 | 2026-07-15 | `260715T09:15:00` | `260715T09:16:00` | **0** | 0 | |
| D_2026_06 | 2026-06-15 | `260615T09:15:00` | `260615T09:16:00` | **0** | 0 | |
| D_2026_05 | 2026-05-15 | `260515T09:15:00` | `260515T09:16:00` | **0** | 0 | |
| D_2026_04 | 2026-04-15 | `260415T09:15:00` | `260415T09:16:00` | **0** | 0 | |
| D_2026_03 | 2026-03-13 | `260313T09:15:00` | `260313T09:16:00` | **0** | 0 | |
| D_2026_02 | 2026-02-13 | `260213T09:15:00` | `260213T09:16:00` | **0** | 0 | |
| D_2026_01 | 2026-01-15 | `260115T09:15:00` | `260115T09:16:00` | **0** | 0 | |
| D_2025 | 2025-08-14 | `250814T09:15:00` | `250814T09:16:00` | **0** | 0 | |
| DOCUMENTED_EXAMPLE_2022 | 2022-10-14 | `221014T09:00:00` | `221014T09:16:00` | **0** | 0 | Postman / v2.6-style example; not this subscription |

**Verdict:** A197-scale LI history is **not present**. Phases 3–6 were **not started**. Trial window (~7 trading days) is **not** an A197 dataset.

## 4.5 Documentation audit vs live (2026-08-14)

Inspected every file in `truedata-docs/` (PDFs, text extracts, Postman collections, README, company profile). Files that do **not** expose historical bid/ask quantity: Corporate/Fundamental, Mutual Funds, News, Analytics (empty `getTickHistory`), Greeks (`getTickHistorywithGreeks` is option greeks, not LI), TCP realtime, Symbol Master, Company Profile.

What the **v2.6 Market Data PDF** actually documents for LI:

| Item | Documented | Live on `TD-6037DD0DD3` |
|---|---|---|
| Historical ticks | `GET https://history.truedata.in/getticks` | Works on 2026-08-06+ |
| Bid/ask qty | `bidask=1` → `bid,bidqty,ask,askqty` | Works on entitled window |
| `from`/`to` | `yymmddTHH:mm:ss` | Matches |
| Example depth | Product sample `210224` / Postman `221014` | **Not this subscription.** Body: `No data exists for …` |
| Retention period | **Not specified** in v2.6, endpoints list, TCP, or README | Observed: empty before 2026-08-06 |
| `getlastnticks` | Last N ticks only (max 200) | Not an archive |
| `/getbars` | OHLCV+OI only; `getlastnbars` requires `bidask=0` | Cannot supply LI |
| Historical WS | Deprecated 30 Apr 2021 | Not a longer archive |
| `getAllTicks` / `getAllBars` | Endpoints list + Postman **add-on** (`**`) | `Full Segment not subscribed` |
| `comp=false` | Postman only, not v2.6 | Does not unlock old dates |

Additional live variants after the doc read (all old-date `/getticks?bidask=1` unless noted):

| Variant | Result |
|---|---|
| v2.6 sample `NIFTY-I` `210224T09:00:00`–`15:30:00` | `"No data exists for NIFTY-I"` |
| Postman `RELIANCE` `221014T09:00:00`–`18:30:00` `comp=false` | `"No data exists for RELIANCE"` |
| `NIFTY-I` 2026-02-13 full session, `bidask=0` and `1` | no data |
| `NIFTY 50`, `RELIANCE`, `NIFTY-II`, `BANKNIFTY-I` 2026-02-13 | no data |
| Dated `NIFTY26FEBFUT` 2026-02-13 | no data |
| Dated `NIFTY26AUGFUT` 2026-08-06 09:15–09:16 | **n=41** (same entitled window) |
| Dated `NIFTY26AUGFUT` 2026-08-05 | no data |
| JSON 2026-08-05 | `{"status":"No data exists for NIFTY-I","Records":""}` |
| `getAllTicks` `fo`/`eq` | not subscribed / 429 after quota |
| Live futures master `search=NIFTY` | only current Aug/Sep/Oct 2026 contracts |

**Conclusion:** there is no unused documented endpoint on this account that returns A197-scale LI. The blocker is subscription retention, not an implementation misread of v2.6.

Adapter note (not an F-101 math change): live empty-range text is `"No data exists for …"` (lowercase *data*, often quoted). The v2.6 PDF says `No Data exists`. `_raise_history_error` now matches case-insensitively and treats `Full Segment not subscribed` as an error instead of a one-row CSV.

---

# 5. CANONICAL DATA PIPELINE

## 5.1 `CanonicalMarketEvent`

`[CANONICAL]` + `[VERIFIED]` in `event_boundary.py`: timezone-aware `event_time` and `available_at`; `available_at >= event_time`.

## 5.2 Causality

No event with `available_at > t` may enter a decision at `t`.  
`FeatureSnapshot.assert_causal()` enforces `available_at <= decision_time`.  
`last_quote_at_or_before()` keeps only ticks with `available_at <= t_k`.

## 5.3 Ordering, dedupe, hash

`CanonicalEventSequence`: drop duplicate `record_id`; sort `(event_time, record_id)`; SHA-256 over serialized events.

## 5.4 Timestamp interpretation (A204)

Naive TrueData strings are interpreted as **Asia/Kolkata** and converted to UTC.

**Classification: `[IMPLEMENTATION ASSUMPTION]`.**

- Not a TrueData v2.6 timezone contract. Samples are timezone-naive.
- Canonical requirement is only: timezone-aware stamps and `available_at >= event_time` (`A200`).
- NSE-looking times (`09:15`, `14:43`) support the assumption empirically. They do **not** make it canonical.

Where receipt time is unavailable: `available_at == event_time`.

## 5.5 Tick identity (A204)

```text
record_id = TD-TICK-{symbol}-{sha256(symbol|event_time_utc|ordinal)[:12]}
ordinal   = local enumerate()  — NOT a provider sequence number
```

Same-second ticks are unique when ordinals differ. Compatible with `CanonicalEventSequence`.  
Overlapping re-fetches can **REPLACE** rows keyed by `(symbol, provider_timestamp, row_ordinal)`.

## 5.6 `FeatureSnapshot`

Causal container only. `event_to_feature_snapshot()` still copies raw payload keys.  
`liquidity_imbalance.py` computes the **primitive** \(LI_t\) at a supplied decision time. That is **not** an F-101 unlock.

---

# 6. F-101 STATUS

```text
Formula ID:                 F-101
Registry:                   FormulaStatus.LOCKED          [VERIFIED]
Trial evaluate:             IMPLEMENTED (TRIAL_NOT_A197)  [VERIFIED]
A197 calibration readiness: BLOCKED                       [VERIFIED / A204]
ExecutionGate:              ExecutionGateStatus.BLOCKED   [VERIFIED]
Calibration:                NOT_STARTED (A197)
Hyperparameter selection:   NOT_STARTED (A203)
Parameter freeze file:      NOT_CREATED (f101_parameters_v1.json)
Trial param artifact:       TRIAL_NOT_A197 identity       [VERIFIED]
Implementation unlock:      NOT AUTHORIZED
```

## 6.1 Why F-101 is locked and blocked

`[CANONICAL]` A194: no implementation without an authorized mathematical definition **and** a parameter-learning contract.

A204 adds a **data** block: this TrueData account cannot supply A197-scale LI history.

Remaining blockers:

1. No authorized, frozen F-101 operator (A195/A196 are `[PROPOSED]`).
2. Learned parameters (`Med_i`, `Scale_i`, `w`) not estimated (A197).
3. `W_short`, `W_long` `[UNFROZEN]` `[HYPERPARAMETER]` (A203).
4. **Primary:** LI calibration-scale history unavailable (~7 trading days of `NIFTY-I`; empty before 2026-08-06).
5. `DeltaVelocity` `[PARKED]` / UNAVAILABLE FROM TRUEDATA (A201). A196 still lists it.

## 6.2 F-101 dependency graph

```text
A196 proposed x_F101
        |
        +-- LogReturn            READY (1-min bars; formula fixed)
        |
        +-- VolatilityRatio      DATA AVAILABLE (1-min bars ≥18 months)
        |                        W_short / W_long UNFROZEN  [HYPERPARAMETER]
        |
        +-- LiquidityImbalance   FORMULA [CANONICAL]
        |                        ACQUISITION MECHANISM [VERIFIED]
        |                        CALIBRATION-SCALE HISTORY UNAVAILABLE
        |                        => BLOCKED
        |
        +-- DeltaVelocity        REMOVED FROM F-101 SUBSET (A206 C-DV)
                                 Exact Math Spec unchanged; A201 remains PARKED record
                                 no proxy

Authorized subset is the A206 3-vector.
Trial E2E on the entitled window is **implemented**.
F-101 A197 calibration remains BLOCKED: LI A197-scale history still absent.
```

---

# 7. F-101 FEATURE MATRIX

A196 subset is `[PROPOSED]`. Primitive formulas are `[CANONICAL]`.

| Feature | Status after A204 |
|---|---|
| **LogReturn** | **READY** for data. Formula fixed. Stage-1 `Med`/`Scale` `[LEARNED]`, not started. |
| **VolatilityRatio** | **DATA AVAILABLE** (bars). `W_short`/`W_long` `[UNFROZEN]` `[HYPERPARAMETER]`. Requires governed selection (A203). Tick cache cannot replace bars. |
| **LiquidityImbalance** | **FORMULA RESOLVED** `[CANONICAL]`. **ACQUISITION MECHANISM VERIFIED**. **CALIBRATION-SCALE HISTORY UNAVAILABLE**. |
| **DeltaVelocity** | **REMOVED from F-101 subset (A206 C-DV)**. A201 remains the PARKED provider record. No proxy. Canonical \(\delta v_t\) definition unchanged. |

Therefore: **F-101 registry = LOCKED**. **A197 calibration = BLOCKED**. **Trial E2E = implemented** on the entitled window only.

### 7.1 LiquidityImbalance semantics (from artifacts, not from code)

`[CANONICAL]` Exact Math Spec §5; Variable Registry `STATE-008`; `V-MKT-005/006`:

\[
LI_t = \frac{bidqty_t - askqty_t}{bidqty_t + askqty_t}
\quad\text{when } LQ_t = bidqty_t + askqty_t > 0
\]

\(LQ_t = 0\) is **undefined** (`STATE-008`).  
Implementation maps that to `FeatureStatus.MISSING` (fail-closed).  
A202’s `0.0` is a **superseded interpretation**. **Do not edit A202.**

LI is a **point-in-time quote-state** feature at decision time from the available bid/ask observation.

It is **not** specified as a bar aggregate, TWAP, VWAP, or a mandatory every-tick series.

A196 causal availability = **Quote Event**.  
A202: one valid quote snapshot at decision time \(t\).

`"last quote with available_at <= t_k"` is an `[IMPLEMENTATION ASSUMPTION]` / sampling choice. **Not** a frozen canonical operator.

---

# 8. DELTAVELOCITY DECISION

**UNAVAILABLE FROM TRUEDATA.** A201 is `[PARKED]`.

Do not reopen without new official provider evidence.  
Do not propose uptick/downtick, Lee-Ready, midpoint, bid/ask-ratio, or synthetic aggressor classification.

A196 remains **UNCHANGED**.

---

# 9. VOLATILITYRATIO GOVERNANCE (A203)

A203 is **UNCHANGED**.

- \(W_{\text{short}}\), \(W_{\text{long}}\): `[UNFROZEN]` `[HYPERPARAMETER]`
- \(\epsilon = 10^{-6}\): numerical safety invariant, not learned
- Do not assume 5/20, 10/30, 20/60, or A196’s example 15/60
- \(W_{\text{short}} < W_{\text{long}}\); \(W_{\text{short}} \ge 2\); first valid VR needs \(W_{\text{long}}+1\) bars
- Bar data exist (≥18 months). The LI tick cache does **not** replace the bar dataset
- Do not run hyperparameter selection until the LI data decision is made

---

# 10. A204 COMPLETE RESULT

Governing artifact: `docs/strategy/adaptive-edge/A204_F101_LIQUIDITY_IMBALANCE_DATA_ACQUISITION_AUDIT.md`  
**Status: COMPLETE. Verdict: BLOCKED.**

## 10.1 Timestamps

Naive TrueData timestamps → Asia/Kolkata → UTC.  
`[IMPLEMENTATION ASSUMPTION]`. Not a documented TrueData timezone contract.

## 10.2 Tick identity

`sha256(symbol | event_time_utc | ordinal)`. Compatible with `CanonicalEventSequence`. Ordinal is local. Overlapping re-fetch can REPLACE rows.

## 10.3 Historical acquisition

- `/getticks?bidask=1` works `[VERIFIED]`
- `yymmddTHH:mm:ss` `[DOCUMENTED]` + `[VERIFIED]`
- Session chunk 09:15–15:30 weekdays: **operational**, not documented (v2.6 example uses 09:00)
- Rate: 5/s implemented; docs also say 1/s; **not conclusively safe** at scale
- Nine live day-chunks succeeded; does **not** prove 120-day scale-out

## 10.4 Local cache

Path: `backend/data/truedata_ticks.sqlite`

Observed `[VERIFIED]`:

- 41,313 `NIFTY-I` ticks
- 2026-08-06 through 2026-08-14
- ~7 trading days
- zero PK duplicates
- all observed \(LQ > 0\)

Contains raw quotes + request window.  
Does **not** contain `event_time`, `available_at`, `record_id`, or sequence hash.

**Acquisition cache. Not a canonical calibration dataset.**

## 10.5 Mapping

```text
TrueData tick -> CanonicalMarketEvent -> CanonicalEventSequence
```

Implemented. No receipt ⇒ `available_at == event_time`.  
`last_quote_at_or_before` does not use future quotes.

## 10.6 Depth vs A197

| Have | Need (A197 `[PROPOSED]` contract) |
|---|---|
| 41,313 ticks / ~7 trading days | ~120 trading days / ~45,000 1-minute bars **and** LI-capable quotes over that period |

`/getticks` is empty before **2026-08-06**. This implementation cannot acquire the missing depth.

## 10.7 Takeover re-verification (Phase 1, 2026-08-14)

Independent check of whether the LI-depth blocker can be resolved **technically** without a Strategy Lead decision.

| Path | Result | Label |
|---|---|---|
| TrueData `/getbars` as LI source | Feb-2026 `NIFTY-I` bars exist (`n=5`) but keys are `timestamp,open,high,low,close,volume,oi` only. **No `bidqty`/`askqty`.** v2.6 `/getlastnbars` requires `bidask=0`. | `[VERIFIED]` bars cannot supply LI |
| TrueData `/getticks` older than 2026-08-06 | `NIFTY-I`, `BANKNIFTY-I`, `FINNIFTY-I`, `SENSEX-I` on 2026-02-13 09:15–09:16 all `n=0`. Recent `BANKNIFTY-I` 2026-08-13 works (`n=45`, `zero_lq=0`). Retention is account-wide, not NIFTY-I-specific. | `[VERIFIED]` |
| TrueData `/getAllTicks` (Postman add-on `getAllTicksForSecond`) | Live `HTTP 200` body: `Full Segment not subscribed`. | `[VERIFIED]` not entitled |
| TrueData historical WebSocket | Docs mention a history WS idle timeout; they do **not** document a longer tick archive than REST `/getticks`. `wss://replay.truedata.in` is **not** in the official PDFs (A201). | `[DOCUMENTED]` no extra depth |
| Local `truedata_ticks.sqlite` | 41,313 `NIFTY-I` rows, 2026-08-06–2026-08-14 only. Acquisition cache. | `[VERIFIED]` |
| Other local SQLite (`sterling_paper.db`, `backend/sterling_paper.db`) | No tables with `bidqty`/`askqty` except TrueData credentials / unrelated engines. | `[VERIFIED]` |
| `backend/data/ohlcv*` | Crypto OHLCV only. No Indian quote book. | `[VERIFIED]` |
| Kitelake (`SterlingLake/ticks`) | Drive mounted. `ticks/` has **zero** parquet files. Kite historical API has **no** sub-minute archive (`kitelake/README.md`, `kitelake/ticks.py`). | `[VERIFIED]` cannot backfill LI |
| DeltaVelocity | Unchanged A201: unavailable from documented TrueData interfaces. No local aggressor archive found. | `[PARKED]` |

Re-check (this continuation): Postman documents a 2022 `/getticks` example (`221014T09:00:00`–`221014T18:30:00`). Live on this account: that window **`n=0`**, and `250101`–`250102` **`n=0`**. Same day with wider hours (`260806T09:00:00`–`18:30:00`) returns ticks. So multi-year tick history is a **product example**, not this subscription’s retention.

**Conclusion:** every technical path that does not require a new entitlement, a new vendor contract, or an A196 supersession **fails**. The project cannot proceed to dataset construction, VR selection, or F-101 implementation. The acquisition code already pulls the entitled window; more code cannot create history the API returns empty.

A196 still requires \(\mathbf{x}_{F101}=(\mathrm{LogReturn},\mathrm{LiquidityImbalance},\mathrm{DeltaVelocity},\mathrm{VolatilityRatio})\). Even a 120-day LI entitlement would **not** by itself authorize F-101 while `DeltaVelocity` remains unavailable.

---

# 11. A-SERIES ARTIFACT INDEX (A194–A204)

Paths under `docs/strategy/adaptive-edge/`.

| ID | Filename | Purpose | Classification | Status | May modify? |
|---|---|---|---|---|---|
| A194 | `A194_F101_FEATURE_NORMALIZATION_SPECIFICATION_GAP.md` | Spec-gap; no F-101 without authorized math + learning contract | `[CANONICAL]` gap audit | COMPLETE | **NO** |
| A195 | `A195_F101_FEATURE_NORMALIZATION_PROPOSAL.md` | Robust + tanh proposal | `[PROPOSED]` | COMPLETE | **NO** |
| A195 Audit | `A195_F101_PROPOSAL_GOVERNANCE_AUDIT.md` | Canonical vs proposed vs learned vs open | `[GOVERNANCE AUDIT]` | COMPLETE | **NO** |
| A196 | `A196_F101_STRATEGY_DECISION_MATRIX.md` | Feature subset (DV superseded by A206) | `[PROPOSED]` + **A206 C-DV** | COMPLETE / **SUPERSEDED for DV** | **NO** further subset edits |
| A197 | `A197_F101_CALIBRATION_AND_VALIDATION_CONTRACT.md` | Walk-forward / freeze contract. No calibration run. | `[PROPOSED]` contract | COMPLETE | **NO** |
| A198 | `A198_F101_DATA_READINESS_AND_FEATURE_AVAILABILITY_AUDIT.md` | First data audit | `[DATA AUDIT]` | COMPLETE | **NO** |
| A199 | `A199_TRUEDATA_HISTORICAL_ORDER_FLOW_CAPABILITY_AUDIT.md` | LI via ticks; DV then uncertain | `[DATA AUDIT]` | COMPLETE (DV superseded by A201) | **NO** |
| A200 | `A200_TRUEDATA_DELTA_VELOCITY_PROVIDER_CONFIRMATION_SPEC.md` | Provider questions; no proxy | `[DATA AUDIT]` | COMPLETE (closed by A201) | **NO** |
| A201 | `A201_F101_DELTA_VELOCITY_TRUEDATA_RESOLUTION.md` | DV UNAVAILABLE FROM TRUEDATA | `[FINAL DATA AUDIT]` | **PARKED** / **UNCHANGED** | **NO** |
| A202 | `A202_F101_REMAINING_FEATURE_READINESS_AUDIT.md` | LR ready; VR partial; LI partial | `[FEATURE AUDIT]` | COMPLETE / **UNCHANGED** | **NO** (its `LI=0.0` is superseded interpretation; leave the file) |
| A203 | `A203_F101_VOLATILITY_RATIO_PARAMETER_GOVERNANCE.md` | VR windows unfrozen | `[GOVERNANCE AUDIT]` | COMPLETE / **UNCHANGED** | **NO** |
| **A204** | `A204_F101_LIQUIDITY_IMBALANCE_DATA_ACQUISITION_AUDIT.md` | LI acquisition + post-implementation governance | `[DATA AUDIT]` | **COMPLETE / BLOCKED** | **NO** — do not weaken live findings |
| **A206** | `A206_F101_STRATEGY_LEAD_LI_A_AND_CDV_DECISION.md` | Strategy Lead LI=A + C-DV; 3-feature subset | `[STRATEGY DECISION]` | **COMPLETE** | **NO** |

**A205 does not exist and must not be created.**

There is also `A200_CANONICAL_MARKET_EVENT_BOUNDARY.md` (different A200). Canonical specs remain in `adaptive-edge/`.

---

# 12. IMMUTABLE / DO-NOT-TOUCH

Do not modify:

1. Canonical specifications in `adaptive-edge/`
2. **A196** — subset superseded **only** for DV by A206 (C-DV authorized)
3. **A201** — PARKED / UNCHANGED (provider record)
4. **A202** — UNCHANGED
5. **A203** — UNCHANGED
6. `formula_registry.py` (F-101..F-114 stay `LOCKED`)
7. `execution_gate.py` (stays `BLOCKED`)
8. Kite Adaptive Edge execution path
9. Do not create `f101_parameters_v1.json`

`git diff` vs `HEAD` is empty for items 2–7 as of this update.

---

# 13. TEST STATUS

Latest verified result: **108 passed in 3.25s** (2026-08-14, projector flatten + research folds).

### Command

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest --noconftest \
    backend/tests/api/test_truedata_routes.py \
    backend/tests/services/providers/truedata/test_truedata_adapter.py \
    backend/tests/services/providers/truedata/test_truedata_credentials.py \
    backend/tests/services/providers/truedata/test_tick_history.py \
    backend/tests/test_truedata_adapter.py \
    backend/tests/engines/test_adaptive_edge_risk_sizing.py \
    backend/tests/engines/test_adaptive_edge_canonical_replay.py \
    backend/tests/engines/test_adaptive_edge_feature_validation.py \
    backend/tests/engines/test_adaptive_edge_replay.py \
    backend/tests/engines/test_adaptive_edge_execution_gate.py \
    backend/tests/engines/test_adaptive_edge_execution_gateway.py \
    backend/tests/engines/test_adaptive_edge_f101_trial.py \
    backend/tests/engines/test_adaptive_edge_formula_registry.py \
    backend/tests/engines/test_adaptive_edge_research_e2e.py
```

### What the 10 LI tests prove

- IST conversion in the adapter
- Same-second ordinal `record_id`s
- LI formula; missing / zero-quote → `MISSING`
- Causal last-quote selection
- Documented `yymmddTHH:mm:ss`
- Session chunker
- Single-row cache hash
- Mocked `/getticks` URL (`bidask=1`)
- F-101 remains `LOCKED`
- Trial 3-vector assemble + evaluate; production freeze rejected
- Bar cache / `/getbars` acquirer

### What they do not prove

- IST is provider-documented
- Live rate-limit safety
- 120-day historical availability
- Cache suitability as a calibration dataset
- Last-quote selection is canonical

---

# 14. GIT / REPOSITORY STATE

Inspected 2026-08-14. Do not invent hashes.

```text
Branch inspected:  fix/kite-settings-review-findings
HEAD:              cb481933 Decide the last five audit leads
```

### Uncommitted at this update (working tree, Adaptive Edge relevant)

```text
 M .gitignore
 M backend/app/services/providers/truedata/__init__.py
 M backend/app/services/providers/truedata/adapter.py
 M docs/strategy/adaptive-edge/A196..A204 (banners / C-DV notes)
 M docs/strategy/adaptive-edge/ADAPTIVE_EDGE_AI_IMPLEMENTATION_HANDOVER.md
?? backend/app/engines/adaptive_edge/f101.py
?? backend/app/engines/adaptive_edge/features_f101.py
?? backend/app/engines/adaptive_edge/liquidity_imbalance.py
?? backend/app/engines/adaptive_edge/trial_dataset.py
?? backend/app/services/providers/truedata/bar_history.py
?? backend/app/services/providers/truedata/bar_store.py
?? backend/app/services/providers/truedata/tick_history.py
?? backend/app/services/providers/truedata/tick_store.py
?? backend/scripts/acquire_truedata_li_ticks.py
?? backend/scripts/run_f101_trial_e2e.py
?? backend/tests/engines/test_adaptive_edge_f101_trial.py
?? docs/strategy/adaptive-edge/A206_F101_STRATEGY_LEAD_LI_A_AND_CDV_DECISION.md
```

Do not commit `backend/.env` or secrets. Do not treat untracked `truedata-docs/*.txt` as higher authority than the PDFs.

---

# 15. CURRENT BLOCKERS

**Primary:**

`BLOCKED — A197 LI HISTORY UNAVAILABLE`

Live remasure 2026-08-14: `/getticks?bidask=1` `n=0` on every probed date before 2026-08-06. Controls on 2026-08-06 (`n=41`) and 2026-08-13 (`n=40`) still work. Entitlement has **not** changed.

Trial E2E on the entitled window remains a research harness only. C-DV is **done**. Do **not** continue F-101 mathematical development while this blocker remains.

**Secondary:**

| ID | Blocker |
|---|---|
| BLK-DV | Closed for F-101 subset by A206 C-DV. A201 stays PARKED as provider record. |
| BLK-VR | `W_short` / `W_long` still require governed hyperparameter selection (A203) |
| BLK-TZ | TrueData timestamp timezone remains `[IMPLEMENTATION ASSUMPTION]` |
| BLK-RATE | TrueData rate-limit documentation is internally inconsistent (5/s vs 1/s) |
| BLK-CACHE | Tick cache is not a canonical calibration dataset |
| BLK-F101 | Registry `LOCKED`; no authorized F-101 operator |
| BLK-X | `ExecutionGate` `BLOCKED` |
| BLK-KITE | Kite Adaptive Edge path DISCONNECTED |

---

# 16. CURRENT DECISION LOG

1. No arbitrary F-101 formula (A194).
2. No silent promotion of A195/A196 into canonical truth.
3. No arbitrary normalization parameters (`Med`, `Scale`, `w` are `[LEARNED]`).
4. **Do not fabricate DeltaVelocity.**
5. **Do not replace DeltaVelocity with a heuristic proxy.**
6. **Do not assume volatility lookbacks.**
7. **Do not treat implementation assumptions as canonical facts** (including IST and last-quote sampling).
8. **Do not treat the current tick cache as a calibration dataset.**
9. **Do not begin F-101 calibration without the required historical dataset.**
10. **Do not silently modify A196** to remove unavailable features.
11. **Do not unlock F-101.**
12. A202’s `LI=0.0` on \(LQ=0\) is a superseded interpretation; **do not edit A202**.
13. A201 remains `[PARKED]`.
14. A203 remains `[UNFROZEN]` for \(W_{\text{short}}, W_{\text{long}}\).
15. Do not create A205.
16. Strategy Lead **C-DV executed** (A206). Strategy Lead **LI=A authorized**; entitlement **not present** on re-measure.
17. Strategy Lead authorized **trial E2E development** on the entitled window. Trial scores / trial params / 5/15 windows / equal weights are **not** a production freeze and **must not seed** A197.
18. 2026-08-14 remasure (repeat): A197 LI history still unavailable (`260715` and `260801` n=0; `260813` n=167). Research E2E software is complete on the entitled window (`SOFTWARE_COMPLETE`). Do not thin A197, substitute bars for LI, invent quotes, freeze, or unlock F-101.

---

# 17. NEXT ACTION

`[VERIFIED]` **Research E2E software is complete** (`RESEARCH_NOT_LIVE`, `SOFTWARE_COMPLETE: True`, manifest `RESEARCH_E2E_SOFTWARE_COMPLETE`). Cache 2026-08-06..14 `NIFTY-I`: 7 entries / 6 A126 exits / 6 next-day re-entries / 7 daily rows / last qty 1 (14 Aug ends 14:42 IST). Quality: LI valid 1.0, VR missing 15 (warmup), LR missing 1, LI missing 0, mean last-quote lag 3.46s, max 43s, 0 bars outside session, not A197. Trial-score hashes match. Artifact digest `b953702d4b80a8bd2e3845fff47422d14df3922fbc6addc2e06fbf11b9436ac3`. Holdout TEST replay: 3 entries / 2 exits / train-params only / complete. Production gate stayed unauthorized.

**A197 promotion is still blocked.** Live remasure 2026-08-14 on account `TD-6037DD0DD3`: `/getticks?bidask=1` `NIFTY-I` 2026-07-15 and 2026-08-01 both `n=0` (`No data exists`). Control 2026-08-13 `n=167` with `bidqty`/`askqty`. Old-date history is still absent.

Next useful **external** action: enable tick-history retention, remasure `/getticks?bidask=1` on an old date, then run the same pipeline as A197.

Do **not** create A205. Do **not** unlock F-101. Do **not** shrink A197. Do **not** invent a DV proxy. Do **not** write `f101_parameters_v1.json`. Do **not** reuse the trial window as A197.

---

# 18. CONTINUATION INSTRUCTIONS FOR THE NEXT AI

**Do not jump to implementation.**  
**Do not create A205.**

```text
A206 C-DV COMPLETE
TRIAL E2E COMPLETE                 — research harness only; not canonical
RESEARCH E2E SOFTWARE COMPLETE     — RESEARCH_NOT_LIVE; simulated fill
A197 LI REMEASURE 2026-08-14       — n=0 before 2026-08-06  =>  STOP
        |
        v
BLOCKED until live old-date /getticks?bidask=1 returns rows
        |
        v
only then: A197 dataset -> quality audit -> A203 VR -> walk-forward
           -> validation -> freeze -> F-101 unlock
```

Do **not**:

- unlock F-101 or ExecutionGate
- edit `formula_registry.py` statuses
- invent a DeltaVelocity proxy
- hardcode `W_short` / `W_long`
- start A197 calibration on 7 days of `NIFTY-I` ticks
- treat trial scores / `f101_parameters_trial.json` as a freeze
- shrink A197
- create A205
- connect Kite to Adaptive Edge

---

# 19. SECURITY

This handover contains **no** passwords, access tokens, API secrets, session tokens, or private keys.

Username appears only as the redacted hint `Tr****96`.  
`STERLING_SECRET_KEY` is named, not valued.

---

# 20. FINAL STATE SNAPSHOT

```text
F-101:                       LOCKED
F-101_trial_evaluate:        IMPLEMENTED (TRIAL_NOT_A197)
F-101_calibration:           BLOCKED (A197)
ExecutionGate:               BLOCKED
DeltaVelocity:               REMOVED_FROM_F101_SUBSET (C-DV)
A201:                        PARKED
A196:                        SUPERSEDED_FOR_DV_BY_A206
A202:                        HISTORICAL_AUDIT (A206 pointer only)
A203:                        HISTORICAL_AUDIT (A206 pointer only)
A204:                        COMPLETE / BLOCKED
A205:                        NOT_CREATED
A206:                        COMPLETE (LI=A recorded; C-DV executed)
LogReturn:                   READY (trial path)
VolatilityRatio:             DATA_AVAILABLE; W_short/W_long UNFROZEN
                             trial uses TRIAL_PLACEHOLDER_WINDOWS 5/15
LiquidityImbalance:          FORMULA_RESOLVED; ACQUISITION_VERIFIED; A197_SCALE_UNAVAILABLE
LI_TickCache:                41313 NIFTY-I ticks; 2026-08-06..2026-08-14; ACQUISITION_CACHE_ONLY
BarCache:                    2577 NIFTY-I 1-min bars; same window; ACQUISITION_CACHE_ONLY
TrialScores:                 2562 VALID / 15 MISSING (VR warmup); TRIAL_NOT_A197
Calibration:                 NOT_STARTED
HyperparameterSelection:     NOT_STARTED
ParameterFreeze:             NOT_CREATED
f101_parameters_v1.json:     NOT_CREATED
LiveExecution:               DISCONNECTED
Kite:                        DISCONNECTED
Tests:                       790 PASSED (engines + TrueData provider)
ResearchE2E:                 SOFTWARE_COMPLETE (RESEARCH_NOT_LIVE; sim fill)
ResearchE2E_cache:           7 entries / 6 A126 exits / 6 reentries
                             last_qty=1 (2026-08-14 ends 14:42 IST)
Daily_ledger:                7 IST days; last day open
Quality:                     TRIAL_NOT_A197_QUALITY; LI=1.0; VR_missing=15; LR_missing=1
                             quote_lag mean=3.46s max=43s
Holdout_test_replay:         3 entries / 2 exits; TRAIN params only
Artifact_digest:             b953702d4b80a8bd2e3845fff47422d14df3922fbc6addc2e06fbf11b9436ac3
Trial_scores_hash_match:     true
Manifest:                    RESEARCH_E2E_SOFTWARE_COMPLETE
Walk_forward_folds:          RESEARCH_PLACEHOLDER_SPLITS
                             train=909 val=581 test=1077 overlap=false
Walk_forward_eval:           TRIAL_NOT_A197_TRAIN_ONLY; val_valid=581; test_valid=1077
f101_parameters_trial.json:  WRITTEN (train-only; not a freeze)
A197_dataset:                NOT_CREATED
A197_dataset_sha256:         N/A
VR_windows_selected:         NOT_SELECTED (search code only)
Learned_parameters:          NOT_ESTIMATED_FOR_PRODUCTION
Purge_embargo:               CALLER_SUPPLIED (not invented)
Validation:                  NOT_AN_A197_PROMOTION
NextAction:                  LIVE_LATER_ENABLE_TRUEDATA_TICK_HISTORY
ProjectState:                RESEARCH_E2E_SOFTWARE_COMPLETE; A197_STILL_BLOCKED
```

---

# APPENDIX — KEY PATHS

```text
truedata-docs/                                                 TrueData provider PDFs
adaptive-edge/                                                 canonical strategy specifications
docs/strategy/adaptive-edge/A204_...md                         A204 COMPLETE / BLOCKED
docs/strategy/adaptive-edge/ADAPTIVE_EDGE_AI_IMPLEMENTATION_HANDOVER.md
backend/app/engines/adaptive_edge/formula_registry.py         F-101..F-114 LOCKED
backend/app/engines/adaptive_edge/execution_gate.py           BLOCKED
backend/app/engines/adaptive_edge/liquidity_imbalance.py      primitive LI (not F-101)
backend/app/engines/adaptive_edge/features_f101.py            A206 3-vector builders
backend/app/engines/adaptive_edge/f101.py                     trial evaluate (not an unlock)
backend/app/engines/adaptive_edge/trial_dataset.py            bars+ticks → trial scores
backend/app/services/providers/truedata/adapter.py            IST assumption + tick IDs
backend/app/services/providers/truedata/tick_history.py       /getticks acquirer
backend/app/services/providers/truedata/tick_store.py         tick acquisition cache
backend/app/services/providers/truedata/bar_history.py        /getbars acquirer
backend/app/services/providers/truedata/bar_store.py          bar acquisition cache
backend/data/truedata_ticks.sqlite                            41313 NIFTY-I ticks
backend/data/truedata_bars.sqlite                             2577 NIFTY-I 1-min bars
backend/scripts/acquire_truedata_li_ticks.py                  live tick acquire helper
backend/scripts/run_f101_trial_e2e.py                         trial bars+ticks scorer
backend/scripts/run_adaptive_edge_research_e2e.py             research E2E (sim fill)
backend/app/engines/adaptive_edge/research_e2e.py             research path; gate stays BLOCKED
backend/app/engines/adaptive_edge/research_pipeline.py        coverage + train-only WF eval
backend/app/engines/adaptive_edge/research_opportunity.py    recovered 3-gate conjunction
backend/app/engines/adaptive_edge/research_session.py        NSE clock + A126 cutoff
backend/data/adaptive_edge/research_e2e.json                 last SOFTWARE_COMPLETE artifact
docs/strategy/adaptive-edge/ADAPTIVE_EDGE_USER_GUIDE.md      user guide (entry/exit/SL/TSL)
backend/app/engines/adaptive_edge/protection.py             A177 stop/trail/lock machinery
backend/data/adaptive_edge/software_e2e_manifest.json        RESEARCH_E2E_SOFTWARE_COMPLETE
backend/data/adaptive_edge/li_retention_remeasure.json       live old-date /getticks probe
backend/scripts/remeasure_truedata_li_retention.py         read-only retention remasure
backend/data/adaptive_edge/f101_parameters_trial.json        train-only; not v1
backend/sterling_paper.db                                     active TrueData credentials
```
