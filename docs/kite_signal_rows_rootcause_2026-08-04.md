# Kite signal board — root-cause audit of the 5 reported symptoms (04 Aug 2026)

Scope: the five complaints raised against the signal board in `SterlingKiteEnginePane`.
Method: 6-dimension parallel code audit + **live runtime capture** from the running engine
(`GET /api/v1/kite/engine/{signals,config,activity}` at 16:46 IST) + numeric tests of the
indicator layer. Live capture is the primary evidence; every load-bearing claim below was
re-verified by hand against source.

**Live configuration at the time of the screenshots:** `scan_source = "both"`,
`strike_moneyness = [ITM5,ITM4,ITM3,ITM2,ITM1,ATM]`, `candle_basis` not exposed in the API.
The board contained **7 live + 39 ended** signals in one list.

> Confidence labels: **CONFIRMED** = reproduced in the live payload *and* traced in source.
> **CONFIRMED (code)** = traced in source on both sides, not separately reproduced.
> **LATENT** = real defect, but not the cause of these screenshots.

---

# STOP-WORK FINDING — every position opened from this board is unprotected

Found while re-prioritising the display defects by money impact. This outranks all five
reported symptoms. Status: **CONFIRMED (code, three independent facts).**

1. `positions.register` — the function that arms fill-tracking, the broker GTT stop, the tick
   monitor, and ticker auto-subscribe — has **exactly one call site** in the entire backend:
   [service.py:526](backend/app/services/kite_engine/service.py:526), inside
   `_make_place_cb` ([service.py:248](backend/app/services/kite_engine/service.py:248)),
   which is the **auto-exec** callback.
2. `place_manual_order` ([service.py:57-97](backend/app/services/kite_engine/service.py:57))
   performs a live-safety gate and a duplicate check, places the order, and returns. It never
   registers the position, never places a protective GTT, never arms the monitor.
3. `_square_off_expiring` ([service.py:565](backend/app/services/kite_engine/service.py:565))
   iterates `positions.open_positions(uid)` — the registry. Its own docstring says it exits
   "**auto-exec** option positions". Same for `_update_open_position_trails` and the time stop.

Live config: **`auto_execute = false`**. Therefore *every* position currently being opened is
manual, and therefore **no** position currently has: a broker stop, a monitor stop, a
ratcheting trail, a time stop, or an expiry square-off.

Meanwhile the board renders `SL`, `TSL` and `Target` on every leg, and the SL tooltip
describes a live ratchet. The screen implies a managed trade; the backend has no record the
trade exists.

The board's Buy button opens the OrderWindow
([SterlingKiteEnginePane.tsx:1105](frontend/src/components/kite/SterlingKiteEnginePane.tsx:1105))
which submits via the standard `POST /kite/orders` path — so this applies to both manual order
routes, since the single `register` call site excludes both.

## Why the expiry gap is the sharp edge

`vehicle = deep_itm_options` on NSE **stock** options, which are **physically settled** in
India. A deep-ITM long call held through expiry with no square-off becomes a delivery
obligation, not an expired premium. One lot, at the strikes in the live payload:

| underlying | lot | strike | 1-lot deliverable notional |
|---|---|---|---|
| ICICIBANK | 700 | 1440 | ₹10,08,000 |
| BHARTIARTL | 475 | 1960 | ₹9,31,000 |
| ADANIENT | 309 | 3000 | ₹9,27,000 |
| BAJFINANCE | 750 | 1140 | ₹8,55,000 |
| LT | 175 | 4000 | ₹7,00,000 |
| TCS | 225 | 2440 | ₹5,49,000 |
| HDFCBANK | 650 | 740 | ₹4,81,000 |

(NIFTY/SENSEX are cash-settled; the 14 stock names are not.) `expiry_square_off_days = 1` is
configured and would handle this — but only for positions in the registry.

Also off in the live config: `max_daily_loss_pct = null` (no daily-loss breaker),
`risk_sizing = false` (the 1% `risk_pct` is not enforced), `wire_risk_infra = false`.
Those are configuration choices, not defects — flagged for visibility.

## Fix order

