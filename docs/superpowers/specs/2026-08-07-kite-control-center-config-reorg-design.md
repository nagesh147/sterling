# Kite control center — trade configuration reorganisation

Date: 2026-08-07 · Branch: `kitev2-develop` · Base commit: `454aab4b`

## Why

Every trade setting in the Kite control center is real-money. Today they are
spread across four panels with no owner, and the split between them is
half-finished: the universe and the signal source were moved into a "shared"
panel, but strike coverage and expiries — which Navigator reads through exactly
the same code path — stayed behind on the SuperTrend page. A user changing
strike coverage from a page titled "SuperTrend Engine" silently moves Navigator
too.

Three specific defects the reorg has to fix, not just re-skin:

1. **`hybrid_st_weight` is a dead control.** It is rendered as an editable
   number, saves, says "Saved", and fires a full rescan — and nothing in
   `engines/sterling_kite_engine/` or `services/kite_engine/` reads it. The
   readers found by grep belong to `engines/directional/trailing_stop.py` and
   `paper_store.py`, which build their own config objects.
2. **"Advanced auto-execution guards" is a lie for two of its five fields.**
   `_square_off_expiring` (`service.py:783`) and `_time_stop_positions`
   (`service.py:812`) iterate `positions.open_positions(uid)` — the whole
   registry, which includes hand-placed orders armed by `protect_manual_orders`
   (`service.py:213`). Both guards apply to manual positions and are filed under
   a heading that says they do not.
3. **The same field behaves differently depending on which surface you clicked.**
   `patch()` defaults to `rescan=false` in `EngineConfigurationPanel.tsx:107` and
   `rescan=true` in `SharedScanSetupPanel.tsx:83`, so `exit_mode` rescans from
   the settings page but not from the board header dropdown. Rescan policy is a
   property of the panel, when it is a property of the field.

Plus the naming problems the user called out: the board's source dropdown has no
label, and the same `scan_source` values are called "Derivatives" on one page and
"Options" on another (`EngineConfigurationPanel.tsx:53` vs
`SharedScanSetupPanel.tsx:23`).

## The organising idea

Two axes, applied consistently.

**Axis 1 — ownership.** A setting belongs to exactly one of four layers:

| Layer | Means | Home |
|---|---|---|
| **Market & Contracts** | What gets scanned and which contracts are considered. Read by *both* engines. | `market` |
| **SuperTrend** | Only exists because the strategy has three SuperTrend lines. | `engine` |
| **Navigator** | Only exists because Navigator reads AVWAP/flow/gamma. | `navigator` |
| **Trade Rules** | Engine-independent: how an order is sized, guarded and protected once a signal exists. | `rules` |

Anything shared is shown on its owner's page and *pointed at* from everywhere
else. Never editable in two places.

**Axis 2 — who placed the order.** Every Trade Rules field is tagged
`MANUAL`, `AUTO`, or `BOTH`, from backend evidence, and the page has a scope
filter so "show me only what affects my manual trades" is one click.

The manual/auto split is a **tag on a shared field, not a duplicated field.**
Duplicating e.g. a stop mode into a manual copy and an auto copy would let the
two disagree, and the backend cannot honour a disagreement — `arm_manual_option_buy`
and the auto path call the same `protection.arm_position` with the same
`cfg.stop_mode` (`service.py:217`). A UI that implied otherwise would be lying
about real money.

## Evidence for the manual/auto tags

| Field | Tag | Evidence |
|---|---|---|
| `protect_manual_orders` | MANUAL | `service.py:149,192` — only consulted on the hand-placed BUY path |
| `stop_mode` | BOTH | `service.py:217` (manual arm) and the auto arm both pass it |
| `exit_mode` | BOTH | frozen onto the position at arm time, `protection.py:311`, for manual arms too |
| `trail_target`, `exit_aligned_trail`, `price_stop_exit` | BOTH | they compute the board plan that `protection.plan_for_symbol` hands to a manual arm |
| `expiry_square_off_days` | BOTH | `service.py:783` iterates every registry position |
| `time_stop_bars` | BOTH | `service.py:812` iterates every registry position |
| `risk_sizing`, `risk_pct`, `max_lots` | AUTO | `service.py:585-616`, inside `_make_place_cb` only |
| `adx_min`, `atr_pct_min` | AUTO | `service.py:511-516`, skips an auto entry only |
| `max_spread_pct`, `min_oi` | AUTO | `service.py:623-627` |
| `block_entry_minutes_before_close` | AUTO | `service.py:475` |
| `max_daily_loss_pct` | AUTO | `service.py:485` |
| `wire_risk_infra` | AUTO | `service.py:636` |
| `vehicle`, `directional_mode`, `itm_depth`, `target_delta`, `futures_expiry`, `enabled_vehicles` | AUTO | they choose the contract the engine buys; a manual trader picks their own |

