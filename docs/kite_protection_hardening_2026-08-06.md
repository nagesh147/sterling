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