- **Now (honest display, ~1 hour, UI only):** stop the board implying protection that is not
  armed. On any row/leg not present in the positions registry, render the SL/TSL/Target cells
  as advisory — e.g. `SL 48.4 (not armed)` — and change the tooltip. This removes the
  misleading part today without touching any order path.
- **Then (real fix, needs tests):** route manual fills into `positions.register` so the
  monitor, trail, time stop and expiry square-off cover them. This arms live stop automation
  on real money, so it needs the `_exit_position` `_exiting`-claim invariant respected and a
  test per path before it goes near production.
- **Independently:** the prior audit's five `[critical]` items
  (`kite_signal_audit_2026-08-04.md:383,406,430,459,487`) are all on the auto-exec path and
  remain **unverified**. They are dormant while `auto_execute = false`, and must be verified
  *before* AUTO is ever switched on — `stop_mode = "both"` in particular is alleged to fire the
  GTT and the monitor at an identical trigger and sell 2× quantity, leaving a naked short.

---

## Complaint 4 first: "why is TCS there twice?"

**Root cause: `scan_source = "both"` runs two independent sweeps and concatenates them.
There is no cross-source merge, and nothing labels which sweep a row came from.**
Status: **CONFIRMED.**

The two TCS cards are one `source="spot"` row and one `source="derivatives"` row:

| src | header ts | adx | atr_pct | stop_loss | entry_sl | spot | underlying_spot |
|---|---|---|---|---|---|---|---|
| derivatives | **03 Aug 15:15** | null | null | 0.0 | null | 0.0 | 2453.4 |
| spot | **03 Aug 14:15** | 29.47 | 67.0 | 2428.92 | 2389.51 | 2453.4 | null |

They are not duplicates — they are two genuinely different signals on the same underlying:

- the **spot** row = triple-SuperTrend fired on TCS's own 1H chart at 14:15; option strikes
  are attached afterwards as candidates.
- the **derivatives** row = SuperTrend fired on each *option contract's own premium* chart;
  the latest of those fired at 15:15.

That is also why the SL/TSL differ for the identical contract — two different stop domains:

| src | TCS26AUG2440CE entry | UI "SL" (`leg.entry_sl`) | UI "TSL" (`leg.premium_sl`) |
|---|---|---|---|
| derivatives | 74.75 | **48.37** | 63.19 |
| spot | 74.75 | **38.29** | 60.78 |

Screenshot S3 shows 48.4/61.6 and 38.3/58.7 — the payload reproduces both exactly.

Evidence: activity log `Scan plan: Scanning 16 instruments using 'both' source.`;
[scanner.py:717](backend/app/services/kite_engine/scanner.py:717) `scan()` runs the spot
branch and the derivatives branch into one `rows` list;
[scanner.py:262](backend/app/services/kite_engine/scanner.py:262) `_compile_rows` groups
**only** `source == "derivatives"` rows (L277 short-circuits everything else), so no
spot↔derivatives reconciliation exists anywhere.

Secondary contributor: the same `(underlying, source)` pair can appear **more than once**
at different bars, because ended signals are retained. In the live payload HDFCBANK has
two `derivatives` rows (04 Aug 13:15 and 03 Aug 09:15) plus a `spot` row — matching S1,
where HDFCBANK appears twice.

---

## Complaint 5: "can't tell spot-based from derivative-based rows"

**Root cause: pure UI gap. `source` is present in the API payload and is simply never
rendered.** Status: **CONFIRMED.**

- The payload carries `source` on every row (`spot` / `derivatives` observed live).
- The board renders a provenance badge for exactly one value:
  [SterlingKiteEnginePane.tsx:634](frontend/src/components/kite/SterlingKiteEnginePane.tsx:634)
  `{row.source === 'navigator' && (…"Navigator idea"…)}`. Nothing for spot/derivatives/confluence.
- The mode selector explicitly promises the missing label:
  [SterlingKiteEnginePane.tsx:86](frontend/src/components/kite/SterlingKiteEnginePane.tsx:86)
  `hint: 'Run both scans; each signal is tagged Spot or DERIV.'` — that tag does not exist.

**The only cue today is accidental.** The `TSL / ADX / ATR%` header chips render on the spot
card and not the derivatives card, because:

- [SterlingKiteEnginePane.tsx:643](frontend/src/components/kite/SterlingKiteEnginePane.tsx:643)
  gates the underlying-TSL chip on `{!isDeriv && …}`, and
- `_compile_rows` blanks the derivatives group parent —
  [scanner.py:296-298](backend/app/services/kite_engine/scanner.py:296) sets
  `parent.spot = 0`, `parent.stop_loss = 0`, `parent.entry_sl = None` — and
  `evaluate_derivative_contract` never populates `adx`/`atr_pct` at all
  ([scanner.py:366-389](backend/app/services/kite_engine/scanner.py:366)).

So "has ADX/ATR chips" == "is a spot row" purely as a side effect. Confirmed live:
derivatives rows have `adx=null, atr_pct=null, stop_loss=0.0, spot=0.0`.

---

## Complaint 1: "entry times mismatch"

**Root cause: the card header renders the *group parent's* timestamp, which is the
`max()` over its legs, while the chart marker renders the *selected leg's own*
timestamp. For a grouped derivatives row those are different bars by construction.**
Status: **CONFIRMED.**

`_compile_rows` groups every option contract of one underlying/type into a single card keyed
`(underlying, option_type)` and then raises the parent's clock to the newest leg:

```
scanner.py:315-316   if r.timestamp_ms > parent.timestamp_ms:
                         parent.timestamp_ms = r.timestamp_ms
```

Each leg keeps its own bar ([scanner.py:289-290](backend/app/services/kite_engine/scanner.py:289),
stamped at birth in [scanner.py:380](backend/app/services/kite_engine/scanner.py:380)).

The two renderers then disagree, deliberately and unreconciled:

- header → [SterlingKiteEnginePane.tsx:712](frontend/src/components/kite/SterlingKiteEnginePane.tsx:712)
  `const d = new Date(row.timestamp_ms);`
- chart → [signalMarkerLogic.ts:41](frontend/src/components/charts/signalMarkerLogic.ts:41)
  `const premiumTs = leg.signal_timestamp_ms ?? leg.entry_timestamp_ms ?? row.timestamp_ms;`
  under a docstring that says *"never from its grouped parent."*

Live proof — the exact row from screenshot S2 (`LT / derivatives`, header **11:15**):

| leg | its own signal ts | entry_px |
|---|---|---|
| LT26AUG4000CE (ATM) | 03 Aug 11:15 | 82.15 |
| **LT26AUG3950CE (ITM1)** | **03 Aug 09:15** | **95.00** |
| LT26AUG3900CE (ITM2) | 30 Jul 11:15 | 111.65 |
| LT26AUG3850CE (ITM3) | 30 Jul 11:15 | 144.15 |
| LT26AUG3800CE (ITM4) | 30 Jul 11:15 | 179.90 |
| LT26AUG3750CE (ITM5) | 03 Aug 09:15 | 265.05 |

The user charted LT26AUG3950CE, whose Entry marker sat on **03 Aug 09:15** — correct for
that leg. The header said **11:15**, which belongs to a different strike. `Entry 95.00` is
also correct for that leg. **Only the displayed time is wrong-by-construction.**

The deeper issue: this card is not one signal's strike ladder. It is **six independent
signals**, fired up to *four days apart*, merged into one row and sorted into a tidy
ITM ladder ([scanner.py:322-323](backend/app/services/kite_engine/scanner.py:322)) that
*looks* like one setup. The same applies to the TCS derivatives card (ATM/ITM1/ITM2 fired
15:15; ITM3/ITM4/ITM5 fired 14:15 — header 15:15).

Side effect that reads as "duplicate signals with different times": the header clock of a
live derivatives card **jumps** (14:15 → 15:15) whenever any other strike in the group fires.

**LATENT, same symptom, different trigger:** board times are formatted with
`toLocaleTimeString('en-IN', { hour, minute, hour12: false })`
([SterlingKiteEnginePane.tsx:713](frontend/src/components/kite/SterlingKiteEnginePane.tsx:713)) —
`'en-IN'` is a *locale*, not a timezone, and no `timeZone` option is passed, so times render
in the **browser's** zone while the chart is pinned to IST. Not the cause here (the capture
machine is IST and the screenshot times match the payload), but every board time is wrong
for a non-IST browser.