`auto_execute` and `is_paper` are the two master switches and live on their own
page.

## The single registry

`frontend/src/components/kite/config/registry.ts` becomes the one place a config
field is described:

```ts
interface FieldDef {
  key:     keyof EngineConfigModel;
  label:   string;      // one name, everywhere
  help:    string;
  owner:   'market' | 'supertrend' | 'execution';
  applies: 'manual' | 'auto' | 'both';
  stage:   'discovery'|'universe'|'entry'|'size'|'stop'|'trail'|'target'|'exit'|'protection'|'guard';
  rescan:  boolean;     // does changing it invalidate the board?
  home:    SectionId;   // where the editable control lives
}
```

Everything reads from it:

* the settings panels render their fields from it;
* the signal-board header dropdowns take their labels and options from it;
* `useConfigPatch()` — one hook, used by every surface — decides whether to
  rescan from `def.rescan`, so **a field cannot behave differently depending on
  where it was changed**. This is the structural answer to "all the settings
  should sync between the settings page and the signal-table shortcuts".

Option sets (`SCAN_SOURCE_OPTIONS`, `EXIT_MODE_OPTIONS`, `TRAIL_OPTIONS`,
`STOP_MODE_OPTIONS`, `STRIKE_GROUPS`) move into the registry too, killing the
"Derivatives"/"Options" drift by construction.

## New navigation

The rail gains group headings and two new sections; `orderSelection` is absorbed.

```
CONNECTION      account       Account & Login
TRADING         mode          Trading Mode          ← new: paper/live, manual/auto, what's running
                market        Market & Contracts    ← renamed from "Scan Setup", absorbs strikes + expiries
                rules         Trade Rules           ← new: sizing, guards, protection, tagged manual/auto
SIGNAL ENGINES  engine        SuperTrend            ← now only SuperTrend strategy mechanics
                navigator     Value-Flow Navigator
PLATFORM        markets       Markets & Tools
                notifications Notifications
                experience    Experience
```

Legacy deep links keep working: `sharedScan → market`, `orderSelection → rules`,
and the existing `kite_connect_tab` mappings are preserved.

### Page contents

**Trading Mode** — `is_paper`, `auto_execute`, `engine_enabled`, and a read-only
line for Navigator's own enable/`auto_execute_originated`, because today those
are two independent arming switches for real orders that never mention each other.

**Market & Contracts** — instruments (indices + F&O stocks), signal source,
**strike coverage** (moved off the SuperTrend page), **index expiries** (moved),
stock expiries rendered as the exchange constraint it actually is rather than a
permanently-ticked fake checkbox (`schemas.py:458` discards any submitted value),
and the live scan-cost readout.

**Trade Rules** — scope filter `All / Manual / Automatic`, then lifecycle order:
Entry → Position size → Stop loss → Trailing stop → Target → Exit → Safety net.
Each field carries its applicability chip. Trailing stop / Exit / Target show
pointers to the owning engine rather than duplicate controls, and the Target
group states honestly that SuperTrend is trend-following and quotes no target
while Navigator supplies one.

**SuperTrend** — `trail_target`, `exit_mode`, `exit_aligned_trail`,
`price_stop_exit`, plus pointers to Market & Contracts. `hybrid_st_weight` is
removed from the UI (dead control); the field stays in the schema so stored
configs still deserialise.

### Signal board header

`SOURCE [Derivatives ▾]  EXIT [1 Red ▾]  │  VIEW [Combined ▾]` — the two engine
dropdowns get caps labels matching the existing `VIEW` treatment, and their
options come from the registry, so the board and the settings page can never
disagree about what a value is called.

## Deliberate behaviour changes

Two, both narrowing waste rather than changing trading:

1. **`protect_manual_orders` no longer forces a rescan.** The old panel passed
   `rescan=true` when it was toggled, costing a multi-minute full scan. It is
   read only by `place_manual_order` / `arm_manual_option_buy` and by nothing in
   the scanner, so no board row changes when it flips. Every other field's
   rescan flag matches the old behaviour exactly.
