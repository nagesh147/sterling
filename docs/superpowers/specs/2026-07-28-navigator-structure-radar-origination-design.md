# Navigator: Structure Radar, Signal Origination, and Auto-Execute

2026-07-28 · Kite Value-Flow Navigator extension

## Context

The Value-Flow Navigator (`backend/app/engines/navigator/`) is a fusion
evidence layer that reacts to the existing Sterling Kite triple-SuperTrend
engine: it only ever evaluates rows the base engine already produced
(`run_navigator_pass` loops over `rows` passed in from `scan_user`). Two
problems this design creates, both raised directly by the user:

1. **"Nav NO_DATA" felt permanent.** Root-caused this session to two real
   bugs (derivatives rows fetching the option contract's own short-lived
   token instead of the underlying's; NSE/BSE index candles always
   reporting `volume=0`, permanently starving AVWAP's volume-weighted
   anchor). Both are now fixed. But the deeper architectural question stands:
   Navigator only ever *reacts* — if SuperTrend never fires for an
   underlying, Navigator never has anything to say about it at all, even
   though its own AVWAP/volatility computation is independently capable of
   reading structure the moment there's enough candle history.
2. **The 4-way signal lens (SuperTrend / Navigator / Combined / Common) and
   the Signal-source dropdown (Spot/Derivatives/Both/Confluence) were
   visually undifferentiated**, and Navigator's scan scope was implicitly
   whatever `scan_source` already produces — both now fixed this session
   (toolbar divider + clarified tooltips; confirmed Navigator has no
   independent universe of its own).

This spec adds three new, additive, default-off settings that let Navigator
independently surface evidence and (opt-in) tradeable setups, without
touching any existing behavior when they're off.

## Goals / non-goals

**Goals**
- Navigator can compute and expose structure for a configured underlying
  continuously, not only when SuperTrend has a live row for it.
- Navigator can surface its own setup as a signal-table row when its fused
  evidence is strong enough, with no SuperTrend trigger required.
- That surfaced setup can, opt-in, become genuinely tradeable (manual and/or
  auto-exec), gated at least as conservatively as the existing `gate`
  operating mode.
- The existing 4-way signal lens and the Signal-source dropdown keep working
  exactly as documented, with an explicit, small rule for how the new row
  type participates in each lens.
- Users get an in-app Help section that walks through all of this by
  scenario, not just a settings reference.