---

## Complaint 2: "doesn't show a signal that IS on the chart"

**Root cause: the option ladder is re-picked against the LIVE spot on every scan, so a
contract that fired a real signal silently drops off the board once spot drifts far enough
that the contract is no longer inside the ITM5..ATM window.** Status: **CONFIRMED.**

```
scanner.py:853   spot = float(q[qsym].get("last_price") or 0.0)     # LIVE quote
scanner.py:869   contracts = pick_contracts(chain, spot=spot, moneynesses=moneyness, …)
```

Only the contracts in that live window are fetched and evaluated, and the band label `m` is
stamped onto the leg from that same live-spot ordering. Proof, same TCS signal, two observations:

| | 13:45 (screenshot S3) | 15:27 (live payload) |
|---|---|---|
| ATM | 2460 CE | **2440 CE** |
| ITM1 | 2440 CE | 2420 CE |
| ITM5 | 2360 CE | 2340 CE |
| 2460 CE | present, Entry 63.70 | **gone** |
| 2340 CE | absent | **present, Entry 144.0** |

TCS moved ~3 points and a contract with a live signal left the board while a new one
appeared. The user opens 2460 CE, sees its SuperTrend and its entry arrow, and finds no row.

This confirms a claim previously filed as *unverified* in
`docs/kite_signal_audit_2026-08-04.md:536`.

Secondary contributors:

- **`held_contract_scan` re-runs `_compile_rows` on already-grouped rows, keeping only
  `legs[0]`** — `_compile_rows` reads `r.legs[0]` ([scanner.py:281](backend/app/services/kite_engine/scanner.py:281))
  and is only idempotent for ungrouped input, so every other leg of a held contract is
  dropped. (Also filed unverified at `kite_signal_audit_2026-08-04.md:586`.)
  **CONFIRMED — reproduced.** Six per-contract rows → `_compile_rows` → 1 card/6 legs; feeding
  that card back in (as [held_contract_scan.py:215](backend/app/services/kite_engine/held_contract_scan.py:215)
  does) → 1 card/**1 leg**, 5 dropped. The existing guard test
  `test_compile_rows_is_idempotent_for_grouped_derivative_legs`
  ([test_scanner.py:1159](backend/tests/engines/sterling_kite_engine/test_scanner.py:1159))
  does **not** cover this: despite its name it only feeds *ungrouped* 1-leg rows.
- **Chart-marker snapping.** The marker is not drawn at the backend's bar; the client
  re-derives the transition and snaps to the nearest one within a tolerance
  ([TradingViewKiteChartLegacy.tsx:1316](frontend/src/components/charts/TradingViewKiteChartLegacy.tsx:1316)
  `freshTripleAlignmentIndex(…, premiumTargetSec, 'up', premiumTolerance)`). When no
  client-side transition lands inside tolerance, no marker is drawn even though the row is
  real — the inverse of this complaint, and the mechanism behind complaint 3. **CONFIRMED (code).**

---

## Complaint 3: "shows a signal that doesn't look right on the chart"

**Root cause: three separate things, none of which is a bad signal.** Status: **CONFIRMED.**

1. **Ended signals share the list with live ones.** The scan itself reports
   `7 live signal(s) + 38 ended`; the capture has 46 rows, all `is_fresh=false`, most
   `is_active=false`. A row the user checks may have legitimately ended days ago.
2. **Band labels are scan-time, not signal-time** (same mechanism as complaint 2): the row
   labelled "ITM1" at 13:45 was a different contract than the row labelled "ITM1" at 15:27.
   Row→contract identity moves under the user.
3. **A grouped derivatives card mixes legs from different days** (see complaint 1), so
   checking "the" signal on "the" chart compares things that were never one signal.

### Explicitly ruled out

- **Pre-warmup / fabricated signals on short option histories.** The scan diagnostic
  `bars 5–285` across 240 option charts looked damning, and the guard in
  `evaluate_derivative_contract` is only `len(candles) <= 1`
  ([scanner.py:343](backend/app/services/kite_engine/scanner.py:343)) versus the spot path's
  `<= cfg.warmup + 1` ([scanner.py:208](backend/app/services/kite_engine/scanner.py:208)).
  But `entry_transitions` zeroes `longs[:warmup+1]` / `shorts[:warmup+1]`
  ([regime.py:127-128](backend/app/engines/sterling_kite_engine/regime.py:127)) and
  `compute_regime` sets `valid[cfg.warmup:]` ([regime.py:105-106](backend/app/engines/sterling_kite_engine/regime.py:105)).
  Numeric test (warmup=21, HA basis, monotone and V-shaped series at 2/3/5/8/10/12/15/21/22/25/30
  bars): **no signal index below warmup is ever emitted.** The docstring claim at
  scanner.py:339-341 holds. **NOT a defect.**
- **SuperTrend candle-basis mismatch.** Backend default is `heikin_ashi`
  ([config.py:38](backend/app/engines/sterling_kite_engine/config.py:38)) and `compute_regime`
  branches on the same string ([regime.py:96](backend/app/engines/sterling_kite_engine/regime.py:96));
  the frontend computes studies from `props.isHA ? heikinAshi(candles) : candles`
  ([TradingViewKiteChart.tsx:113](frontend/src/components/charts/TradingViewKiteChart.tsx:113)).
  All three screenshots have the chart in Heikin Ashi, so they agree. **NOT the cause here.**
  **LATENT:** the chart's candle-style toggle silently re-bases the *visible* SuperTrend onto
  raw OHLC while the backend stays on HA, and `candle_basis` is absent from the config API so
  the user cannot see or match it. The comment at
  [regime.py:91-95](backend/app/engines/sterling_kite_engine/regime.py:91) also still claims
  "the production scanner defaults to regular OHLC", contradicting config.py:38.
- **Spot-vs-derivatives React key collision.** `rowKey` is
  `${r.token}:${r.option_type}:${r.timestamp_ms}` ([SterlingKiteEnginePane.tsx:1964](frontend/src/components/kite/SterlingKiteEnginePane.tsx:1964)) —
  it omits `source`, but `token` is the underlying's token for spot rows and the option's
  token for derivatives rows, so the two cannot collide. The key *can* collide for a spot row
  vs a **Navigator** row (both keyed on the underlying's token); no Navigator rows exist in
  the live payload. **LATENT, not this symptom.**

---

## The one architectural defect underneath all five

**A "row" has two incompatible meanings that were never reconciled: for spot rows it is
*one signal plus a ladder of candidate strikes*, and for derivatives rows it is *a bag of
independent per-contract signals* collapsed by `(underlying, option_type)` and relabelled
against live spot — and the board renders both with the same card, the same columns and no
provenance label.**

Everything above follows: the header needs one clock for six legs (complaint 1), the two
sweeps produce two unlabelled cards (4, 5), and the ladder is a live-spot view rather than a
record of what fired (2, 3).

---

## Ranked fixes

| # | Defect | Change at | Fix | Blast radius | Proving test |
|---|---|---|---|---|---|
| 1 | No provenance label | `SterlingKiteEnginePane.tsx:634` | Render a `SPOT` / `DERIV` / `CONFLUENCE` badge next to the existing Navigator badge, from `row.source`. Delivers the L86 hint's promise. | UI only; `source` already in payload | Board test asserting both TCS cards render distinct badges |
| 2 | Header clock unrelated to the charted leg | `SterlingKiteEnginePane.tsx:712` + per-leg row render | Show the **leg's** `signal_timestamp_ms` on each leg row; make the header time explicit ("latest 15:15") or drop it for grouped deriv cards. Do **not** change `scanner.py:315-316` — the parent clock is load-bearing for sort/retention. | UI only | Fixture = live LT row (legs 30 Jul/09:15/11:15); assert the ITM1 row shows 09:15 |
| 3 | Board times in browser TZ | `SterlingKiteEnginePane.tsx:713`, `:663` | Pass `timeZone: 'Asia/Kolkata'` to every `toLocale*` call on the board. | UI only | Render under `TZ=America/New_York`, assert IST output |
| 4 | Band labels + ladder membership are live-spot | `scanner.py:853`, `:869` | For a row that already fired, resolve the ladder against the **signal-bar** underlying close (`under_close_by_ts`, already computed at `scanner.py:844`) instead of the live quote; keep live spot only for fresh rows. | Backend; changes which contracts appear for retained rows — verify against auto-exec leg pick | Two scans with spot moved ±1 strike: retained row's leg set and labels must not change |
| 5 | `held_contract_scan` truncates legs | `scanner.py:281` | Make `_compile_rows` genuinely idempotent: when `r.legs` has >1 entry, absorb all legs rather than `r.legs[0]`. | Backend; the docstring at L262-272 already warns this function is re-entered | Feed already-grouped 6-leg rows through `_compile_rows` twice; assert 6 legs survive |
| 6 | Ended and live signals indistinguishable in one list | board list render | Separate or clearly mark the 39 ended rows; the scan already knows the split. | UI only | Assert ended rows carry an ENDED treatment |
| 7 | Chart marker snaps to a client-recomputed bar | `TradingViewKiteChartLegacy.tsx:1316` | When no transition lands inside tolerance, draw the marker at the backend bar anyway (and flag the disagreement) instead of drawing nothing. | Chart only | Row whose backend bar has no client transition → marker still drawn |
| 8 | Backend `candle_basis` invisible/unmatched | `config.py:38`, `regime.py:91-95` | Expose `candle_basis` in the config API and warn when the chart style disagrees; fix the stale comment. | Config surface | Config response includes `candle_basis` |

## Not bugs — do not "fix"

- Two TCS cards under `scan_source="both"` are **correct behaviour**: two real signals from
  two real strategies. The bug is that they are unlabelled, not that they exist.
- `Entry 95.00` on the LT ITM1 leg is **correct** for that leg.
- Differing SL/TSL between the spot and derivatives cards for the same contract is
  **correct** — an underlying-ST stop and a premium-ST stop are different stops.
- The `len(candles) <= 1` guard in `evaluate_derivative_contract` is harmless (see ruled-out).

## Revision (same day) — measured scale changes the recommended fix

Measured against the live payload:

- **24 of 30 derivatives cards currently merge legs from more than one trigger bar.**
  Worst cases: SENSEX 13 legs across **7** bars, NIFTY 50 18 legs across 4, RELIANCE 6 across 4.
  So the wrong header clock is not an edge case — it is the normal state of a derivatives card.
- **39 of 46 rows are ended signals**; only 7 are live.
- Simply adding the trigger bar to the group key would produce **91 cards instead of 46** —
  truthful, but unusable as a flat list.

Therefore the fix-table row 2 ("show per-leg times") and a naive group-key change are both
insufficient. The grouping is **display-only** (auto-exec's `place_cb` runs on the raw
pre-grouping row — [scanner.py:924](backend/app/services/kite_engine/scanner.py:924), and
`_compile_rows` has only two call sites, both assigning `us.rows`), which means the honest fix
is to stop grouping in the backend and make bar-and-source *levels of a view hierarchy*
(underlying → source → trigger bar → contracts) rather than facts flattened into one card.
See the structural plan discussed with the author.

## Caveats on this audit

- The adversarial second-layer verification agents were killed by a session limit mid-run
  (4 of 6 audit dimensions returned; all 6 verifiers, the completeness critic and the
  synthesizer did not). Every finding above was instead verified by hand against source
  and, where marked CONFIRMED, against the live payload. Two dimensions never reported:
  **monkey-patch layering** (`signal_board_runtime.py` replaces `evaluate_item`,
  `_fetch_candles` and `scan`; `expiry_series_runtime.py` may stack on top) and a full
  **chart↔backend parity** sweep. Those remain open.
- Findings from the audit that concern the **confluence** path are real code defects but
  cannot explain these screenshots: live `scan_source` is `both`, and no confluence rows
  exist in the capture. They are recorded in the run journal, not promoted here.
- Raw evidence: `signals.json`, `act.json` and `LIVE_EVIDENCE.md` in the session scratchpad;
  run journal at `subagents/workflows/wf_e01aa2e8-d63/journal.jsonl`.