2. **`hybrid_st_weight`'s control is gone**, as above. It was the other field
   that forced a rescan for nothing.

`scan_expiries_stocks` is the one config field with no control anywhere, which
is correct: its validator discards whatever it is sent and always returns
`["monthly"]`, so the page states the exchange constraint instead.

Applicability tooltips cite backend *function names*, not line numbers —
line numbers drift with every commit and these strings are user-visible.

## What "shared with Navigator" actually means

The first draft of this page asserted that "both signal engines read every
setting here". That is false, and an adversarial review caught it. Field by
field, from `navigator/runtime.py`:

| Field | Reaches Navigator? | Where |
|---|---|---|
| `strike_moneyness`, `scan_expiries*` | **Always**, whatever its scan scope | passed on every pass when Navigator resolves legs for its own setups |
| `scan_indices`, `scan_stocks`, `scan_all_stocks` | **Only while Navigator's scan scope is "shared"** | `_resolve_nav_universe` |
| `scan_source` | **Never** | Navigator carries its own `scan_source` and reads that one unconditionally |

`scanner.py` does not read `scan_source` at all — the engine's two readers are
`service.scan_user` and `service._make_place_cb`. The registry's `evidence`
string named the wrong file.

So each field now carries a `navigator: 'always' | 'when-scope-shared' | 'never'`
tag and a **BOTH ENGINES / SUPERTREND ONLY** chip that reflects the live scope,
instead of one blanket sentence that was only mostly true.

This also exposed a pre-existing bug the copy was papering over: Navigator's own
signal-source picker was rendered **only** in custom scope, while the panel
displayed the *engine's* source above it as "Currently covering". On a shared
scope the value Navigator actually used was therefore neither visible nor
reachable. The picker now renders in both scopes.

## Concurrency: partial writes

`POST /config` replaces the whole model, so every UI write was a
read-modify-write over all 38 fields — and anything that had moved since the
client's copy was fetched got silently reverted. New `PATCH /kite/engine/config`
merges only the named fields (unknown keys are rejected 422, and the merge is
re-validated through the model so field validators still run). Every frontend
writer now sends only what changed, so a write cannot revert a field it does not
mention. Five backend tests cover it, including the concrete two-surface
revert scenario.

Related fixes in the same area:
* `useEngineConfig` now revalidates (60s + on focus). It was the only query
  never refreshed, despite being the one that decides real-money behaviour.
* `useRunScan` no longer invalidates in `onMutate` (that refetch raced its own
  optimistic `scanning: true` flag), gained an `onError` rollback (a failed scan
  left the board stuck "scanning"), and now merges rather than replaces so a
  SuperTrend scan stops wiping Navigator-originated rows off the board.
* `useResetEngineConfig` invalidates the derived caches, instead of leaving the
  board showing rows computed under the settings it just discarded.

## Non-goals

* No new backend config fields. The manual/auto separation is expressed as
  applicability, not as duplicated storage.
* No change to any trading behaviour. `hybrid_st_weight` losing its control
  changes nothing because nothing read it.
* Navigator's own settings page is not restructured. It keeps its existing
  layout; only the scan-scope honesty fix and the shared source vocabulary
  landed here.

## Test contract

`cd frontend && npx vitest run src/components/kite/__tests__` — 38 files, 237
tests, green on `454aab4b`.

Tests that must be updated because the IA they assert is what is changing:
`ConnectPane.settings-hub.test.tsx` (rail names and homes),
`ConnectPane.navigator.test.tsx`, `SharedScanSetupPanel.test.tsx` (renamed).
`queryAllByRole('tab') === 0` stays true — the rail remains buttons, not tabs.

New coverage added, because these had none and are the UI face of the 2026-08-06
real-money hardening: `price_stop_exit`, `protect_manual_orders`, the
applicability tags, and the registry-driven rescan policy.

Result: 261 kite tests green (was 237), 389 frontend tests green, 504 backend
kite+navigator tests green, `tsc` clean. The kite suite was run twice back to
back to rule out the order-dependent flakiness this repo is prone to.

An adversarial review did run: 23 candidate findings, 22 refuted, **1
confirmed** — the false "both engines read every setting here" claim, fixed
above. Note that 19 of the refutation agents died on a session limit partway
through, so the refuted set is less thoroughly established than the confirmed
one.