**Non-goals**
- No new option-flow/gamma capture — origination reuses AVWAP + Volatility
  only (the two components that don't require live chain data). Flow/gamma
  stay exactly as they are today (`CHAIN_UNAVAILABLE` until chain capture is
  wired).
- No change to `operating_mode` (`shadow`/`advisory`/`gate`) semantics or to
  how Navigator attaches to real SuperTrend rows — that whole path is
  untouched.
- No new calibration/promotion mechanism. `auto_execute_originated` reuses
  the exact same `calibration_readiness == "ready"` gate the `gate` mode
  already requires, which stays `"not_ready"` in production today — so this
  is provably inert for real orders until a real calibration pipeline exists,
  exactly like `gate` mode is today.

## The three settings

All three live on `NavigatorConfigModel`, default off, independent of
`operating_mode`:

| Setting | Type | Default | What it does |
|---|---|---|---|
| `structure_radar_enabled` | `bool` | `False` | Navigator computes AVWAP + Volatility for every configured underlying every scan, in both directions, whether or not SuperTrend has a live row there. Feeds `/snapshot`, `/series`, `/status` continuously. Never adds a signal-table row by itself. |
| `signal_origination` | `"off" \| "heads_up" \| "full"` | `"off"` | When not `"off"`, a Navigator-only decision that reaches `CONFIRMED`/`HIGH_CONVICTION` (with no accompanying real SuperTrend row for that underlying+direction) is surfaced as a new signal-table row, `source="navigator"`. Implies structure-radar-style continuous computation even if `structure_radar_enabled` is off (origination needs the same underlying computation to exist; the radar toggle is about whether OFF-signal structure is *visible* outside the table, not a prerequisite). `"heads_up"` = visible, never executable (no manual or auto order). `"full"` = a real ATM leg is resolved for the row (same strike-picking Sterling already uses for spot-mode rows) and it becomes tradeable like any other row. |
| `auto_execute_originated` | `bool` | `False` | Only takes effect when `signal_origination == "full"`. Lets a Navigator-originated row fire through the *same* auto-exec path as every other row (`_make_place_cb`), gated by all of: the base engine's own `auto_execute` master switch, `calibration_readiness == "ready"`, and the decision's own `execution_eligible`. Config validation rejects `auto_execute_originated=True` with `signal_origination != "full"` rather than silently ignoring it. |

### Why reuse `fuse()` instead of a new scoring path

`determine_trigger()` already produces an `"avwap_fresh"` trigger whenever
`base.state in ("fresh", "active")` and AVWAP shows a fresh
pullback/continuation family within the alignment window — it does not
actually require the base signal to be a *real* SuperTrend trigger, just a
well-formed `BaseSignalEvidence`. Origination is implemented as: construct a
**synthetic, neutral** `BaseSignalEvidence` (`score_100=50.0`,
`strategy="navigator_origination"`, `signal_id` prefixed
`navigator_origin_`) for a given underlying+direction, and run it through the
exact same `evaluate_signal`/`fuse()` pipeline used for real rows. This
means:
- Zero new scoring/hard-gate/status logic — the existing weighted blend,
  compression-forces-WAIT, strong-opposition-forces-CONFLICT, and
  CONFIRMED/HIGH_CONVICTION thresholds all apply unchanged.
- The neutral 50.0 base score means AVWAP/volatility/flow/gamma entirely
  carry the decision — there's no fabricated "opinion" injected as if it
  came from a real trigger.
- `base_signal_id.startswith("navigator_origin_")` is the one new marker
  used to identify an originated decision — no schema field changes needed
  on `NavigatorDecision`.

### Exit/target mechanics for an originated position

SuperTrend rows exit via the red-line counter (`exit_state`, e.g. "1/1
red"), which doesn't exist for a row with no real triple-ST lines. Navigator
already computes exactly what's needed instead:
`avwap.propose_stop_target()` (spec §7.4, already shipped and tested) —
an R-multiple stop + target bracket off the AVWAP structure. A
Navigator-originated row's `stop_loss` is this proposal's `stop`, and its
target is exposed via the row's Navigator evidence panel (not a new field —
`NavigatorDecision` doesn't carry target today, and adding a display-only
target isn't required for this build; the AVWAP evaluation is already
inspectable via `/snapshot` for a user who wants to see it). This is a fixed
bracket, not a trailing exit — deliberately simpler than SuperTrend's
red-counter trail, since there is no multi-line trend structure to trail.

### Leg resolution ("full" mode only)

Reuses `attach_strikes()` (`scanner.py`) exactly as spot-mode rows do today:
given the synthetic row's `spot`/`direction`/`timestamp_ms`, resolve one ATM
leg from the same NFO/BFO dumps and `UniverseItem` the base engine already
loaded for this scan (`option_name=item.tradingsymbol`, `moneynesses=["ATM"]`,
respecting the user's configured expiry types). No new strike-selection
logic. In `"heads_up"` mode a leg is still resolved and shown (useful
information), it's simply never passed to a place/execute path.

## Signal-lens compatibility (SuperTrend / Navigator / Combined / Common)

The 4-way lens (`SterlingKiteEnginePane.tsx`, `signalMode`) is a pure
client-side display filter. A Navigator-originated row (`source="navigator"`)
is a new case each lens needs an explicit rule for, since by construction it
has no real SuperTrend basis:

- **Navigator lens** — no change needed. Its filter is `r.navigator != null`,
  which an originated row trivially satisfies.
- **Combined lens** — no change needed. It has no row-level filter today
  (shows every row, with the Navigator badge alongside when present); an
  originated row fits that as-is.
- **SuperTrend lens** — needs one explicit exclusion: filter out
  `source === 'navigator'` rows. This lens means "what would the board look
  like with no Navigator at all" — a row with no real triple-ST basis
  showing here (badge merely hidden) would be a phantom entry with no
  alignment chips behind it.
- **Common lens** — needs the same explicit exclusion: filter out
  `source === 'navigator'` rows. "Common" means *both systems agree*; a row
  only one system produced cannot structurally satisfy that, regardless of
  its own status.

Implementation: in `filteredRows`, before the existing `navigator`/`common`
branches, add
`if (signalMode === 'supertrend' || signalMode === 'common') result = result.filter(r => r.source !== 'navigator')`
folded into the existing branches (see plan for exact diff).

Visual treatment: an originated row's `alignment` is a neutral
`{fast:0,mid:0,slow:0}` placeholder (truthful — there is no real ST
alignment), so the card gets a small `Navigator idea` / `Navigator setup`
source tag in place of the usual alignment chips, using the same badge
pattern already used for the Navigator status pill.

## Help section (next to Connect)

New nav item `'help'` alongside `'connect'` (`KiteLayout.tsx`'s `NavItem`
union, `SimpleTerminal.tsx`'s nav button row, `KiteTab.tsx`'s content
switch). Scenario-first, not a settings reference:

1. **What Navigator is** — one paragraph, plain English.
2. **The 4 signal lenses** — each with one concrete example row.
3. **The 3 new settings** — each with "what changes on your board when you
   flip this," plus the safety notes (defaults, what's gated behind
   calibration).
4. **Quick-pick scenarios** — "I want to…" → settings to use:
   - "…ignore Navigator entirely" → SuperTrend lens (Navigator can stay off
     or on; the lens hides it either way).
   - "…see Navigator's take on my existing trades" → Combined or Navigator
     lens, radar/origination off.
   - "…see structure on my indices even when SuperTrend is quiet" →
     Structure Radar on.
   - "…let Navigator surface brand-new setups I take manually" → Signal
     Origination = Heads-up (browse only) or Full (tradeable, manual).
   - "…let it trade on its own" → Full + Auto-Execute Originated on (still
     blocked until calibration is promoted to ready).

Implemented as a new `HelpPane.tsx`, following the existing Kite pane
visual conventions (same primitives as `ConnectPane.tsx`/
`kiteSettingsPrimitives.tsx`), static content (no new API calls).

## Testing

- Backend: config validator (auto_execute_originated requires full);
  `synthetic_origination_base` adapter; `run_navigator_pass` with radar-only
  (decisions cached, no new row), with origination (row appended only on
  CONFIRMED/HIGH_CONVICTION, never duplicating an underlying+direction a
  real row already covers), with `"full"` leg resolution, and the auto-exec
  gate (all four conditions independently tested).
- Frontend: lens filter excludes `source==='navigator'` under `supertrend`/
  `common`, includes it under `navigator`/`combined`; NavigatorSettingsPanel
  renders the 3 new fields and disables auto-execute until `full` +
  calibration ready; HelpPane renders its scenario sections.

## Rollout

Ships with all three settings off, exactly matching the existing
"safe-by-default" pattern the rest of Navigator already uses
(`enabled=false`, `calibration_readiness="not_ready"`). No behavior change
for any existing user unless they explicitly opt in from the Navigator
settings panel.
