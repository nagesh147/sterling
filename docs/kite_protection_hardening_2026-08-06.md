# Kite position protection — review of `41f1d00` and the fixes on top

**Date:** 2026-08-06 · **Branch:** `kitev2-develop` · **Base:** `41f1d00` ("Protect hand-placed
orders, and make the target a real exit")

Real-money review. Every defect below was traced to a line and pinned by a test that fails
against `41f1d00` and passes after the fix (17 new tests verified both ways by stashing the
source and re-running).

Method: five adversarial verifiers (one per claimed defect, each told to REFUTE) plus a diff
sweep and a test-coverage sweep, then hand-verification of everything they returned.
Their verdicts are in the transcript: C2/C3 CONFIRMED, C1/C4/C5 PARTIAL with the scope
corrected, plus 22 additional findings. Two of their PARTIAL corrections changed what I fixed
and are recorded below.

---

## What `41f1d00` got right

* `positions.register` has exactly one call site (`protection.arm_position`), so there is a
  single arming path instead of an auto-exec-only one.
* A target is the second leg of an **OCO** GTT, not a second server-side sell path — the
  exchange enforces mutual exclusion instead of our code.
* `_exit_position` returns a bool so callers can tell a real exit from a bail.
* A position with no `gtt_id` is unaffected by the stand-down logic (`monitor.py:162`).

## The one defect that mattered most

**The commit fixed the wrong order endpoint.** `place_manual_order` backs
`POST /kite/engine/order` — the detail panel and the Telegram bot. The signal board's Buy
button goes **Buy → OrderWindow → `usePlaceKiteOrder` → `POST /kite/orders`**
(`frontend/src/hooks/useKite.ts`), which placed the order raw: no registry row, no broker
stop, no tick monitor, no expiry square-off — while the board rendered SL, TSL and Target
beside it. With `auto_execute=false` every position is hand-placed, so this was the path
essentially all real positions took.

Fixed by extracting `service.arm_manual_option_buy` and calling it from both endpoints
(`app/api/v1/endpoints/kite.py`), for NFO/BFO symbols ending CE/PE only, never fatally.

---

## Fixes, worst first

| # | Defect | Where | Consequence |
|---|--------|-------|-------------|
| 1 | Board Buy bypassed all protection | `endpoints/kite.py:640` | every hand-placed entry unguarded |
| 2 | Exit intent inferred from **price**, not the caller | `monitor.py:156` | the exits a GTT will never perform were the ones skipped |
| 3 | Manual Sell reported "Position closed at market" without selling | `service.py:106` | user believes they are flat; retry blocked 60 s by the idempotency key |
| 4 | `GONE` conflated "already triggered" with "not there any more" | `protective_stop.py:155` | a GTT deleted in the Kite app, or triggered-then-rejected, left the position with **no exit at all, permanently** |
| 5 | Partial fill resized the position but not the resting GTT | `monitor.py:126` | trigger sells more than we hold → **naked short** |
| 6 | Prior-GTT cancel only logged, then a second trigger armed | `protection.py:176` | two resting SELLs against one long |
| 7 | Scale-in overwrote the registry row | `positions.py:124` | earlier lot kept no stop |
| 8 | Exit SELL failing after a successful cancel left `gtt_id` set | `monitor.py:222` | every later tick deferred to a trigger we cancelled ourselves |
| 9 | A `COMPLETE` postback with no order id resurrected a CLOSED position | `monitor.py:114` | reopened at the exit price, then sold again |
| 10 | An exit filled outside the engine left the GTT resting | `monitor.py:94` | orphan SELL → naked short |
| 11 | Positions stuck `PENDING` were invisible to every guard | no reconciliation existed | a dropped WS postback left a real position unguarded |
| 12 | `plan_for_symbol` armed the first leg found — often an ENDED row | `protection.py:95` | stale trail; if above the live premium the GTT fires on acceptance and sells the entry immediately |
| 13 | `entry_delta` read a field `OptionLeg` does not have, then `abs()`d it | `protection.py:117` | always 0.0 → hand-placed stops never trailed; `abs()` was also wrong-signed for a PE |
| 14 | `protected`/`protection` dropped by the response model | `schemas.py:266` | the "UNPROTECTED" toast could never fire |
| 15 | Manual exits booked realized PnL at the **stop**, not the fill | `monitor.py:228` | fabricated number into the INR daily-loss breaker |
| 16 | A failed GTT trail was silent | `service.py:785` | registry and broker stop drift apart unnoticed |
| 17 | `DELETE /open-positions/{symbol}` swallowed a failed cancel | `endpoints/kite_engine.py:307` | resting SELL with nothing tracking it |

### The shape of #2 and #4 together

`_exit_position` now takes `price_stop_exit`, and only `on_tick`'s price-trail branch passes
`True`. When a cancel does not come back `CANCELLED` it asks the broker
(`protective_stop.stop_status` → `GET /gtt/triggers/{id}`, rate-limited to one probe per 15 s
per trigger) and acts on the answer:

| broker says | price-stop exit | any other exit |
|---|---|---|
| `TRIGGERED` | stand down | **stand down** — catches the OCO *target* leg, invisible to any price test |
| `ACTIVE` | stand down (it will fire) | sell — a GTT never performs a red-count/expiry/manual exit |
| `ABSENT` (404 / inert status) | **sell** — nothing there will exit us | sell |
| `UNVERIFIED` | stand down + `order_failed` alert | sell + alert |

`ABSENT` is returned only on hard evidence because a wrong `ABSENT` sells on top of a live
broker SELL and goes naked short, while a wrong `UNVERIFIED` costs a delayed exit the user
is told about. That asymmetry is deliberate.

### #18 — "hard evidence" was a single HTTP status code

The first cut of `stop_status` accepted exactly two things as proof that a trigger was
gone: an explicit inert status, or a **404**. Kite does not promise a 404 for a trigger it
no longer holds — a `400` / `InputException` is at least as likely — and on that answer the
probe returned `UNVERIFIED`, which stands a price-stop exit **down**. So the flagship fix
degraded to *announcing* the permanent-no-exit case instead of ending it: the position sat
open with nothing to exit it, plus an alert. `ABSENT` was hostage to a status code this
repo cannot pin, in the one direction where being wrong costs money.

`stop_status(client, trigger_id, *, tradingsymbol, direction)` now narrows through three
sources, cheapest first, and stops as soon as one is conclusive:

| # | Source | Conclusive when |
|---|--------|-----------------|
| 1 | `GET /gtt/triggers/{id}` | status is acting (`active`/`triggered`) or documented-inert |
| 2 | `GET /gtt/triggers` | the id is present (use its status) or **absent from a list we read** |
| 3 | `GET /orders` | an exit-side order for the symbol has filled / is working, or provably none has |

`ABSENT` now requires positive evidence from **two independent reads** — not on the GTT book
(so nothing will fire later) *and* no exit order filled or working (so nothing fired
already). Step 3 is also the only source that can see the case no GTT status can express:
a trigger that fired and whose market SELL the exchange **rejected** (freeze quantity,
circuit, margin) — trigger consumed, position unexited.

Two further tightenings fell out of it:

* an **unrecognised** status is now `UNVERIFIED`, not `ABSENT`. The trigger demonstrably
  exists at the broker, so "it will never fire" is a guess — the exact guess that sells
  twice. It falls through to source 2 instead.
* every call site passes the symbol. Without it source 3 cannot run and a missing trigger
  can only be reported `UNVERIFIED`, so the parameter being optional would silently
  reintroduce the defect.

Deliberately conservative in one place: an exit order from an **earlier round trip in the
same symbol today** also reads as working, so a same-day re-entry can hold a stop back.
That is a delayed exit the user is told about — the side of the trade-off this module
always takes.

14 tests (`TestAMissingTriggerIsProvedNotGuessed`); 7 fail against the previous cut, 7 are
regression guards on the stand-down direction that must keep passing.

### Scope corrections from the adversarial pass

* The red-count branch of `on_tick` was **not** misclassified: when the tick is at/below the
  stop, `price_exit` is true as well and the GTT genuinely fires. `price_stop_exit=bool(price_exit)`
  preserves that.
* `on_tick`'s target branch requires `not p.gtt_id`, so it could never reach the GTT block.
* The time stop does not run in live config (`time_stop_bars: 0`); fixed anyway, it was free.

---

## Deliberately not fixed

* **Partial manual exits.** `_exit_position` always exits the whole tracked position; a GTT-protected
  holding cannot be part-sold without re-arming the trigger for the remainder. The response now
  says so explicitly instead of implying a partial close happened.
* **Partial-sell registry accounting** through `POST /kite/orders`: an exit-side `COMPLETE` closes
  the whole row. Pre-existing.
* **`ArmResult.protected` counts a tick subscription while the position is `PENDING`**, which
  `on_tick` refuses to act on. Mitigated by #11 (reconciliation resolves PENDING within a scan)
  rather than by weakening the flag.

## Verification

* `backend/tests/engines/sterling_kite_engine/test_protection.py` — 18 → 55 tests. All 17
  fixes' tests fail against `41f1d00`, confirmed by stashing the source and re-running;
  #18's 7 behaviour-change tests fail against the first cut of `stop_status`, confirmed the
  same way.
* Full backend suite: **2289 passed**, 6 skipped, 1 xfailed. The 2 failures
  (`test_greeks_final.py::TestMonitorAllPnLRecord`, `test_zerodha_alerts.py::TestZerodhaAdapterPaper`)
  fail identically at `41f1d00` — pre-existing, unrelated.
* Frontend: `tsc --noEmit` clean, 237 tests pass.

## Still open before AUTO is enabled

The five `[critical]` items in `docs/kite_signal_audit_2026-08-04.md:383,406,430,459,487`
remain unverified. They are auto-exec-only, so they do not gate manual trading — but they do
gate `auto_execute=true`.

---

## Round 2 — the five `[critical]` auto-exec items

`docs/kite_signal_audit_2026-08-04.md` lists five `[critical]` claims under "Unverified
claims, worth checking". They were written before `41f1d00`, so each was re-checked against
the code as it stands rather than taken at face value.

| # | Audit line | Claim | Verdict |
|---|-----------|-------|---------|
| C1 | 383 | Rejected entry / externally-filled exit orphans the broker GTT | **PARTIAL** → fixed |
| C2 | 406 | `stop_mode="both"` fires GTT *and* monitor at one trigger → 2× sell | **CLOSED** |
| C3 | 430 | GTT armed on a PENDING entry, never cancelled on REJECT/CANCEL | **CLOSED** |
| C4 | 459 | Zero premium quote → real BUY, no stop, log claims `[both stop+monitor]` | **OPEN** → fixed |
| C5 | 487 | Live red count read from the entry-bar chip → every PE sold at entry | **OPEN** → fixed |

### Already closed by `41f1d00` + round 1

* **C2.** `monitor._exit_position` cancels strictly before selling and skips the sell unless
  the broker confirms nothing is acting (`monitor.py:275`). Pinned by
  `test_no_second_sell_when_the_gtt_could_not_be_cancelled` and `test_cancel_happens_before_the_sell`.
* **C3.** A `REJECTED`/`CANCELLED` entry with `filled_quantity` 0 cancels the GTT and zeroes
  `gtt_id` (`monitor.py:187`); a partial fill takes the other branch and *resizes* the trigger
  to what actually filled (`monitor.py:171`). The audit's precondition — "ticker_manager must
  start passing a client" — is satisfied at `ticker_manager.py:66`.
* **C1's live paths.** The broker-exit-fill branch cancels and chases the orphan
  (`monitor.py:132`).

### C1's residual — the orphan nobody was looking for

Every path that *creates* an orphan is closed at the point it happens. What none of them
covers is one that was **already** resting: the process restarted while a trigger was armed,
or a cancel failed and only logged "check Zerodha for a resting SELL" before the position left
the registry. Nothing ever looked again.

`_reconcile_orphan_stops` now runs each scan: any **active** trigger whose symbol is neither
in the broker's net positions nor in our registry is reported once. It **reports and never
cancels** — our abandoned trigger is indistinguishable from a stop the user placed by hand in
the Kite app, and deleting theirs would remove the protection they were relying on. The
broker's own net quantity is what makes the warning safe: a trigger over a real holding is
legitimate whoever placed it.

### C4 — auto-exec opened positions it could not exit

When the premium quote came back empty (strike untraded today, quote rate-limited,
`_resolve_premium_stop` swallowing an error) `stop_px` stayed 0 and *everything downstream
degraded silently*: `place_stop` refuses a trigger of 0, `should_exit(0, ltp)` is False on
every tick, and `_retranslated_stop` cannot re-derive a level from an entry premium of 0 — so
the stop stayed 0 for the life of the trade. The terminal printed `[both stop+monitor]` over
it, because the log reported `cfg.stop_mode`, i.e. what was *asked for*. Only the T-1 expiry
square-off would ever close it.

Two changes: **no stop, no trade** — auto-exec logs `order_blocked` and returns before placing
anything; and the `order_placed` line now prints `armed.describe()`, with a second
`order_failed` line when `armed.protected` is False. The manual path deliberately keeps the
opposite policy: the user asked for the fill and gets an explicit UNPROTECTED warning rather
than a refusal.

### C5 — the red counter was pointed at the wrong thing

Confirmed exactly as claimed. `want_red` came from `p.direction`, which is `"long"` for every
option — CE and PE alike, as `positions.py` documents. A bear signal's three SuperTrends are
all `-1` *by definition at entry*, so a PE scored 3-of-3 against the position it had just
opened; `one_red` fires at 1, so the monitor market-sold it on the first tick after the first
post-entry scan with the trend still perfectly in its favour. Two further errors compounded
it: the code read `row.alignment`, which is frozen at the **entry** bar and therefore never
moves, and it took whichever row matched the underlying first — the bull row, for a bear
position, under `scan_source="both"`.

* `EngineSignalRow.current_reds` — computed at `last_idx`, always live. Distinct from
  `exit_state`, which freezes at the exit bar so an ended row stops moving.
* `OpenPosition.signal_direction` — recorded at arm time. It cannot be inferred from the CE/PE
  suffix: a *derivatives*-source row runs the SuperTrend on the contract's own premium series,
  so a PE bought there really is a long signal.
* The trail updater matches on underlying **and** signal direction, and a scan with no
  matching row leaves the last count alone instead of resetting it to 0 — writing 0 there
  would silently disarm the red exit for a position already in trouble.

### Verification

* `test_protection.py` — 55 → 71 tests. Of the 16 new, 15 fail against the pre-fix logic
  (verified by reverting the three decision sites and re-running); the 16th is the deliberate
  narrowness guard proving the C4 abort does not block a resolvable entry.
* One existing test changed: `test_auto_exec_one_position_guard`'s fake broker gained a
  `get_ltp`. It was passing only because auto-exec would open an unprotectable position — an
  accidental dependency on the C4 defect, not a behaviour worth preserving.
* Full backend suite: **2305 passed**, 6 skipped, 1 xfailed, same 2 pre-existing failures.
  Frontend `tsc --noEmit` clean.

---

## Round 3 — C5 under independent attack

`01a90496` claimed C5 closed. Five adversarial verifiers were sent at it, each on a different
angle, each told its default position was that the fix is wrong. Four returned (the fifth and
the judge hit a session limit); **all four ruled FIX_INCOMPLETE with high confidence, and all
four actually ran code rather than only reading it.**

They confirmed the original defect was real — one reproduced it against the parent commit and
reported the actual number a bear position scored: **3**, against a threshold of 1.

They also found five ways the fix did not reach far enough. Two of those had been caught
independently while they ran; three had not.

| # | Hole | Effect |
|---|------|--------|
| 1 | The manual path never passed `signal_direction` | C5 **completely unfixed** on the path essentially every real position takes |
| 2 | Positions persisted before the field default to `"long"` | C5 survives a restart for anything open across the deploy |
| 3 | Every derivatives row is `direction="long"` on the same underlying string | a derivatives PE matched the spot **bull** row and read its count |
| 4 | Grouping collapses every strike under one parent | a position on any leg but the first read another contract's counter |
| 5 | `current_reds` defaulted to `0` on rows from the pre-fix cache | `0` means "nothing against us" — it **overwrote** a real count of 2 or 3 |

### 1 & 2 — the fix missed the path that matters

`LegPlan.direction` is hardcoded `"long"` — correct, a PE is long premium — and
`arm_manual_option_buy` passed only that. So every hand-placed position was stamped as a long
signal. With `auto_execute` off, hand-placed is *the* path, which makes this the same mistake
as round 1's headline defect: the fix landed on the branch almost nothing uses. `LegPlan` now
carries `signal_direction` from the row, and the manual arm passes it.

`OpenPosition.signal_direction` now defaults to `""` meaning **unknown**, not `"long"`, and is
read through `positions.signal_direction_of`, which falls back to the CE/PE suffix only for a
row that predates the field. The suffix is a fallback and never the source of truth — a
derivatives-source PE really is a long signal — but it errs toward a red exit that does not
fire rather than a position sold while the trend is still with it.

### 3 & 4 — `(underlying, direction)` does not identify a position

Every derivatives row carries `direction="long"` on the same underlying string the spot rows
use, so the match key could not tell them apart: a derivatives PE whose own premium trend was
intact matched the spot **bull** row and would be market-sold as the underlying broke down —
which is the normal state of affairs for a profitable PE. And `_compile_rows` groups every
strike of an underlying under one parent whose count belongs to whichever leg arrived first.

`_live_red_count` now matches the **exact contract** first — `OptionLeg.current_reds`, stamped
per contract in the derivatives builder and carried through grouping — and only then falls back
to underlying + signal direction, skipping derivatives rows entirely.

### 5 — zero is not "unknown"

`current_reds` is `Optional[int]`, `None` meaning the scan cannot say. `None` leaves the stored
count untouched; `0` would have disarmed the red exit one tick before it fired.

### Also fixed: a rollback could empty the position registry

Not a C5 finding, but found while checking persistence. `_load` rebuilt each row with
`OpenPosition(**d)` inside one blanket `except` that set `out = {}`. A payload written by a
newer build carries fields an older one has never heard of — so **one** unknown key discarded
**every** position for that user, leaving them unguarded and freeing the auto-open guard to
re-enter slots already held. Unknown keys are now dropped and each row is isolated.

### Known limit, accepted

If the signal that opened a position ends and no row of that direction is emitted again, the
red count freezes at its last value; the price trail and the expiry square-off remain. That is
the safe direction, but it is not a working red counter, and it is not fixed here.

### Verification

* `test_protection.py` — 71 → 88 tests. 12 of the 17 new ones fail against `01a90496`
  (verified by reverting the decision sites and re-running); the rest are regression guards.
* Full backend suite: **2322 passed**, same 2 pre-existing failures. Frontend `tsc` clean.

---

## Round 4 — the remaining gaps, the gate, and both "pre-existing" failures

### The two failing tests were not incidental

Both had been carried as "pre-existing, unrelated" since round 1. Neither was.

**`test_live_mode_requires_credentials`** was pointing at a real hole *in this session's own
work*. Every read on `KiteClient` answered with a stub — `[]`, `{"net": [], "day": []}`,
fabricated paper balances — whenever `access_token` was empty, **regardless of `is_paper`**.
Round 1 then built `stop_status` to treat an empty GTT list plus an empty order book as
positive evidence that nothing is protecting a position, and to place its own SELL on that
evidence. So an expired or dropped session manufactured exactly that evidence and would have
gone **naked short on top of a live broker stop** — the precise failure the whole asymmetry
was designed to prevent, defeated by a stub. `_allow_sessionless_read` now raises for a live
client with no session; paper is untouched. A test pins it: with the guard removed, the probe
returns `ABSENT` and the monitor sells.

**`test_monitor_all_records_pnl_history`** sat next to two defects of its own. `_monitor_one`
ended in a bare `except Exception: return None`, so `monitor-all` reported
`open_positions_checked=N` while having monitored none of them — no snapshot, no trail update,
no exit check, and nothing anywhere saying so. And the P&L snapshot whose comment read "Record
P&L snapshot first — ensures capture regardless of which exit path fires" sat *after* the
red-count exit's early return, which was itself handed `estimated_pnl=0.0` and
`current_dte=0` — so **every red-count exit closed a position while reporting a P&L of exactly
zero**. DTE and P&L are now computed before any exit path can return, the snapshot really is
first, and the handler logs. The test's own mock adapter was never reaching the code
(`adapter_manager.get_adapter()` wins over `app.state.adapter` in all six position endpoints),
so the fixture now overrides both.

### The frozen red counter is now audible

Round 3 documented this and left it: when the signal that opened a position ends and no row of
that direction is emitted again, the count holds its last value forever. Holding it is still
the right call — inventing a `0` disarms the exit outright — but a counter that has silently
stopped counting looks exactly like a working one on the board. `OpenPosition.red_count_ms`
records each refresh, and after three scan intervals without one the user is told, once, that
the red-count exit is not being maintained for that position and only the price trail and the
expiry square-off apply.

### Auto-execute is gated

It was a plain boolean any client could flip. `service.autoexec_preflight` now runs on the way
ON (never OFF) and refuses when the engine cannot account for what it is already carrying:
open positions with no stop, entries stuck `PENDING` past the fill grace window, or a red
counter that stopped updating. It returns the reasons and `force=true` overrides — a gate, not
a prohibition, and an informed choice rather than a silent one.

### One round-3 claim refuted

A verifier reported the red exit as "mathematically unreachable" under `three_red` /
`three_red_signal`. It is not: thresholds are 1–3, the counter is bounded at 3 by construction,
and `red_line_count` returns 3 when all three lines are against the signal. Both are now
pinned by tests so the claim does not resurface.

### Verification

* `test_protection.py` — 88 → 102 tests. Full backend suite **2343 passed, 0 failed** — the
  first fully green run of this work. Frontend `tsc` clean, 393 tests pass.
* Two existing tests changed, both because they had been asserting the defect:
  `test_get_auctions/alerts_empty_without_session` asserted that a **live** sessionless client
  returns `[]`; they now assert it raises and still makes no network call, with the paper case
  added alongside.
