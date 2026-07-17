# Kite Sterling Engine — Confluence scan-source + signal-table columns

Date: 2026-07-17 · Branch: kite-mobile · Status: approved for implementation

## Problem

The Kite Sterling engine's `scan_source` has three modes (`spot`, `derivatives`,
`both`). The user wants a fourth, **confluence**, that fires a strike only when
the *underlying* signals a fresh entry AND that option's *own premium* SuperTrend
also confirms — the highest-conviction filter. Separately, the signal table
should expose a complete per-signal readout: **entry, exit, tsl, sl, target,
change, ltp**. Today the table has Entry, Stop, Change/%, and LTP; Exit, TSL
(as distinct from SL), and Target are missing.

## Current behaviour (confirmed by reading the code)

- **spot** — `evaluate_item` runs the triple-ST on the underlying's 1H Heikin-Ashi
  chart; `attach_strikes` attaches one candidate `OptionLeg` per selected moneyness
  (CE for a bull entry, PE for a bear entry). Legs carry no premium data (no
  per-option quote is made — this is the cheap path).
- **derivatives** — `evaluate_derivative_contract` runs the same triple-ST on each
  contract's OWN premium series, BUY-only (fresh up-transition). `_compile_rows`
  groups the per-contract rows into one row per (underlying, option_type) with a
  leg each. Legs carry `premium_spot` (entry) + `premium_sl` (trail).
- **both** — runs both passes; rows are tagged `source` (`spot`/`derivatives`) and
  shown side by side (a union, never merged). `_make_place_cb` has a per-underlying
  cross-guard so one move isn't auto-traded twice.

So the user's modes 1–3 already match the description. The new work is the 4th
mode and the three missing columns.

## Design

### 1. `confluence` scan source

**Trigger (reuses the existing entry definition on both sides):** a strike is
emitted iff
1. the **underlying** produces a retained entry (fresh full 3-ST alignment; the
   same output as spot mode), giving direction (long→CE / short→PE) and the
   candidate strikes, AND
2. that candidate option's **own premium** triple-ST is confirming — i.e.
   `evaluate_derivative_contract` returns a running/fresh BUY entry for it. Because
   we always *buy* the option, a correct bull-CE or bear-PE thesis makes the
   option's premium trend up, so the BUY-only premium pass maps directly.

**Output:** one merged row per underlying entry (`source="confluence"`), carrying
the underlying trigger and only the confirmed legs. Each confirmed leg carries the
option's own `premium_spot`/`premium_sl`/`entry_sl`/`is_active` (from its premium
regime), so confluence rows show full per-leg pricing.

**Scanner** (`scanner.py`): a new `_confluence_one(item)` pass, run over
`deriv_universe` when `source == "confluence"`:
- fetch + `drop_forming` the underlying candles; `evaluate_item`; `_retain_signals`.
- for each retained spot row, `pick_strikes` the candidate contracts (same call
  `attach_strikes` uses), then for each pick fetch its premium candles and
  `evaluate_derivative_contract`. Keep the leg only if the premium pass returns a
  retained (running/fresh) entry; stamp `premium_spot`/`premium_sl`/`entry_sl`/
  `token`/`is_active` from that premium row.
- emit the spot row with `source="confluence"`, `legs=confirmed`, `underlying_spot`
  set; append to `rows`. Diag counters reuse `deriv_*` fields plus a new
  `confluence_fired`.
- auto-exec fires like spot (guard key = underlying; one merged row ⇒ no
  double-fire), gated by the same `place_cb`.

`_compile_rows` already passes non-`derivatives` rows straight through, so
confluence rows need no grouping.

**Service** (`service.py` `scan_user`): thread `"confluence"` through the universe
split and the log summary. Confluence uses the underlying universe for the spot
leg and each candidate's premium for confirmation, so it is dispatched like the
derivatives pass (`deriv_universe = selected`, `spot_universe = []`). Add a
`confluence` branch to the scan-plan / scan-done log parts.

**Schema** (`schemas.py`): add `"confluence"` to `EngineConfigModel.scan_source`
and `EngineSignalRow.source` Literals.

### 2. New per-signal fields

- `OptionLeg.entry_sl: Optional[float]` — the initial hard stop at the entry bar
  = the `trail_target` (validated `fast`) ST line value at the entry index. For
  derivatives/confluence this is on the option's premium regime; computed in
  `evaluate_derivative_contract`.
- `EngineSignalRow.entry_sl: Optional[float]` — same, on the underlying regime, for
  spot/confluence rows (row-level SL when legs have no premium).
- `EngineSignalRow.exit_state: Optional[str]` — red-counter progress at the latest
  bar as `"<reds>/<threshold> red"` (threshold from `get_exit_threshold(exit_mode)`),
  the live Exit-column readout. Computed in `evaluate_item` (underlying) and
  `evaluate_derivative_contract` (premium).

**Target** is intentionally not a data field: the strategy is trail-following with
no fixed take-profit, so the column renders a constant `— (trail)` — exit is owned
by TSL + the Exit counter.

### 3. Table columns (7)

Frontend `SterlingKiteEnginePane.tsx` list-view header + leg rows:

| Column | Source | Notes |
|---|---|---|
| Entry | `leg.premium_spot` / row `spot` | existing `Entry (Δpts)` |
| SL | `leg.entry_sl` / row `entry_sl` | NEW — initial stop |
| TSL | `leg.premium_sl` / row `stop_loss` | existing `Stop`, relabelled |
| Exit | row `exit_state` | NEW — e.g. `1/2 red` |
| Target | constant `— (trail)` | NEW — trend-following, no fixed TP |
| Chg. / Chg.% | live tick vs Entry | existing |
| LTP | live tick | existing |

Premium columns (Entry/SL/TSL/Target) stay gated to `scan_source !== 'spot'`
(spot legs carry no premium). Exit shows for all sources. New columns respect the
existing per-column visibility toggles (`s.showSL`, `s.showTSL`, `s.showExit`,
`s.showTarget`), defaulting on. Flex containers keep `minWidth: 0` to avoid the
known column-clipping overflow.

### 4. Config UI (4th mode)

- `kiteEngine.ts`: `ScanSource` gains `'confluence'`; `OptionLeg`/`EngineSignalRow`
  gain `entry_sl?`, `EngineSignalRow` gains `exit_state?`, `source` union gains
  `'confluence'`.
- `SCAN_SOURCE_OPTS`: append `{ value:'confluence', label:'Confluence', hint:… }`.
  The settings-drawer `Segmented` picker and `settingsSummary()` derive from this
  list — no separate edit.
- `SCAN_SOURCE_QUICK_STYLE` (`Record<ScanSource,…>`, a hard compile gate): add a
  `confluence` entry (label `Conf`, colour `k.green`); widen the toggle track from
  28→40px and recompute knob positions (`spot:1, derivatives:10, both:18,
  confluence:27`). The quick toggle's cycle already derives from `SCAN_SOURCE_OPTS`
  order → Spot→Deriv→Both→Conf→Spot for free.
- `scanCost()`: add a `confluence` branch (same charts as `both`: spot + each
  option premium, but emits matched pairs only).

The existing Trail / Exit-Counter / Stop-anchor controls are unchanged — the
design reuses them (Entry = 3-green + fresh arrow, Exit = the counter, TSL =
ratchet on the `fast` anchor).

## Testing

- **Backend (TDD):** `test_scanner.py` — a confluence case where the underlying
  fires and the option premium confirms → one merged `source="confluence"` row
  with the confirmed leg; a case where the premium does NOT confirm → no leg /
  no row. Assert `entry_sl` and `exit_state` populated on `evaluate_item` and
  `evaluate_derivative_contract` outputs. Config round-trip test accepts
  `scan_source="confluence"`.
- **Frontend:** `tsc --noEmit` clean (the `Record<ScanSource,…>` gate proves the
  4th mode is wired everywhere); existing vitest suite stays green.

## Out of scope

- No new strategy validation (confluence is a filter over existing validated spot
  signals + unvalidated premium confirmation; same caveats as `both`).
- `scan-report` endpoint's hardcoded `scan_source='derivatives'` is left as-is
  (separate TODO).
